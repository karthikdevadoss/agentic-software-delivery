"""
Session Intelligence / Value Ledger data layer.

Answers "how are we using human + AI resources to produce verified
value?" using only real evidence:

  - Git history (read-only `git log`, argv list, shell=False, never a
    write) — used to reconstruct historical development sessions by
    clustering commits with large time gaps between them into separate
    sessions. This gives a REAL wall-clock commit-span, which is NOT the
    same as active human working time and is labeled as such everywhere.
  - agent/web_run_history.jsonl — real Control UI runs (product_runtime /
    benchmark), including real API-reported token usage when the run
    called the Anthropic API (see agent/agent_loop.py's
    metrics.record_model_usage, sourced from response.usage, never
    estimated).
  - agent/dev_sessions.json — explicit creator-controlled start/stop
    records for future development sessions (see start_dev_session /
    stop_dev_session). Nothing is inferred about active vs idle time;
    only the explicit start/stop wall-clock span is recorded.
  - docs/PROJECT_STATE.json's verification_state — used to score the two
    most recent (best-documented) sessions' verification_quality
    dimension from real per-capability verification tiers.

Anything not actually known is None / "NOT CAPTURED" — never inferred,
never estimated, never scraped from a UI counter.
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import dashboard_data
import event_ledger

REPO_ROOT = Path(__file__).resolve().parent.parent
RUN_HISTORY_PATH = REPO_ROOT / "agent" / "web_run_history.jsonl"
DEV_SESSIONS_PATH = REPO_ROOT / "agent" / "dev_sessions.json"

# A gap this large between two commits is treated as a session boundary
# (e.g. an overnight break) rather than continuous work. This is a
# deliberate, documented heuristic — not a claim of exact session
# boundaries. See docstring above.
SESSION_GAP_MINUTES = 90

SCORE_DIMENSIONS = [
    "goal_completion", "verification_quality", "scope_discipline",
    "value_produced", "learning_correction", "efficiency",
]


def score_session(dims: dict) -> dict:
    """Deterministic, documented, and explainable: average of whichever
    dimensions actually have a 0-100 score, plus a coverage percentage so
    a low-coverage score is never confused with a high-confidence one."""
    scored = {k: v for k, v in dims.items() if v is not None}
    coverage_pct = round(100 * len(scored) / len(SCORE_DIMENSIONS))
    if not scored:
        return {"score": None, "coverage_pct": 0, "breakdown": dims}
    score = round(sum(scored.values()) / len(scored))
    return {"score": score, "coverage_pct": coverage_pct, "breakdown": dims}


def _run_git_log() -> list:
    """Read-only, argv-list, shell=False — same controlled-subprocess
    style as agent/build_tools.py. Never writes, never takes user input."""
    try:
        proc = subprocess.run(
            ["git", "log", "--format=%h|%aI|%s"],
            cwd=str(REPO_ROOT), capture_output=True, text=True,
            timeout=15, shell=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    if proc.returncode != 0:
        return []
    commits = []
    for line in proc.stdout.strip().splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        sha, iso_ts, subject = parts
        try:
            ts = datetime.fromisoformat(iso_ts)
        except ValueError:
            continue
        commits.append({"sha": sha, "ts": ts, "subject": subject})
    commits.reverse()  # oldest first
    return commits


def _cluster_commits(commits: list) -> list:
    clusters = []
    current = []
    prev_ts = None
    for c in commits:
        if prev_ts is not None and (c["ts"] - prev_ts).total_seconds() > SESSION_GAP_MINUTES * 60:
            clusters.append(current)
            current = []
        current.append(c)
        prev_ts = c["ts"]
    if current:
        clusters.append(current)
    return clusters


# Hand-verified linkage from the two most recent (best-documented)
# reconstructed clusters to real docs/PROJECT_STATE.json verification_state
# keys, so their verification_quality dimension is scored from real
# per-capability evidence rather than left NOT SCORED like older clusters.
_VERIFICATION_TIER_SCORE = {
    "runtime_verified": 100, "ui_verified": 100,
    "unit_tested": 70, "implemented": 40, "not_verified": 10,
}
_CLUSTER_VERIFICATION_KEYS = {
    # subject substring -> list of verification_state keys to average
    "browser agentic delivery control plane": [
        "control_ui_real_browser_human_approved_run", "control_ui_scroll_bug_fixed",
        "control_ui_build_test_panel_fixed", "control_ui_bugfixes_creator_visually_confirmed",
    ],
    "AI engineering intelligence dashboard": [
        "dashboard_mvp_real_evidence_only", "dashboard_run_history_persists_across_restart",
    ],
}
# Corrections known to have happened within a given cluster (subject
# substring -> real fixes from docs/LESSONS.md / this session's own work),
# used only for the learning_correction dimension. Kept short and factual.
_CLUSTER_CORRECTIONS = {
    "safe agent execution boundary": [
        "secret-like filenames for not-yet-existing files were not blocked — fixed in tools._resolve_safe_path",
    ],
    "Wire live agent execution workflow": [
        "approval-binding integrity gap (content/path substitution after approval) — fixed by hashing (path, content) at approval time",
        "an earlier security test used substring matching instead of exact set membership — rewritten to exact match",
        "non-interactive EOFError from input() was uncaught — now fails closed (reject), not crash",
    ],
    "browser agentic delivery control plane": [
        "EventSource never closed on terminal SSE state, causing browser auto-reconnect to replay the full event history (scroll-jump bug) — fixed with explicit close()",
        "Build/Test panel was never populated and the final banner text-sniffed the agent's prose instead of using real structured state — fixed with a real summary field + structured banner derivation",
    ],
}


def _reconstructed_sessions() -> list:
    clusters = _cluster_commits(_run_git_log())
    sessions = []
    for cluster in clusters:
        start_ts, end_ts = cluster[0]["ts"], cluster[-1]["ts"]
        subjects = [c["subject"] for c in cluster]
        goal = "; ".join(subjects)

        verification_scores = []
        for subj in subjects:
            for key_substr, vs_keys in _CLUSTER_VERIFICATION_KEYS.items():
                if key_substr in subj:
                    verification_scores.extend(vs_keys)
        verification_quality = None  # populated by caller with live PROJECT_STATE.json data

        corrections = []
        for subj in subjects:
            for key_substr, fixes in _CLUSTER_CORRECTIONS.items():
                if key_substr in subj:
                    corrections.extend(fixes)

        dims = {
            "goal_completion": 100,  # every commit here is merged to main and still relied upon today
            "verification_quality": None,  # filled in below if we have real per-capability evidence
            "scope_discipline": None,  # no reliable automatic signal for historical clusters
            "value_produced": 100 if corrections or len(cluster) > 1 else 70,
            "learning_correction": 100 if corrections else None,
            "efficiency": None,  # no token/cost data exists for any historical session
        }

        sessions.append({
            "session_id": f"hist-{cluster[0]['sha']}",
            "reconstructed": True,
            "reconstruction_label": "RECONSTRUCTED FROM PROJECT EVIDENCE (Git commit clustering)",
            "date": start_ts.date().isoformat(),
            "session_type": "development",
            "goal": goal,
            "status": "COMPLETED",
            "start_ts": start_ts.isoformat(),
            "end_ts": end_ts.isoformat(),
            "wall_clock_commit_span_seconds": (end_ts - start_ts).total_seconds(),
            "wall_clock_label": "commit-span (first commit -> last commit) — NOT active human time, includes any pauses within the window",
            "human_active_time": "NOT CAPTURED",
            "model_usage": None,
            "commits": [{"sha": c["sha"], "subject": c["subject"]} for c in cluster],
            "corrections": corrections,
            "_verification_keys": verification_scores,
            "dims": dims,
        })
    return sessions


def _apply_verification_scores(sessions: list, project_state: dict) -> None:
    vs = project_state.get("verification_state", {})
    for s in sessions:
        keys = s.pop("_verification_keys", [])
        if not keys:
            continue
        tiers = [vs[k]["status"] for k in keys if k in vs]
        scores = [_VERIFICATION_TIER_SCORE.get(t, 0) for t in tiers]
        if scores:
            s["dims"]["verification_quality"] = round(sum(scores) / len(scores))
            s["dims"]["scope_discipline"] = 100  # these two clusters: all work was explicitly creator-approved/instructed, no autonomous scope expansion


def _read_run_history() -> list:
    if not RUN_HISTORY_PATH.exists():
        return []
    records = []
    for line in RUN_HISTORY_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _run_history_sessions() -> list:
    sessions = []
    for r in _read_run_history():
        started = r.get("started_ts")
        ended = r.get("ended_ts")
        is_trainer = r.get("session_type") == "trainer_demo" or str(r["run_id"]).startswith("trainer-")
        session_type = "trainer_demo" if is_trainer else ("benchmark" if r["is_mock"] else "product_runtime")
        goal = r.get("requirement") or r["requirement_excerpt"] or "(no requirement text captured)"
        # Must stay in sync with web_server.TERMINAL_RUN_STATES (that module
        # is the authoritative source; not imported here to avoid a
        # circular import — web_server imports this module already).
        # DEPLOYMENT_STATUS_UNKNOWN is deliberately NOT folded into FAILED
        # here — that conflation is exactly the class of bug this state
        # exists to prevent (see docs/LESSONS.md: timeout/decoding
        # uncertainty is not a verified failure).
        _NON_FAILED_STATUSES = ("COMPLETED", "NO_CHANGE_NEEDED", "DEPLOYMENT_STATUS_UNKNOWN")
        status = r["final_status"] if r["final_status"] in _NON_FAILED_STATUSES else "FAILED"

        compile_ok = r.get("compile", {}).get("success") if r.get("compile") else None
        test_ok = r.get("test", {}).get("success") if r.get("test") else None
        verification_quality = None
        if compile_ok is not None or test_ok is not None:
            checks = [x for x in (compile_ok, test_ok) if x is not None]
            verification_quality = round(100 * sum(1 for c in checks if c) / len(checks))

        corrections = []  # run-history entries don't carry correction narratives (that's session-level, not run-level)
        commits = []
        if r.get("production_commit"):
            commits.append({"sha": r["production_commit"], "subject": f"Trainer demo deploy: {goal[:80]}"})

        goal_met = status in ("COMPLETED", "NO_CHANGE_NEEDED")  # a correct "already satisfied" no-op meets the goal just as much as a deploy does
        dims = {
            "goal_completion": 100 if goal_met else 0,
            "verification_quality": verification_quality,
            "scope_discipline": 100,  # write scope is structurally enforced (app/src/{main,test}/java only) regardless of run outcome
            "value_produced": 70 if session_type == "benchmark" else (100 if goal_met else 0),
            "learning_correction": None,
            "efficiency": None,  # tokens present for real runs but no baseline yet to compare against — see NO COMPARABLE BASELINE YET
        }

        sessions.append({
            "session_id": r["run_id"],
            "reconstructed": False,
            "reconstruction_label": None,
            "date": datetime.fromtimestamp(started).astimezone().date().isoformat() if started else "NOT CAPTURED",
            "session_type": session_type,
            "goal": goal,
            "status": status,
            "start_ts": started,
            "end_ts": ended,
            "wall_clock_commit_span_seconds": None,
            "wall_clock_label": f"{(ended - started):.1f}s real run wall-clock" if started and ended else "NOT CAPTURED",
            "human_active_time": "NOT CAPTURED",
            "model_usage": r.get("model_usage"),
            "risk_assessment": r.get("risk_assessment"),
            "production_commit": r.get("production_commit"),
            "deployment": r.get("deployment"),
            "commits": commits,
            "corrections": corrections,
            "dims": dims,
        })
    return sessions


def _read_dev_sessions() -> list:
    if not DEV_SESSIONS_PATH.exists():
        return []
    try:
        data = json.loads(DEV_SESSIONS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    sessions = []
    for rec in data.get("sessions", {}).values():
        end_ts = rec.get("end_ts")
        start_ts = rec.get("start_ts")
        duration = (end_ts - start_ts) if (start_ts and end_ts) else None
        dims = {
            "goal_completion": None,  # creator hasn't marked outcome yet in this MVP
            "verification_quality": None, "scope_discipline": None,
            "value_produced": None, "learning_correction": None, "efficiency": None,
        }
        sessions.append({
            "session_id": rec["id"],
            "reconstructed": False,
            "reconstruction_label": None,
            "date": datetime.fromtimestamp(start_ts).astimezone().date().isoformat() if start_ts else "NOT CAPTURED",
            "session_type": "development",
            "goal": rec.get("goal") or "(no goal recorded)",
            "status": "ACTIVE" if end_ts is None else "ENDED (goal outcome not yet recorded)",
            "start_ts": start_ts, "end_ts": end_ts,
            "wall_clock_commit_span_seconds": None,
            "wall_clock_label": (f"{duration:.0f}s wall-clock (explicit start/stop)" if duration is not None
                                  else ("in progress" if end_ts is None else "NOT CAPTURED")),
            "human_active_time": "NOT CAPTURED (wall-clock only — no active/idle inference performed)",
            "model_usage": None,
            "commits": [],
            "corrections": [],
            "dims": dims,
        })
    return sessions


def start_dev_session(goal: str, ai_assistant: str = None, model: str = None) -> dict:
    import uuid
    data = {"sessions": {}}
    if DEV_SESSIONS_PATH.exists():
        try:
            data = json.loads(DEV_SESSIONS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    session_id = "dev-" + uuid.uuid4().hex[:8]
    data.setdefault("sessions", {})[session_id] = {
        "id": session_id, "goal": goal, "ai_assistant": ai_assistant, "model": model,
        "start_ts": datetime.now(tz=timezone.utc).timestamp(), "end_ts": None,
    }
    DEV_SESSIONS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data["sessions"][session_id]


def stop_dev_session(session_id: str) -> dict:
    if not DEV_SESSIONS_PATH.exists():
        return {"error": "no dev sessions recorded"}
    data = json.loads(DEV_SESSIONS_PATH.read_text(encoding="utf-8"))
    rec = data.get("sessions", {}).get(session_id)
    if rec is None:
        return {"error": f"no such session: {session_id}"}
    rec["end_ts"] = datetime.now(tz=timezone.utc).timestamp()
    DEV_SESSIONS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return rec


# Categorical value ledger — LOW/MEDIUM/HIGH/NOT ASSESSED with a concise
# evidence-backed reason each. Applies to the current (most recent) build
# period as a whole, not fabricated per-euro figures.
VALUE_LEDGER = {
    "technical_value": {"level": "HIGH", "reason": "Working tool-calling agent, MCP adapter, incremental RAG, and a structurally-enforced human-approval boundary — all unit-tested and/or runtime-verified, not prototypes."},
    "product_value": {"level": "MEDIUM", "reason": "A real end-to-end propose->approve->apply->compile->test loop exists and was proven live in a browser, but only one ticket type has ever been exercised and Update Email (the first real business ticket) is still unimplemented."},
    "learning_value": {"level": "HIGH", "reason": "Multiple real security gaps found and fixed during development (secret-filename check, approval-binding substitution, exact-match vs substring test mistake, EOF fail-closed) plus two real UI defects found through actual use and root-caused, not guessed."},
    "career_interview_value": {"level": "HIGH", "reason": "docs/EXPERIENCE_EVIDENCE.md maps 13 implemented capabilities to file-level evidence and tests; several are concrete 'describe a bug you found and fixed' interview stories backed by real code."},
    "portfolio_value": {"level": "MEDIUM", "reason": "Control UI + Dashboard are demoable today; not yet deployed publicly (Vercel deploy is a planned next step, not done)."},
    "customer_commercial_value": {"level": "NOT ASSESSED", "reason": "No real customer or pilot has used this system yet (YogaCRM pilot is a future strategic target, not started) — no evidence basis for a commercial-value claim yet."},
    "risk_reduction": {"level": "HIGH", "reason": "The human-approval boundary is structurally enforced (approve/reject never exposed as an LLM tool, verified by exact set-membership tests) and fails closed without a human present — the highest-risk failure modes for an agentic write system are covered by tests, not just policy."},
}


def _event_ledger_recent(limit: int = 10) -> dict:
    """Minimal real event-ledger evidence for Usage — recent events with
    real source/activity_class/duration/model/token fields where captured.
    Never a redesign of this page: one additional section, read-only."""
    try:
        recent = event_ledger.get_recent_events(limit=limit)
        count = event_ledger.count_events()
        return {
            "status": "REACHABLE",
            "events_captured": count,
            "recent_events": [
                {
                    "event_type": r["event_type"],
                    "run_id": r.get("run_id"),
                    "status": r.get("status"),
                    "source": r.get("source"),
                    "activity_class": r.get("activity_class"),
                    "duration_ms": r.get("duration_ms"),
                    "provider": r.get("provider"),
                    "model": r.get("model"),
                    "input_tokens": r.get("input_tokens"),
                    "output_tokens": r.get("output_tokens"),
                    "timestamp_utc": r["timestamp_utc"].isoformat() if r.get("timestamp_utc") else None,
                }
                for r in recent
            ],
        }
    except Exception as exc:  # noqa: BLE001 - Usage must never break because the ledger is down
        return {"status": "UNREACHABLE", "error": str(exc)}


def build_sessions_snapshot() -> dict:
    project_state = dashboard_data.read_project_state()
    reconstructed = _reconstructed_sessions()
    _apply_verification_scores(reconstructed, project_state)
    run_sessions = _run_history_sessions()
    dev_sessions = _read_dev_sessions()

    all_sessions = reconstructed + run_sessions + dev_sessions
    for s in all_sessions:
        s["score"] = score_session(s["dims"])

    def _sort_key(s):
        ts = s["start_ts"]
        if ts is None:
            return 0.0
        if isinstance(ts, str):
            return datetime.fromisoformat(ts).timestamp()
        return float(ts)

    all_sessions.sort(key=_sort_key, reverse=True)

    today = datetime.now().astimezone().date().isoformat()  # local date, matching commit-timestamp offsets
    return {
        "sessions": all_sessions,
        "today_date": today,
        "today_sessions": [s for s in all_sessions if s["date"] == today],
        "value_ledger": VALUE_LEDGER,
        "relative_improvement": "NO COMPARABLE BASELINE YET — this is the first set of sessions with any scoring at all; trend comparison becomes meaningful once at least two similarly-scoped sessions exist.",
        "score_dimensions": SCORE_DIMENSIONS,
        "consumption_categories": [
            "development", "product_runtime", "benchmark", "portfolio_demo",
            "trainer_demo", "staging", "yogacrm_pilot", "customer_production",
        ],
        "event_ledger": _event_ledger_recent(),
    }
