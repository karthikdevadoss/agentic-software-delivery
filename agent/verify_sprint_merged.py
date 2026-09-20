"""
Real, mechanical gate: before a sprint's merge phase is considered done,
check that every worktree branch dispatched this sprint is ACTUALLY an
ancestor of master -- not "a task-tracker says it's completed," which is
not the same claim and was the real cause of a real bug (Sprint 4: two
branches were fully finished inside their worktrees and marked done in
BACKLOG.json, but the parent session never actually ran `git merge` for
them -- caught only by accident during an unrelated audit).

Usage:
    python agent/verify_sprint_merged.py worktree-agent-abc worktree-agent-def ...
    python agent/verify_sprint_merged.py --branches-file branches.txt

Exits 0 only if every named branch is a real ancestor of the current
branch (HEAD, normally master). Exits 1 and prints exactly which
branch(es) are NOT merged otherwise -- never silently "probably fine."
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True)


def branch_exists(branch: str) -> bool:
    result = _run(["git", "rev-parse", "--verify", "--quiet", branch])
    return result.returncode == 0


def is_merged(branch: str, into: str = "HEAD") -> bool:
    """True only if `branch` is a real ancestor of `into` -- computed via
    git's own merge-base check, never inferred from a task tracker."""
    result = _run(["git", "merge-base", "--is-ancestor", branch, into])
    return result.returncode == 0


def verify(branches: list[str]) -> dict:
    results = []
    for b in branches:
        if not branch_exists(b):
            results.append({"branch": b, "status": "NO_SUCH_BRANCH"})
            continue
        merged = is_merged(b)
        results.append({"branch": b, "status": "MERGED" if merged else "NOT_MERGED"})

    unmerged = [r["branch"] for r in results if r["status"] != "MERGED"]
    return {
        "all_merged": len(unmerged) == 0,
        "checked": len(branches),
        "results": results,
        "unmerged_or_missing": unmerged,
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("usage: python agent/verify_sprint_merged.py <branch1> [branch2 ...]")
        print("       python agent/verify_sprint_merged.py --branches-file <path>")
        sys.exit(2)

    if args[0] == "--branches-file":
        if len(args) != 2:
            print("usage: python agent/verify_sprint_merged.py --branches-file <path>")
            sys.exit(2)
        branches = [
            line.strip() for line in Path(args[1]).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    else:
        branches = args

    import json
    report = verify(branches)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["all_merged"] else 1)
