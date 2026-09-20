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
import re
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


def _parse_midpoint(estimate_range: str | None) -> float | None:
    """'30-50 min' -> 40.0. Returns None if the field is missing or doesn't
    match this project's own consistent '<n>-<n> min' convention."""
    if not estimate_range:
        return None
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*min\s*$", estimate_range)
    if not m:
        return None
    lo, hi = float(m.group(1)), float(m.group(2))
    return (lo + hi) / 2.0


def suggest_estimate(size: str, confidence: str, pattern_type: str, raw_estimate_range: str | None = None) -> dict:
    """Real, computed reference-class lookup -- built 2026-09-20 as a
    direct response to a real, named root cause: four sprints of retro
    narrative never got mechanically fed back into how the NEXT estimate
    gets written. Filters docs/BACKLOG.json's own history to items
    matching (size, confidence, pattern_type) with a real numeric
    estimate_range and actual_ratio, EXCLUDING anything flagged
    contaminated=true (a duplicate, an agent-stall takeover, a superseded
    investigation -- see each item's own contamination_reason).

    Returns an honest shape, never a fabricated number: n=0 or n<3 comes
    back as INSUFFICIENT_HISTORY with the raw rubric-derived guidance
    still available to fall back on -- this function never invents
    precision a thin sample can't support."""
    data = load_backlog()
    matches = []
    for it in data["items"]:
        if it.get("size") != size:
            continue
        if it.get("confidence") != confidence:
            continue
        if it.get("pattern_type") != pattern_type:
            continue
        if it.get("contaminated"):
            continue
        ratio = it.get("actual_ratio")
        if ratio is None:
            continue
        matches.append({"id": it["id"], "ratio": ratio})

    n = len(matches)
    base = {
        "size": size, "confidence": confidence, "pattern_type": pattern_type,
        "raw_estimate_range": raw_estimate_range,
    }
    if n == 0:
        return {
            **base, "status": "INSUFFICIENT_HISTORY", "n": 0,
            "reason": "no non-contaminated historical items match this exact "
                      "(size, confidence, pattern_type) combination yet",
            "fallback": "use the raw rubric-derived range unadjusted",
        }

    ratios = sorted(m["ratio"] for m in matches)
    mid = len(ratios) // 2
    median_ratio = ratios[mid] if len(ratios) % 2 else (ratios[mid - 1] + ratios[mid]) / 2.0

    result = {
        **base,
        "status": "INSUFFICIENT_HISTORY" if n < 3 else "COMPUTED",
        "n": n,
        "median_ratio": round(median_ratio, 3),
        "ratio_range": [round(min(ratios), 3), round(max(ratios), 3)],
        "matched_items": [m["id"] for m in matches],
    }
    if n < 3:
        result["reason"] = f"only {n} non-contaminated historical match(es) -- too thin to trust a computed number over the raw rubric band"
        result["fallback"] = "use the raw rubric-derived range unadjusted"

    raw_mid = _parse_midpoint(raw_estimate_range)
    if raw_mid is not None:
        result["raw_midpoint_min"] = raw_mid
        result["suggested_midpoint_min"] = round(raw_mid * median_ratio, 1)
        if n < 3:
            result["suggested_midpoint_note"] = "low-confidence suggestion (n<3) -- weigh against the raw range, don't substitute it blindly"
    return result


def record_deviation(item_id: str, suggestion: dict, chosen_midpoint_min: float, reason: str) -> None:
    """Real, honest accountability for overriding a COMPUTED suggestion --
    built 2026-09-20 after the first real use of suggest_estimate()
    produced a COMPUTED suggestion of 4.0 min, was overridden upward to a
    15-20 min estimate on a plausible-sounding risk argument, and the real
    actual time (~3 min) landed almost exactly on the ORIGINAL computed
    suggestion, not the override. One data point proves nothing on its
    own; this records every such deviation on the item itself so a future
    retro can compute, from real data across many sprints, whether
    deviating from a COMPUTED suggestion is ever net-positive -- rather
    than trusting either 'always follow the tool' or 'my judgment is
    fine' without evidence either way."""
    data = load_backlog()
    item = next((i for i in data["items"] if i["id"] == item_id), None)
    if item is None:
        raise ValueError(f"no such item: {item_id}")
    item["deviated_from_suggestion"] = True
    item["deviation"] = {
        "suggestion_status": suggestion.get("status"),
        "suggested_midpoint_min": suggestion.get("suggested_midpoint_min"),
        "chosen_midpoint_min": chosen_midpoint_min,
        "reason": reason,
    }
    save_backlog(data)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "suggest-estimate":
        if len(sys.argv) not in (5, 6):
            print("usage: python agent/backlog.py suggest-estimate <SIZE> <CONFIDENCE> <PATTERN_TYPE> [<RAW_RANGE eg '30-50 min'>]")
            print("  PATTERN_TYPE: apply_known_pattern | first_of_kind | investigation_only | verification_only | research")
            sys.exit(2)
        raw_range = sys.argv[5] if len(sys.argv) == 6 else None
        print(json.dumps(suggest_estimate(sys.argv[2], sys.argv[3], sys.argv[4], raw_range), indent=2))
    elif len(sys.argv) > 1:
        print(json.dumps(size_vs_actual(sys.argv[1]), indent=2))
    else:
        data = load_backlog()
        for item in data["items"]:
            print(f"{item['id']} [{item['size']}] {item['status']}: {item['title']}")
