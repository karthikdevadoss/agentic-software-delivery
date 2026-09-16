#!/usr/bin/env python3
"""Content-idempotency check for claude-project-context/.

`generated_at` is a real wall-clock timestamp by design (see
docs/LESSONS.md) -- it, and every fast-changing section's `as of:`
marker (which embeds that same value), are EXPECTED to differ between
two regenerations even with zero source changes. A byte-for-byte diff
check would therefore always "fail" on a value that was never meant to
be stable, which is the wrong test.

The correct guarantee: regenerating from unchanged sources must not
change anything else. This script regenerates the bundle for real, then
compares before/after content with every generated_at-bearing line
stripped out first. Anything surviving that strip must be byte-identical,
or a real source/generator content change slipped in disguised as "just
the timestamp."

Usage: python agent/check_bundle_idempotency.py
Exit 0 = content-idempotent (nothing but generated_at-bearing lines
   differed, or nothing differed at all).
Exit 1 = a real content difference was found, or the generator itself
   failed.
"""
import difflib
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_DIR = REPO_ROOT / "claude-project-context"
SNAPSHOT_PATH = BUNDLE_DIR / "CONTEXT_SNAPSHOT.md"
MANIFEST_PATH = BUNDLE_DIR / "SOURCE_MANIFEST.yaml"
GENERATOR = REPO_ROOT / "agent" / "generate_claude_context_bundle.py"

# Exact prefixes of the lines this generator itself injects to carry
# generated_at (the bundle-level header line, each fast-changing
# section's `as of:` marker, and the manifest's own `generated_at:`
# field). Deliberately a precise startswith() match, NOT a substring
# search for the word "generated_at" anywhere in the file -- several
# canonical sources (docs/PROJECT_STATE.json's own narrative history,
# docs/LESSONS.md's lesson about this exact generator) legitimately
# mention that word as prose describing an unrelated system
# (learn-tree.json's own generated_at_utc field) or this fix itself.
# Excluding those lines from the comparison too would still never cause
# a false PASS, but it would silently weaken the check's ability to
# catch a real corruption in that prose -- so match narrowly instead.
VOLATILE_LINE_PREFIXES = (
    "**Bundle-level freshness header:**",
    "**as of:** `generated_at`",
    "generated_at:",  # SOURCE_MANIFEST.yaml's top-level field
)


def is_volatile(line: str) -> bool:
    stripped = line.strip()
    return any(stripped.startswith(prefix) for prefix in VOLATILE_LINE_PREFIXES)


def strip_volatile_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if not is_volatile(line)]


def volatile_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if is_volatile(line)]


def main() -> int:
    before_snapshot = SNAPSHOT_PATH.read_text(encoding="utf-8") if SNAPSHOT_PATH.exists() else ""
    before_manifest = MANIFEST_PATH.read_text(encoding="utf-8") if MANIFEST_PATH.exists() else ""

    result = subprocess.run(
        [sys.executable, str(GENERATOR)], cwd=REPO_ROOT, capture_output=True, text=True
    )
    if result.returncode != 0:
        print("check_bundle_idempotency: generator run FAILED:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return 1

    after_snapshot = SNAPSHOT_PATH.read_text(encoding="utf-8")
    after_manifest = MANIFEST_PATH.read_text(encoding="utf-8")

    problems = []
    volatile_count = 0
    for name, before, after in [
        ("CONTEXT_SNAPSHOT.md", before_snapshot, after_snapshot),
        ("SOURCE_MANIFEST.yaml", before_manifest, after_manifest),
    ]:
        volatile_count += len(volatile_lines(after))
        before_stripped = strip_volatile_lines(before)
        after_stripped = strip_volatile_lines(after)
        if before_stripped != after_stripped:
            problems.append(
                f"{name}: content differs after stripping the known volatile "
                "generated_at-bearing lines -- a REAL content change, not just a timestamp:"
            )
            diff = list(difflib.unified_diff(
                before_stripped, after_stripped,
                fromfile=f"{name} (before)", tofile=f"{name} (after)",
                lineterm="", n=1,
            ))
            problems.extend(f"    {d}" for d in diff[:40])

    if problems:
        print(f"check_bundle_idempotency: NOT content-idempotent -- {len(problems)} line(s) of evidence:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    print(
        "check_bundle_idempotency: OK -- regenerating from unchanged sources "
        f"left everything byte-identical except {volatile_count} known "
        "generated_at-bearing line(s) (expected: 1 bundle-level header line + "
        "1 manifest field + 1 per fast-changing section, across both files)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
