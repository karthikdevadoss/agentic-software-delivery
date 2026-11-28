"""Live data: read usage from the existing ledger, read/write outcomes,
learning records and the audit log. Reuses event_ledger's connection and
schema bootstrap (infra/event-ledger/schema.sql) -- no second database.

Which ledger rows become usage events, and how they are labelled:

  model_usage, source != claude_code   the platform's own gateway calls,
      billed to the platform's API key -> METERED_API; tokens come from the
      provider's usage object -> provider_reported.
  model_usage / claude_code_subagent_usage, source == claude_code
      the owner's Claude Code sessions (hook, agent/claude_code_hook.py),
      summed from the local session transcript. Claude Code runs on a
      subscription, so this is NOT API spend: it is valued at API list price
      as EQUIVALENT_API_VALUE; tokens -> imported (from the transcript).

Cost is always re-estimated from tokens with usage_intel.pricing so every
row uses the same, visible method. Nothing here reads prompt or response
content: payload excerpts in the ledger are ignored.
"""
from __future__ import annotations

import json
import uuid

from . import pricing
from .events import BillingCategory, Source, UsageEvent
from .learning import LearningRecord
from .outcomes import Outcome

OWNER_ORG, OWNER_TEAM, OWNER_USER = "org_platform_owner", "team_owner", "owner"
USAGE_TYPES = ("model_usage", "claude_code_subagent_usage")


def row_to_event(row: dict) -> UsageEvent:
    """Pure: one delivery_events row (as a dict) -> UsageEvent."""
    claude_code = (row.get("source") == "claude_code")
    ts = row.get("timestamp_utc")
    ts = ts.isoformat().replace("+00:00", "Z") if hasattr(ts, "isoformat") else ts
    tok_src = (Source.IMPORTED if claude_code else Source.PROVIDER_REPORTED).value
    ev = UsageEvent(
        event_id=row["event_id"], timestamp=ts, request_id=row["event_id"], trace_id=row.get("trace_id"),
        org_id=OWNER_ORG, team_id=OWNER_TEAM, user_id=OWNER_USER,
        project_id="agentic-software-delivery",
        feature="claude-code" if claude_code else (row.get("source") or "platform"),
        activity_category="software_development" if claude_code else (row.get("source") or "platform_runtime"),
        session_id=row.get("session_id") or row.get("run_id"), task_id=row.get("run_id"),
        provider=row.get("provider"), requested_model=row.get("model"), response_model=row.get("model"),
        input_tokens=row.get("input_tokens"), output_tokens=row.get("output_tokens"),
        cache_read_tokens=row.get("cache_read_tokens"), cache_write_tokens=row.get("cache_write_tokens"),
        duration_ms=row.get("duration_ms"),
        billing_category=(BillingCategory.EQUIVALENT_API_VALUE if claude_code else BillingCategory.METERED_API).value,
        success=True if row.get("status") not in ("error", "failed") else False,
        dataset="live")
    ev.provenance = {f: (tok_src if getattr(ev, f) is not None else Source.UNAVAILABLE.value)
                     for f in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")}
    ev.provenance["reasoning_tokens"] = Source.UNAVAILABLE.value
    ev.provenance["duration_ms"] = Source.APP_MEASURED.value if ev.duration_ms is not None else Source.UNAVAILABLE.value
    if claude_code:
        ev.provenance["note"] = ("Claude Code session usage summed from the local transcript; valued at API list "
                                 "price, not billed (subscription).")
    return pricing.estimate(ev)


def _conn():
    import event_ledger
    event_ledger.ensure_schema()
    return event_ledger._connect()  # noqa: SLF001 - reuse the ledger's hardened connection


def load_events(start: str | None = None, end: str | None = None, limit: int = 50_000) -> list[UsageEvent]:
    import psycopg2.extras
    sql = ("SELECT event_id, timestamp_utc, event_type, status, source, session_id, run_id, trace_id, provider, "
           "model, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, duration_ms "
           "FROM delivery_events WHERE event_type = ANY(%s)")
    params: list = [list(USAGE_TYPES)]
    if start:
        sql += " AND timestamp_utc >= %s"
        params.append(start)
    if end:
        sql += " AND timestamp_utc < (%s::date + 1)"
        params.append(end)
    sql += " ORDER BY timestamp_utc LIMIT %s"
    params.append(limit)
    conn = _conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [row_to_event(dict(r)) for r in cur.fetchall()]
    finally:
        conn.close()


def audit(actor: str, action: str, target: str | None, detail: dict, conn=None) -> None:
    own = conn is None
    conn = conn or _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO usage_audit_log (audit_id, actor, action, target, detail) VALUES (%s,%s,%s,%s,%s)",
                        ("au_" + uuid.uuid4().hex[:20], actor, action, target, json.dumps(detail)))
        if own:
            conn.commit()
    finally:
        if own:
            conn.close()


