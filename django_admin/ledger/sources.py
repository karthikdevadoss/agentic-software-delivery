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
    d = Path(settings.EVAL_HISTORY_DIR)
    if not d.is_dir():
        return {"present": False, "path": str(d), "files": []}
    return {"present": True, "path": str(d), "files": sorted(p.name for p in d.iterdir() if p.is_file())}


def in_memory_budgets() -> list:
    """Configured LIMITS only. The counters live in the Starlette process's
    memory; this separate Django process cannot see them, so it shows none."""
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


def durable_budget_store() -> dict:
    """Optional SQLite file from the (unmerged) durable budget store PR. Schema
    is not assumed: we list tables and row counts only. Opened mode=ro."""
    path = Path(settings.BUDGET_SQLITE_PATH)
    if not path.is_file():
        return {"present": False, "path": str(path), "tables": {}, "error": None}
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            names = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            tables = {n: conn.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}
        finally:
            conn.close()
        return {"present": True, "path": str(path), "tables": tables, "error": None}
    except sqlite3.Error as exc:
        return {"present": True, "path": str(path), "tables": {}, "error": str(exc)}
