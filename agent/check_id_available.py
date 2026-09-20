"""
Real, mechanical check for a real, already-happened incident: Sprint 4
had a genuine ID collision (two concurrent forks each independently
assigned "ACT-015" to two different, unrelated findings) because both
read the same sprint-start snapshot of docs/ACTION_QUEUE.json and neither
could see the other's concurrent assignment. External research (a real
study of 142k+ agent-authored PRs) independently recommends the same fix
this incident pointed to: reserve IDs before dispatch, don't let
concurrent agents mint their own.

This script is the PARENT session's tool, run once per new ID it's about
to hand to a fork in that fork's dispatch prompt -- not something a fork
runs on itself (a fork can't see a sibling fork's not-yet-committed
choice either way; the parent, dispatching sequentially even when work
runs in parallel, can).

Usage:
    python agent/check_id_available.py BL-036
    python agent/check_id_available.py ACT-017

Exits 0 and prints "AVAILABLE" if the ID is not already used in either
docs/BACKLOG.json or docs/ACTION_QUEUE.json; exits 1 and prints exactly
where it's already used otherwise.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKLOG_PATH = REPO_ROOT / "docs" / "BACKLOG.json"
ACTION_QUEUE_PATH = REPO_ROOT / "docs" / "ACTION_QUEUE.json"


def check(item_id: str) -> dict:
    item_id = item_id.upper()
    hits = []
    for path, key in [(BACKLOG_PATH, "BACKLOG.json"), (ACTION_QUEUE_PATH, "ACTION_QUEUE.json")]:
        data = json.loads(path.read_text(encoding="utf-8"))
        for it in data.get("items", []):
            if it.get("id", "").upper() == item_id:
                hits.append({"file": key, "title": it.get("title")})
    return {"id": item_id, "available": len(hits) == 0, "existing_uses": hits}


def next_free_id(prefix: str) -> str:
    """Real convenience: given a prefix like 'BL' or 'ACT', return
    max(existing)+1 -- deliberately never fills a numbering gap (an old
    id like ACT-003 may be gone from these two files but still referenced
    by number in old commit messages/docs; reusing it would be genuinely
    confusing later). Still just a suggestion, always verified with
    check() before being handed to a fork."""
    prefix = prefix.upper().rstrip("-")
    used = set()
    for path in (BACKLOG_PATH, ACTION_QUEUE_PATH):
        data = json.loads(path.read_text(encoding="utf-8"))
        for it in data.get("items", []):
            iid = it.get("id", "")
            if iid.upper().startswith(prefix + "-"):
                try:
                    used.add(int(iid.split("-", 1)[1]))
                except ValueError:
                    continue
    n = (max(used) + 1) if used else 1
    return f"{prefix}-{n:03d}"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python agent/check_id_available.py <BL-NNN|ACT-NNN>")
        print("       (or a bare prefix like 'BL' / 'ACT' to get the next free id)")
        sys.exit(2)

    arg = sys.argv[1]
    if "-" not in arg or not arg.split("-", 1)[1].isdigit():
        suggestion = next_free_id(arg)
        result = check(suggestion)
        result["suggested"] = suggestion
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["available"] else 1)

    result = check(arg)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["available"] else 1)
