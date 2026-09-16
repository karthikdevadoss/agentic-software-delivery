#!/usr/bin/env python3
"""Deterministic validation for claude-project-context/.

No LLM involved. Fails (exit 1) if:
  1. A canonical source listed in SOURCE_MANIFEST.yaml no longer exists.
  2. Any canonical source's current sha256 no longer matches the manifest
     (the bundle is STALE -- someone edited a source without regenerating).
  3. CONTEXT_SNAPSHOT.md contains a phrase that belongs only in the
     private karthik-ai-context repo (private-content leak into public).

Usage: python agent/validate_claude_context_bundle.py
"""
import hashlib
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_DIR = REPO_ROOT / "claude-project-context"
SNAPSHOT_PATH = BUNDLE_DIR / "CONTEXT_SNAPSHOT.md"
MANIFEST_PATH = BUNDLE_DIR / "SOURCE_MANIFEST.yaml"

# Same private-only categories as karthik-ai-context/tools/leakage_check.py --
# kept in sync by hand since the two repos can't share code across the
# public/private boundary.
SECRET_SHAPE_PATTERNS = {
    "AWS Access Key ID": re.compile(r"AKIA[0-9A-Z]{16}"),
    "Anthropic API key": re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}"),
    "OpenAI API key": re.compile(r"sk-[A-Za-z0-9]{32,}"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "Private key block": re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "Slack token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "JWT-looking string": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
}

PRIVATE_ONLY_PATTERNS = {
    "salary figure": re.compile(r"€\s?\d|EUR\s?\d|\$\d{2,}k|net/month", re.IGNORECASE),
    "visa/work-authorization detail": re.compile(r"h-?1b|221\(g\)|permanent residence|work permit|visa interview", re.IGNORECASE),
    "recruiter/interview detail": re.compile(r"recruiter feedback|interview feedback|offer letter", re.IGNORECASE),
    "employment vendor chain": re.compile(r"tekdoors|futuremindz|remote gmbh", re.IGNORECASE),
    "raw chat reference": re.compile(r"chatgpt.?export|conversations\.json|chat\.html", re.IGNORECASE),
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_manifest(text: str) -> list[dict]:
    """Hand-rolled parser for the flat YAML this generator writes -- no
    PyYAML dependency. Only understands the exact shape
    generate_claude_context_bundle.py produces."""
    entries = []
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- path:"):
            if current:
                entries.append(current)
            current = {"path": _unquote(stripped.split(":", 1)[1].strip())}
        elif stripped.startswith("sha256:") and current is not None:
            current["sha256"] = _unquote(stripped.split(":", 1)[1].strip())
        elif stripped.startswith("classification:") and current is not None:
            current["classification"] = stripped.split(":", 1)[1].strip()
    if current:
        entries.append(current)
    return entries


def _unquote(value: str) -> str:
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def main() -> int:
    problems = []

    if not MANIFEST_PATH.exists():
        print("validate_claude_context_bundle: MANIFEST missing -- run "
              "agent/generate_claude_context_bundle.py first", file=sys.stderr)
        return 1
    if not SNAPSHOT_PATH.exists():
        print("validate_claude_context_bundle: SNAPSHOT missing -- run "
              "agent/generate_claude_context_bundle.py first", file=sys.stderr)
        return 1

    entries = parse_manifest(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not entries:
        problems.append("manifest parsed to zero source entries -- parser or generator broken")

    for entry in entries:
        rel_path = entry.get("path")
        recorded_hash = entry.get("sha256")
        full_path = REPO_ROOT / rel_path if rel_path else None

        if not full_path or not full_path.exists():
            problems.append(f"required canonical source disappeared: {rel_path}")
            continue

        current_hash = sha256_text(full_path.read_text(encoding="utf-8"))
        if current_hash != recorded_hash:
            problems.append(
                f"STALE: {rel_path} changed since the bundle was generated "
                f"(manifest sha256 {recorded_hash[:12]}... != current {current_hash[:12]}...)"
            )

    snapshot_text = SNAPSHOT_PATH.read_text(encoding="utf-8", errors="ignore")
    for name, pattern in PRIVATE_ONLY_PATTERNS.items():
        for lineno, line in enumerate(snapshot_text.splitlines(), 1):
            if pattern.search(line):
                problems.append(f"possible private-content leak into public bundle ({name}) at CONTEXT_SNAPSHOT.md:{lineno}")

    for name, pattern in SECRET_SHAPE_PATTERNS.items():
        for lineno, line in enumerate(snapshot_text.splitlines(), 1):
            if pattern.search(line):
                problems.append(f"secret-shaped string in bundle ({name}) at CONTEXT_SNAPSHOT.md:{lineno} -- generator's redaction step should have caught this, do not push")

    if problems:
        print(f"validate_claude_context_bundle: {len(problems)} problem(s):", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print(f"validate_claude_context_bundle: OK ({len(entries)} sources checked, "
          "not stale, no private-content leakage detected)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
