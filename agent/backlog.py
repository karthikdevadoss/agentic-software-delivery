"""
Phase 1 of the AI-Scrum-Master system (2026-09-18 overnight design
conversation -- see docs/BACKLOG.json and docs/interview-scenarios/ for
the full rationale). Deliberately lean: reads/writes the backlog JSON
file and compares a sized item's real cost/time against its size, for
MANUAL review. No scheduled retro subagent yet -- that is a later,
separate phase, built only once this simple version proves it adds real
value (the Owner's own explicit instruction, to avoid the measurement
system itself becoming the waste it exists to prevent).

Never a second, divergent cost calculation: reuses
session_history._usage_for_claude_code() for the real per-session token/
cost totals, the exact same function every other real Claude-Code-dev-
session cost figure in this project already goes through.
"""

import json
from pathlib import Path

BACKLOG_PATH = Path(__file__).resolve().parent.parent / "docs" / "BACKLOG.json"


def load_backlog() -> dict:
    return json.loads(BACKLOG_PATH.read_text(encoding="utf-8"))


def save_backlog(data: dict) -> None:
    BACKLOG_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def get_item(item_id: str) -> dict | None:
    data = load_backlog()
    return next((i for i in data["items"] if i["id"] == item_id), None)


def size_vs_actual(item_id: str) -> dict:
    """Compares one backlog item's recorded size against its real cost/
    tokens/wall-clock time, pulled from the event ledger via its
    session_ids. Returns an honest shape: a session_id with no captured
    usage (e.g. work still in progress, or predates capture) is reported
    as NOT_CAPTURED, never silently treated as zero cost."""
    item = get_item(item_id)
    if item is None:
        return {"status": "NOT_FOUND", "item_id": item_id}

    session_ids = item.get("session_ids") or []
    if not session_ids:
        return {
            "status": "NO_SESSIONS_LINKED",
            "item_id": item_id, "title": item["title"], "size": item["size"],
        }

    import event_ledger as el
    import session_history as sh

    conn = el._connect()
    try:
        el.ensure_schema()
        usage_by_session = sh._usage_for_claude_code(conn, session_ids)
    finally:
        conn.close()

    total_input = total_output = total_cache_read = total_cache_write = 0
    total_cost_usd = 0.0
    cost_known = True
    sessions_with_usage = 0
    for sid in session_ids:
        usage = usage_by_session.get(sid)
        if not usage:
            continue
        sessions_with_usage += 1
        total_input += usage["input_tokens"] or 0
        total_output += usage["output_tokens"] or 0
        total_cache_read += usage["cache_read_tokens"] or 0
        total_cache_write += usage["cache_write_tokens"] or 0
        if usage["cost"].get("available"):
            total_cost_usd += usage["cost"]["total_usd"]
        else:
            cost_known = False

    if sessions_with_usage == 0:
        return {
            "status": "NOT_CAPTURED",
            "item_id": item_id, "title": item["title"], "size": item["size"],
            "reason": "no linked session has a captured model_usage record yet -- work may still be in progress, or predates cost capture",
        }

    return {
        "status": "REACHABLE",
        "item_id": item_id, "title": item["title"], "size": item["size"],
        "size_rationale": item.get("size_rationale"),
        "sessions_total": len(session_ids), "sessions_with_captured_usage": sessions_with_usage,
        "tokens": {
            "input_tokens": total_input, "output_tokens": total_output,
            "cache_read_tokens": total_cache_read, "cache_write_tokens": total_cache_write,
        },
        "cost_usd": round(total_cost_usd, 6) if cost_known else None,
        "cost_known_for_all_linked_sessions": cost_known,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(json.dumps(size_vs_actual(sys.argv[1]), indent=2))
    else:
        data = load_backlog()
        for item in data["items"]:
            print(f"{item['id']} [{item['size']}] {item['status']}: {item['title']}")
