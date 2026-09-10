"""
Durable, append-only event ledger for observable Agentic Software Delivery
activity — the P0 "no more lost engineering events" foundation.

Canonical envelope, one Postgres table (infra/event-ledger/schema.sql),
write-through as events happen (never batched to run-end). Backed by
Railway PostgreSQL (project agentic-delivery-events, see
docs/RESOURCE_REGISTRY.md) reached over its public TCP proxy from this
laptop's local Workbench execution engine — no server-side code runs
inside Railway for this table, so the private-network DATABASE_URL
Railway injects into other services is not reachable here; a public TCP
proxy endpoint is used instead (see docs/RESOURCE_REGISTRY.md).

Outage-safety: if the remote insert fails for ANY reason (network,
credential, timeout), the event is appended to a local JSONL spool
(agent/event_spool.jsonl, gitignored) instead of being dropped, and
sync_spool() later retries — idempotent via event_id (ON CONFLICT DO
NOTHING), so a duplicate retry is provably a no-op, never a duplicate
row. The spool is a fallback, not canonical long-term truth — nothing is
ever deleted from it until a remote insert genuinely succeeds.
"""

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

import tools  # reuse tools.redact_secrets — no duplicated security logic

load_dotenv()  # same pattern as agent/main.py — loads agent/.env

# v2: added activity_class (PRODUCT_DEVELOPMENT vs PRODUCT_RUNTIME) for the
# Claude Code development-telemetry source. Additive/backward-compatible —
# v1 rows remain valid, they simply predate this field (honestly None).
SCHEMA_VERSION = 2
REPO_ROOT = Path(__file__).resolve().parent.parent
SPOOL_PATH = Path(__file__).resolve().parent / "event_spool.jsonl"
SYNC_LOCK_PATH = Path(__file__).resolve().parent / "event_ledger_sync.lock"

# activity_class values — distinguishes what this platform BUILDS (our own
# Claude Code development activity) from what this platform DOES at
# runtime (the Workbench executing on behalf of a requirement). Never
# mixed indistinguishably even though both share this one table.
ACTIVITY_CLASS_PRODUCT_DEVELOPMENT = "PRODUCT_DEVELOPMENT"
ACTIVITY_CLASS_PRODUCT_RUNTIME = "PRODUCT_RUNTIME"

# Data-safety/training-eligibility classification (Section 4). Distinct
# concepts, not free text, so a consumer can filter reliably.
TRAINING_ALLOWED = "TRAINING_ALLOWED"
TRAINING_ALLOWED_AFTER_REDACTION = "TRAINING_ALLOWED_AFTER_REDACTION"
EVAL_ONLY = "EVAL_ONLY"
OPERATIONS_ONLY = "OPERATIONS_ONLY"
PERSONAL_DATA_RESTRICTED = "PERSONAL_DATA_RESTRICTED"
SECRET_NEVER_STORE = "SECRET_NEVER_STORE"

ENVELOPE_FIELDS = (
    "event_id", "schema_version", "timestamp_utc", "event_type", "stage",
    "status", "actor_type", "actor_id", "actor_role", "session_id",
    "run_id", "requirement_id", "trace_id", "correlation_id", "source",
    "service", "environment", "duration_ms", "provider", "model",
    "input_tokens", "output_tokens", "cache_read_tokens",
    "cache_write_tokens", "tool_name", "tool_call_id", "git_commit",
    "deployment_version", "data_classification", "retention_class",
    "training_eligibility", "payload", "backfill_source",
    "evidence_quality", "activity_class",
)

