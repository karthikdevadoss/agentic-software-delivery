"""Read-only data sources for the budget and eval pages. No invented values:
everything is either read from a real file/module or reported as absent."""
import json
import sqlite3
from pathlib import Path

from django.conf import settings


def eval_snapshot() -> dict:
    path = Path(settings.EVAL_RESULTS_PATH)
    if not path.is_file():
        return {"present": False, "path": str(path), "data": None}
    return {"present": True, "path": str(path), "data": json.loads(path.read_text(encoding="utf-8"))}


def eval_history() -> dict:
    """Real rows from agent/web/eval-history/index.json (written by
    agent/publish_eval_results.py) when the directory exists. Rows are read,
    never synthesised; an unreadable/missing index degrades to a file listing."""
    d = Path(settings.EVAL_HISTORY_DIR)
    if not d.is_dir():
        return {"present": False, "path": str(d), "files": [], "entries": [], "index_error": None}
    files = sorted(p.name for p in d.iterdir() if p.is_file())
    entries, err = [], None
    idx = d / "index.json"
    if idx.is_file():
        try:
            raw = json.loads(idx.read_text(encoding="utf-8")).get("entries", [])
            for e in raw:
                entries.append({
                    "generated_at": e.get("generated_at"), "commit_sha": (e.get("commit_sha") or "")[:7],
                    "overall_passed": e.get("overall_passed"), "source": e.get("source"),
                    "suites": [{"key": x.get("key"), "kind": x.get("kind"), "score": x.get("score"),
                                "passed": x.get("passed")} for x in e.get("suites", [])],
                })
            entries.sort(key=lambda e: e["generated_at"] or "", reverse=True)
        except (ValueError, OSError, AttributeError) as exc:
            err = f"{exc.__class__.__name__}: {exc}"
    return {"present": True, "path": str(d), "files": files, "entries": entries, "index_error": err}


def endpoint_budget_limits() -> list:
    """Configured LIMITS of the per-endpoint policies (triage / strategy
    interviewer). Their counters now live in the durable store below (scopes
    'triage' and 'si'); the limits are read from env/defaults of THIS process."""
    import si_budget
    import triage_budget
    return [
        {"name": "Triage (agent/triage_budget.py)", "limits": triage_budget.limits(),
         "note": "env-overridable; defaults shown unless TRIAGE_* env is set in THIS process"},
        {"name": "Strategy interviewer (agent/si_budget.py)", "limits": {
            "daily_usd_budget": si_budget.SI_DAILY_USD_BUDGET,
            "usd_per_answer_estimate": si_budget.SI_USD_PER_ANSWER,
            "daily_max_answers": si_budget.SI_DAILY_MAX_ANSWERS,
            "per_visitor_min_seconds": si_budget.SI_PER_VISITOR_MIN_SECONDS,
            "per_visitor_daily_max": si_budget.SI_PER_VISITOR_DAILY_MAX},
         "note": "usd_per_answer is a measured average used as an estimate, not an accounting figure"},
    ]


# Back-compat name used by older tests/templates.
in_memory_budgets = endpoint_budget_limits


def gateway_limits() -> dict:
    """Platform caps (agent/gateway_budget.py), from env/defaults of THIS
    process. If the Starlette process runs with different GATEWAY_* env the
    'remaining' figure here is computed against THIS process's caps -- said so
    on the page."""
    import gateway_budget
    return gateway_budget.limits()


def durable_budget_store() -> dict:
    """The durable SQLite budget store written by agent/budget_store.py.
    Opened mode=ro (never creates, never writes). Reads the real
    `budget_ledger` table: per-scope calls and USD for today (UTC). USD values
    are reservations (worst-case estimates) until `settled`=1; both are
    reported separately so nothing is presented as more certain than it is.
    A file without that table is reported as such, not guessed at."""
    import time
    path = Path(settings.BUDGET_SQLITE_PATH)
    base = {"present": False, "path": str(path), "tables": {}, "scopes": [], "error": None,
            "has_ledger_table": False, "day_utc": time.strftime("%Y-%m-%d", time.gmtime()),
            "gateway": None}
    if str(path) == ":memory:" or not path.is_file():
        return base
    base["present"] = True
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            names = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            base["tables"] = {n: conn.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}
            if "budget_ledger" in names:
                base["has_ledger_table"] = True
                rows = conn.execute(
                    "SELECT scope, COUNT(*), COALESCE(SUM(usd),0), COALESCE(SUM(settled),0) "
                    "FROM budget_ledger WHERE day=? GROUP BY scope ORDER BY scope",
                    (base["day_utc"],)).fetchall()
                base["scopes"] = [{"scope": r[0], "calls": r[1], "usd": round(r[2], 6),
                                   "settled_calls": r[3], "reserved_only_calls": r[1] - r[3]}
                                  for r in rows]
                lim = gateway_limits()
                spent = next((s["usd"] for s in base["scopes"] if s["scope"] == "gateway"), 0.0)
                base["gateway"] = {
                    "spent_or_reserved_usd": spent,
                    "daily_usd_cap": lim["daily_usd_cap"],
                    "remaining_usd": round(max(lim["daily_usd_cap"] - spent, 0.0), 6),
                }
        finally:
            conn.close()
    except sqlite3.Error as exc:
        base["error"] = str(exc)
    return base
