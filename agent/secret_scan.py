#!/usr/bin/env python3
"""Deterministic secret scan for this repository.

Scans all Git-tracked + staged text files for common credential patterns.
Never prints matched values -- only file:line and the pattern name that
matched. Mirrors karthik-ai-context/tools/secret_scan.py (kept in sync by
hand since the two repos can't share code across the public/private
boundary).

Exit code 0 = clean, 1 = findings (must be resolved before push).
"""
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PATTERNS = {
    "AWS Access Key ID": re.compile(r"AKIA[0-9A-Z]{16}"),
    "AWS Secret Key (heuristic)": re.compile(r"aws_secret_access_key\s*=\s*['\"][^'\"]{20,}['\"]", re.IGNORECASE),
    "Generic API key assignment": re.compile(r"(api[_-]?key|secret|token|password|passwd)\s*[:=]\s*['\"][A-Za-z0-9_\-/+=]{16,}['\"]", re.IGNORECASE),
    "Anthropic API key": re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}"),
    "OpenAI API key": re.compile(r"sk-[A-Za-z0-9]{32,}"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "Private key block": re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "Slack token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "JWT-looking string": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
}

ALLOWLIST_SUFFIXES = {".gitkeep", ".pyc"}
ALLOWLIST_PATHS = {"agent/secret_scan.py"}  # this file's own pattern strings


def list_repo_files() -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True, text=True, check=True,
    )
    return [REPO_ROOT / line for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    findings = []
    for path in list_repo_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        if path.suffix in ALLOWLIST_SUFFIXES or rel in ALLOWLIST_PATHS:
            continue
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for name, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(f"{rel}:{lineno}: possible {name}")

    if findings:
        print(f"secret_scan: {len(findings)} possible secret(s) found -- DO NOT PUSH until resolved:", file=sys.stderr)
        for f in findings:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print(f"secret_scan: OK ({len(list_repo_files())} files scanned, no matches)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