# Real event types this session's Workbench pipeline actually emits.
# Not every type in this list has a live producer yet — see
# docs/PROJECT_STATE.json for exactly which ones are wired vs. reserved
# for a future ingestion source (e.g. Claude Code development activity).
KNOWN_EVENT_TYPES = frozenset({
    "requirement_received", "risk_assessment",
    "run_started", "stage_started", "stage_completed",
    "model_call_started", "model_call_completed", "model_usage", "model_error",
    "retrieval_started", "retrieval_result",
    "tool_call_started", "tool_call_completed", "tool_call_failed",
    "change_proposed", "authorization_requested", "authorization_decision", "change_applied",
    "build_started", "build_completed", "build_failed",
    "test_started", "test_completed", "test_failed",
    "commit_created",
    "deployment_started", "deployment_status", "deployment_completed",
    "deployment_failed", "deployment_status_unknown",
    "production_verification_started", "production_verified", "production_verification_failed",
    "transport_degraded", "transport_recovered",
    "run_completed", "run_failed", "run_no_change",
    "human_input_requested", "human_decision",
    "error", "timeout",
    "correction_recorded", "regression_verified",

    # Claude Code development-activity source (activity_class=
    # PRODUCT_DEVELOPMENT) — genuinely new event shapes, not a forced fit
    # into the Workbench/PRODUCT_RUNTIME taxonomy above. See
    # agent/claude_code_hook.py.
    "dev_session_started", "dev_session_ended",
    "user_prompt_submitted", "dev_turn_stopped",
    "subagent_started", "subagent_stopped",
})

_lock = threading.Lock()
_schema_ready = False


def _connection_string():
    return os.environ.get("EVENT_LEDGER_DATABASE_URL")


def _connect():
    import psycopg2
    url = _connection_string()
    if not url:
        raise RuntimeError("EVENT_LEDGER_DATABASE_URL not configured")
    return psycopg2.connect(url, connect_timeout=8)


def ensure_schema():
    global _schema_ready
    if _schema_ready:
        return
    schema_sql = (REPO_ROOT / "infra" / "event-ledger" / "schema.sql").read_text(encoding="utf-8")
    conn = _connect()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(schema_sql)
        _schema_ready = True
    finally:
        conn.close()