OUTCOME_COLS = ("outcome_id", "task_id", "outcome_type", "status", "evidence", "org_id", "team_id", "user_id",
                "project_id", "workflow_id", "activity_category", "difficulty", "attempts", "corrections",
                "human_review_minutes", "time_saved_minutes", "time_saved_source", "feedback")


def save_outcome(o: Outcome, actor: str) -> None:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            vals = [getattr(o, c) for c in OUTCOME_COLS]
            cur.execute(f"INSERT INTO usage_outcomes ({', '.join(OUTCOME_COLS)}, recorded_by) "
                        f"VALUES ({', '.join(['%s'] * (len(OUTCOME_COLS) + 1))}) "
                        "ON CONFLICT (outcome_id) DO NOTHING", vals + [actor])
        audit(actor, "outcome.create", o.outcome_id, {"task_id": o.task_id, "status": o.status, "evidence": o.evidence}, conn)
        conn.commit()
    finally:
        conn.close()


def load_outcomes() -> list[Outcome]:
    import psycopg2.extras
    conn = _conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"SELECT {', '.join(OUTCOME_COLS)}, recorded_at FROM usage_outcomes ORDER BY recorded_at")
            out = []
            for r in cur.fetchall():
                r = dict(r)
                ts = r.pop("recorded_at")
                out.append(Outcome(**r, timestamp=ts.isoformat().replace("+00:00", "Z"), dataset="live"))
            return out
    finally:
        conn.close()


LEARN_COLS = ("session_id", "section", "concept", "event", "user_id", "correct", "attempt", "evidence", "minutes", "source")


def save_learning(records: list[LearningRecord], actor: str) -> int:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            for r in records:
                cur.execute(f"INSERT INTO learning_records (record_id, {', '.join(LEARN_COLS)}) "
                            f"VALUES (%s, {', '.join(['%s'] * len(LEARN_COLS))})",
                            ["lr_" + uuid.uuid4().hex[:20]] + [getattr(r, c) for c in LEARN_COLS])
        audit(actor, "learning.create", None, {"records": len(records), "sources": sorted({r.source for r in records})}, conn)
        conn.commit()
        return len(records)
    finally:
        conn.close()


def load_learning() -> list[LearningRecord]:
    import psycopg2.extras
    conn = _conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"SELECT {', '.join(LEARN_COLS)}, recorded_at FROM learning_records ORDER BY recorded_at")
            out = []
            for r in cur.fetchall():
                r = dict(r)
                ts = r.pop("recorded_at")
                out.append(LearningRecord(**r, timestamp=ts.isoformat().replace("+00:00", "Z")))
            return out
    finally:
        conn.close()


def load_audit(limit: int = 200) -> list[dict]:
    import psycopg2.extras
    conn = _conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT audit_id, at, actor, action, target, detail FROM usage_audit_log ORDER BY at DESC LIMIT %s", (limit,))
            return [{**dict(r), "at": r["at"].isoformat()} for r in cur.fetchall()]
    finally:
        conn.close()
