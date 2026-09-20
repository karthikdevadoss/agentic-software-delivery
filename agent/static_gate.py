"""
STATIC verification tier (BL-018, 2026-09-20) -- Testing & Verification
Architecture V1's first real inhabitant of the previously-empty STATIC
tier (docs/TESTING_ARCHITECTURE_V1.md SS G). Zero-LLM, deterministic,
no model involved: real file-mode/shebang checks via `git ls-files -s`.

Real defect class this closes: a file's Unix executable bit silently
lost when copying files on Windows (mode 100644 instead of 100755) is
invisible on this Windows dev machine and only surfaces as a real CI
"Permission denied" failure (exit 126) -- see docs/LESSONS.md and
docs/AI_NATIVE_TESTING_RESEARCH.md finding 3c. This gate catches it
locally, deterministically, before it ever reaches CI.

Rule (CLAUDE.md's "AI-characteristic defect discipline"): every file with
a real `#!` shebang, or any file under scripts/, must be git mode 100755.

Usage:
    python agent/static_gate.py        # check the whole real repo
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Cheap, real candidate filters -- avoids reading every tracked file's
# content (slow across a whole repo); covers the real, known cases in
# this repo (mvnw scripts, anything under scripts/, any .sh file)
# without needing a full byte-by-byte shebang scan of everything.
_CANDIDATE_NAME_PATTERNS = ("mvnw",)
_CANDIDATE_SUFFIXES = (".sh",)
_CANDIDATE_DIR_PREFIXES = ("scripts/",)


def _list_tracked_with_mode() -> list[tuple[str, str]]:
    """Real (mode, path) pairs for every git-tracked file, via
    `git ls-files -s` -- never estimated, never assumed."""
    proc = subprocess.run(
        ["git", "ls-files", "-s"], cwd=str(REPO_ROOT),
        capture_output=True, text=True, check=True,
    )
    pairs = []
    for line in proc.stdout.splitlines():
        # Format: "<mode> <sha> <stage>\t<path>"
        meta, path = line.split("\t", 1)
        mode = meta.split()[0]
        pairs.append((mode, path))
    return pairs


def _is_candidate(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    if name in _CANDIDATE_NAME_PATTERNS:
        return True
    if any(path.endswith(suf) for suf in _CANDIDATE_SUFFIXES):
        return True
    if any(path.startswith(pfx) for pfx in _CANDIDATE_DIR_PREFIXES):
        return True
    return False


def _has_real_shebang(path: str) -> bool:
    full = REPO_ROOT / path
    if not full.is_file():
        return False
    try:
        with open(full, "rb") as f:
            head = f.read(2)
        return head == b"#!"
    except OSError:
        return False


def check() -> list[dict]:
    """Returns a list of real violations: candidate files that are
    scripts (shebang or under scripts/) but are NOT git mode 100755.
    Empty list means the gate passes. Never raises for a clean repo."""
    violations = []
    for mode, path in _list_tracked_with_mode():
        if not _is_candidate(path):
            continue
        name = path.rsplit("/", 1)[-1]
        is_script = (
            name in _CANDIDATE_NAME_PATTERNS
            or any(path.endswith(suf) for suf in _CANDIDATE_SUFFIXES)
            or _has_real_shebang(path)
        )
        if is_script and mode != "100755":
            violations.append({"path": path, "mode": mode, "expected_mode": "100755"})
    return violations


def main():
    violations = check()
    if not violations:
        print("STATIC gate (file-mode/shebang): PASS -- no violations found.")
        sys.exit(0)

    print(f"STATIC gate (file-mode/shebang): FAIL -- {len(violations)} violation(s):")
    for v in violations:
        print(f"  {v['path']}: mode={v['mode']} (expected {v['expected_mode']})")
    print("\nFix with: git update-index --chmod=+x <path>")
    sys.exit(1)


if __name__ == "__main__":
    main()