def _redact_payload(payload):
    """Applies tools.redact_secrets() to every string value in a payload,
    recursively — the same deterministic pattern already used for RAG
    ingestion and tool traces, reused here rather than reimplemented."""
    if payload is None:
        return None
    if isinstance(payload, str):
        return tools.redact_secrets(payload)
    if isinstance(payload, dict):
        return {k: _redact_payload(v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [_redact_payload(v) for v in payload]
    return payload


def build_envelope(event_type, **fields):
    """Constructs one canonical event envelope. Unknown kwargs are an
    error (fail fast on a typo) rather than silently accepted. Any field
    not supplied is None — never invented. payload is redacted here, at
    construction time, so both the remote insert and the local spool
    fallback only ever see already-redacted text."""
    unknown = set(fields) - set(ENVELOPE_FIELDS)
    if unknown:
        raise TypeError(f"build_envelope() got unexpected field(s): {unknown}")
    envelope = {f: None for f in ENVELOPE_FIELDS}
    envelope["event_id"] = str(uuid.uuid4())
    envelope["schema_version"] = SCHEMA_VERSION
    envelope["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    envelope["event_type"] = event_type
    envelope.update(fields)
    envelope["payload"] = _redact_payload(envelope.get("payload"))
    return envelope


def _insert(envelope):
    import psycopg2.extras
    ensure_schema()
    conn = _connect()
    try:
        with conn, conn.cursor() as cur:
            cols = ENVELOPE_FIELDS
            values = [envelope.get(c) for c in cols]
            payload_idx = cols.index("payload")
            values[payload_idx] = (
                psycopg2.extras.Json(envelope.get("payload"))
                if envelope.get("payload") is not None else None
            )
            placeholders = ", ".join(["%s"] * len(cols))
            cur.execute(
                f"INSERT INTO delivery_events ({', '.join(cols)}) VALUES ({placeholders}) "
                f"ON CONFLICT (event_id) DO NOTHING",
                values,
            )
    finally:
        conn.close()


def _spool_append(envelope):
    with _lock:
        with SPOOL_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(envelope) + "\n")


def record_event(event_type, **fields):
    """The one write-through entry point. Tries the remote ledger first;
    on ANY failure, falls back to the local spool rather than dropping
    the event. Never raises to the caller — a telemetry failure must
    never break the actual Workbench run it's observing."""
    envelope = build_envelope(event_type, **fields)
    try:
        _insert(envelope)
        return {"event_id": envelope["event_id"], "remote_persisted": True}
    except Exception as exc:  # noqa: BLE001 - telemetry must never crash the caller
        _spool_append(envelope)
        return {"event_id": envelope["event_id"], "remote_persisted": False, "spooled": True, "error": str(exc)}


def sync_spool():
    """Drains the local spool: attempts each spooled event's insert,
    keeps only genuinely-still-failing ones in the file. Idempotent — an
    event already inserted (e.g. a prior partial sync) is a safe
    ON CONFLICT DO NOTHING no-op, never a duplicate row. Never deletes an
    event that hasn't actually been confirmed inserted remotely."""
    if not SPOOL_PATH.exists():
        return {"synced": 0, "remaining": 0}
    with _lock:
        lines = [l for l in SPOOL_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
        synced = 0
        still_failing = []
        for line in lines:
            envelope = json.loads(line)
            try:
                _insert(envelope)
                synced += 1
            except Exception:  # noqa: BLE001
                still_failing.append(line)
        if still_failing:
            SPOOL_PATH.write_text("\n".join(still_failing) + "\n", encoding="utf-8")
        else:
            SPOOL_PATH.unlink(missing_ok=True)
    return {"synced": synced, "remaining": len(still_failing)}


def spool_pending_count():
    if not SPOOL_PATH.exists():
        return 0
    return sum(1 for l in SPOOL_PATH.read_text(encoding="utf-8").splitlines() if l.strip())


def spool_only(event_type, **fields):
    """Fast path for callers that must never block on network at all —
    specifically Claude Code hooks (agent/claude_code_hook.py), which must
    return in milliseconds or they visibly slow down every tool call/
    session event. Unlike record_event(), this makes ZERO network attempt
    (no _insert(), no ensure_schema()) — it only builds the envelope
    (redaction still applied) and appends to the same spool file
    record_event() already falls back to. A background sync
    (trigger_background_sync() / sync_spool()) reconciles it later,
    through the exact same idempotent ON CONFLICT DO NOTHING path as
    every other spooled event — this is not a second telemetry system,
    just a second producer into the same one."""
    envelope = build_envelope(event_type, **fields)
    _spool_append(envelope)
    return {"event_id": envelope["event_id"], "remote_persisted": False, "spooled": True}


def trigger_background_sync():
    """Best-effort, non-blocking: spawns a detached background process to
    drain the spool, without making the caller wait even a millisecond
    for network I/O. Guarded by a lock file so a burst of hook events
    (e.g. several tool calls in a row) doesn't pile up redundant sync
    processes — if a sync is already in flight, this is a no-op. Never
    raises: a failure to even SPAWN the background sync must not be
    allowed to slow down or break the caller (a Claude Code hook)."""
    try:
        if SYNC_LOCK_PATH.exists():
            return {"spawned": False, "reason": "sync already in progress"}
        SYNC_LOCK_PATH.touch(exist_ok=False)
    except OSError:
        return {"spawned": False, "reason": "could not acquire sync lock"}

    try:
        import subprocess
        import sys
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--sync-spool"],
            cwd=str(Path(__file__).resolve().parent),
            creationflags=creationflags,
            close_fds=True,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return {"spawned": True}
    except Exception as exc:  # noqa: BLE001 - spawning telemetry sync must never break the caller
        try:
            SYNC_LOCK_PATH.unlink(missing_ok=True)
        except OSError:
            pass
        return {"spawned": False, "reason": str(exc)}


# --- one-time historical backfill (Section 9) ----------------------------

# Fixed, arbitrary namespace UUID — used only to derive stable, deterministic
# backfill event_ids (uuid5 of run_id + a discriminator), so re-running
# backfill_from_run_history() is a safe no-op via the normal ON CONFLICT DO
# NOTHING idempotency, with no separate "already imported" tracking needed.
_BACKFILL_NAMESPACE = uuid.UUID("6ff1b1ba-8a1b-4c1e-9a52-2f7c1e6b1a11")

# agent/web_run_history.jsonl's final_status values, mapped onto the
# canonical taxonomy — mirrors web_server.py's _STAGE_TO_CANONICAL_TYPE.
# Anything not in this map falls back to "run_completed" only when the
# source row's own final_status is missing/unrecognized; a genuinely
# unknown historical status is never silently called a failure.
_BACKFILL_STATUS_MAP = {
    "COMPLETED": "run_completed",
    "FAILED": "run_failed",
    "NO_CHANGE_NEEDED": "run_no_change",
    "DEPLOYMENT_STATUS_UNKNOWN": "deployment_status_unknown",
}


def _backfill_event_id(run_id, discriminator):
    return str(uuid.uuid5(_BACKFILL_NAMESPACE, f"{run_id}|{discriminator}"))


def backfill_from_run_history(history_path=None):
    """One-time, safely re-runnable importer for the pre-existing local
    run-summary log (agent/web_run_history.jsonl) captured before this
    ledger existed. Never fabricates a field absent from the source: uses
    each row's own real ended_ts/started_ts as timestamp_utc (falling back
    to insertion time only if genuinely neither was captured), and tags
    every imported row with backfill_source="historical_backfill" and
    evidence_quality="partial_reconstructed" so it can never be confused
    with a live write-through event — each source row is a per-run
    SUMMARY, not the individual-event granularity live capture provides.

    Returns counts of rows PROCESSED this call (idempotent — rerunning
    reports the same processed count each time, not a growing "new rows"
    count, since a duplicate event_id is a safe no-op)."""
    path = Path(history_path) if history_path else (REPO_ROOT / "agent" / "web_run_history.jsonl")
    if not path.exists():
        return {"rows": 0, "processed": 0, "skipped": 0}

    rows = 0
    processed = 0
    skipped = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows += 1
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        run_id = row.get("run_id")
        if not run_id:
            skipped += 1
            continue

        ts = row.get("ended_ts")
        if ts is None:
            ts = row.get("started_ts")
        ts_kwargs = {}
        if ts is not None:
            ts_kwargs["timestamp_utc"] = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

        source = "workbench_mock" if row.get("is_mock") else "workbench"
        canonical_type = _BACKFILL_STATUS_MAP.get(row.get("final_status"), "run_completed")

        outcome_result = record_event(
            canonical_type,
            event_id=_backfill_event_id(run_id, "outcome"),
            run_id=run_id, source=source, service="web_server",
            status=row.get("final_status"),
            backfill_source="historical_backfill", evidence_quality="partial_reconstructed",
            training_eligibility=TRAINING_ALLOWED_AFTER_REDACTION,
            payload=row,
            **ts_kwargs,
        )
        if outcome_result["remote_persisted"] or outcome_result.get("spooled"):
            processed += 1
        else:
            skipped += 1

        usage = row.get("model_usage")
        if usage:
            record_event(
                "model_usage",
                event_id=_backfill_event_id(run_id, "model_usage"),
                run_id=run_id, source=source, service="web_server",
                provider=usage.get("provider"), model=usage.get("model"),
                input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"),
                backfill_source="historical_backfill", evidence_quality="partial_reconstructed",
                training_eligibility=OPERATIONS_ONLY,
                **ts_kwargs,
            )

    return {"rows": rows, "processed": processed, "skipped": skipped}


def _transcript_message_text(message):
    """Real human/assistant text only — excludes tool_result-wrapped
    content, which Claude Code's transcript format also files under the
    'user' role but is not something a human actually typed."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return " ".join(parts)
    return ""


def backfill_from_claude_code_transcript(transcript_path, window_start_iso, window_end_iso, session_label):
    """One-time, safely re-runnable importer of REAL Claude Code session
    transcript evidence (~/.claude/projects/.../<session>.jsonl) for a
    bounded time window — used to backfill development activity that
    occurred before agent/claude_code_hook.py existed to capture it live.

    Deliberately scoped to [window_start_iso, window_end_iso] rather than
    a whole (potentially many-day, many-task) transcript file — this is a
    backfill of ONE specific prior task's evidence, not a full-history
    import. Every event_id is derived from the transcript's own real
    per-entry `uuid` field (uuid5, deterministic) so rerunning this is a
    safe no-op via the usual ON CONFLICT DO NOTHING idempotency.

    Captures only what the transcript genuinely contains: real user
    prompt text (redacted, with real char/word counts) and real tool_use
    invocations (tool name only — the transcript does not reliably expose
    paired success/failure without deeper tool_result correlation, so
    that is NOT fabricated here). Never invents timestamps: every event's
    timestamp_utc is the transcript's own real `timestamp` field."""
    path = Path(transcript_path)
    if not path.exists():
        return {"rows": 0, "processed": 0, "skipped": 0}

    start = datetime.fromisoformat(window_start_iso.replace("Z", "+00:00"))
    end = datetime.fromisoformat(window_end_iso.replace("Z", "+00:00"))

    rows = 0
    processed = 0
    skipped = 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts_raw = entry.get("timestamp")
            if not ts_raw:
                continue
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except ValueError:
                continue
            if not (start <= ts <= end):
                continue

            entry_type = entry.get("type")
            entry_uuid = entry.get("uuid")
            if entry_type not in ("user", "assistant") or not entry_uuid:
                continue

            message = entry.get("message", {})

            if entry_type == "user":
                text = _transcript_message_text(message)
                if not text:
                    continue  # a tool_result-wrapped entry, not a real human prompt
                rows += 1
                result = record_event(
                    "user_prompt_submitted",
                    event_id=str(uuid.uuid5(_BACKFILL_NAMESPACE, f"claude_code_transcript|{entry_uuid}")),
                    timestamp_utc=ts.isoformat(),
                    session_id=session_label, source="claude_code",
                    activity_class=ACTIVITY_CLASS_PRODUCT_DEVELOPMENT,
                    actor_type="human",
                    backfill_source="historical_backfill", evidence_quality="partial_reconstructed",
                    training_eligibility=TRAINING_ALLOWED_AFTER_REDACTION,
                    payload={"prompt_char_count": len(text), "prompt_word_count": len(text.split()), "prompt_excerpt": text[:2000]},
                )
                processed += 1 if (result["remote_persisted"] or result.get("spooled")) else 0
                if not (result["remote_persisted"] or result.get("spooled")):
                    skipped += 1
                continue

            # assistant entry: one event per real tool_use block
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for i, block in enumerate(content):
                if not (isinstance(block, dict) and block.get("type") == "tool_use"):
                    continue
                rows += 1
                result = record_event(
                    "tool_call_started",
                    event_id=str(uuid.uuid5(_BACKFILL_NAMESPACE, f"claude_code_transcript|{entry_uuid}|tool_use|{i}")),
                    timestamp_utc=ts.isoformat(),
                    session_id=session_label, source="claude_code",
                    activity_class=ACTIVITY_CLASS_PRODUCT_DEVELOPMENT,
                    actor_type="ai",
                    tool_name=block.get("name"),
                    backfill_source="historical_backfill", evidence_quality="partial_reconstructed",
                    training_eligibility=TRAINING_ALLOWED_AFTER_REDACTION,
                )
                if result["remote_persisted"] or result.get("spooled"):
                    processed += 1
                else:
                    skipped += 1

    return {"rows": rows, "processed": processed, "skipped": skipped}


# --- read queries (minimal, for Dashboard/Usage live-proof only) ---------

def get_recent_events(limit=20):
    ensure_schema()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT event_id, timestamp_utc, event_type, run_id, status "
                "FROM delivery_events ORDER BY timestamp_utc DESC LIMIT %s",
                (limit,),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def get_run_events(run_id):
    ensure_schema()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT event_id, timestamp_utc, event_type, stage, status, payload "
                "FROM delivery_events WHERE run_id = %s ORDER BY timestamp_utc ASC",
                (run_id,),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def count_events():
    ensure_schema()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM delivery_events")
            return cur.fetchone()[0]
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    # Entrypoint for trigger_background_sync()'s detached subprocess only —
    # not a general CLI. Always releases the lock, even on failure, so a
    # crashed sync never permanently blocks future sync attempts.
    if "--sync-spool" in sys.argv:
        try:
            result = sync_spool()
            print(f"SYNC: {result}")
        finally:
            SYNC_LOCK_PATH.unlink(missing_ok=True)
