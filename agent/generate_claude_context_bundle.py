#!/usr/bin/env python3
"""Deterministically regenerate claude-project-context/ from canonical docs.

No LLM involved -- this is pure concatenation + hashing + a hand-written
YAML manifest, so the output is byte-reproducible from the same source
files. The bundle is a DERIVED VIEW: canonical files listed in
SOURCE_MANIFEST.yaml always outrank it. Run after any canonical source in
SOURCES changes, then re-run validate_claude_context_bundle.py.

Usage: python agent/generate_claude_context_bundle.py
"""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Secret-shaped substrings must never be copied into the derived bundle,
# real or fake -- GitHub's push protection (correctly) can't tell a
# genuine credential from a test-fixture string of the same shape, and
# neither can a human skimming a diff. Same patterns as
# agent/secret_scan.py; redaction here is substring-level (not a whole-
# line failure) so the surrounding real content stays verbatim. See
# docs/PROJECT_STATE.json's own recorded lesson about exactly this shape
# of false positive (a fake AWS-Access-Key-ID-shaped test-fixture string).
SECRET_SHAPE_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{32,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
]


def redact_secret_shapes(text: str) -> tuple[str, int]:
    count = 0

    def _replace(match: re.Match) -> str:
        nonlocal count
        count += 1
        return f"[REDACTED-SECRET-SHAPED-STRING-{len(match.group(0))}-CHARS -- see source file directly]"

    for pattern in SECRET_SHAPE_PATTERNS:
        text = pattern.sub(_replace, text)
    return text, count
BUNDLE_DIR = REPO_ROOT / "claude-project-context"
SNAPSHOT_PATH = BUNDLE_DIR / "CONTEXT_SNAPSHOT.md"
MANIFEST_PATH = BUNDLE_DIR / "SOURCE_MANIFEST.yaml"
GENERATOR_REL = "agent/generate_claude_context_bundle.py"

# (path relative to repo root, classification) -- classification is
# canonical (stable law/principles), current (changes frequently, trust
# the live file over this snapshot), or historical (append-only log).
FIXED_SOURCES = [
    ("START_HERE.md", "canonical"),
    ("CLAUDE.md", "canonical"),
    ("docs/context/PROJECT_CONTEXT_INDEX.md", "canonical"),
    ("docs/context/PROJECT_PURPOSE_AND_GOALS.md", "canonical"),
    ("docs/context/OWNER_ENGINEERING_PRINCIPLES.md", "canonical"),
    ("docs/context/MODEL_COLLABORATION_PROTOCOL.md", "canonical"),
    ("docs/context/CURRENT_ENGINEERING_CONTEXT.md", "current"),
    ("docs/CONSTITUTION.md", "canonical"),
    ("docs/PROJECT_STATE.json", "current"),
    ("docs/ACTION_QUEUE.json", "current"),
    ("docs/DECISIONS.md", "historical"),
    ("docs/LESSONS.md", "historical"),
    ("docs/ARCHITECTURE_V3_DECISIONS.md", "canonical"),
    ("docs/DETERMINISTIC_ENGINEERING_KERNEL.md", "canonical"),
    ("docs/DETERMINISTIC_VS_LLM_DECISIONS.md", "canonical"),
    ("docs/INTELLIGENCE_PLACEMENT_V3.md", "canonical"),
    ("docs/EVIDENCE_AUTHORITY_MODEL.md", "canonical"),
    ("docs/INVARIANT_REGISTRY.md", "canonical"),
    ("docs/CAPABILITY_SECURITY_MODEL.md", "canonical"),
    ("docs/TESTING_ARCHITECTURE_V2.md", "canonical"),
    ("docs/EXPERIENCE_EVIDENCE.md", "current"),
    ("docs/AI_COLLABORATION.md", "canonical"),
    (".claude/skills/testing-strategy/SKILL.md", "canonical"),
]

# docs/training/* is a directory whose membership changes -- expand it
# deterministically (sorted) at generation time instead of hardcoding files.
TRAINING_GLOB = "docs/training/*.md"
TRAINING_CLASSIFICATION = "historical"

JSON_EXTENSIONS = {".json"}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def resolve_sources() -> list[tuple[str, str]]:
    sources = list(FIXED_SOURCES)
    training_files = sorted(REPO_ROOT.glob(TRAINING_GLOB))
    for f in training_files:
        rel = f.relative_to(REPO_ROOT).as_posix()
        sources.append((rel, TRAINING_CLASSIFICATION))
    return sources


def render_source_section(rel_path: str, classification: str, content: str, digest: str) -> str:
    is_json = Path(rel_path).suffix.lower() in JSON_EXTENSIONS
    lines = [
        f"## Source: `{rel_path}` ({classification})",
        "",
        f"sha256: `{digest}`",
        "",
    ]
    if is_json:
        lines.append("```json")
        lines.append(content.rstrip("\n"))
        lines.append("```")
    else:
        lines.append(content.rstrip("\n"))
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def yaml_escape(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> int:
    generated_at = datetime.now(timezone.utc).isoformat()
    sources = resolve_sources()

    missing = [rel for rel, _ in sources if not (REPO_ROOT / rel).exists()]
    if missing:
        print("generate_claude_context_bundle: ABORTED -- required canonical "
              "source(s) missing, refusing to generate a bundle that silently "
              "drops content:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        return 1

    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)

    snapshot_parts = [
        "# Claude Project Context Snapshot (agentic-software-delivery)",
        "",
        "**DERIVED VIEW -- not a new source of truth.** Generated by "
        f"`{GENERATOR_REL}` at {generated_at} from the canonical files "
        "listed in `SOURCE_MANIFEST.yaml`, verbatim, with no summarization "
        "or invention. If this snapshot and a canonical source disagree, "
        "or `agent/validate_claude_context_bundle.py` reports the bundle "
        "STALE, the canonical source wins -- regenerate this file, never "
        "hand-edit it.",
        "",
        "Model memory is not authoritative over this snapshot, and this "
        "snapshot is not authoritative over the canonical sources it was "
        "built from. See `README.md` in this directory for the full "
        "precedence statement.",
        "",
        "---",
        "",
    ]

    manifest_entries = []
    total_redactions = 0
    for rel_path, classification in sources:
        full_path = REPO_ROOT / rel_path
        content = full_path.read_text(encoding="utf-8")
        digest = sha256_text(content)  # hash of the REAL source, for staleness checks
        rendered_content, n_redacted = redact_secret_shapes(content)
        if n_redacted:
            total_redactions += n_redacted
            print(f"generate_claude_context_bundle: redacted {n_redacted} "
                  f"secret-shaped substring(s) from {rel_path} in the bundle "
                  "(source file left untouched)", file=sys.stderr)
        snapshot_parts.append(render_source_section(rel_path, classification, rendered_content, digest))
        manifest_entries.append((rel_path, digest, classification))

    SNAPSHOT_PATH.write_text("\n".join(snapshot_parts), encoding="utf-8")

    manifest_lines = [
        "# Auto-generated by agent/generate_claude_context_bundle.py -- do not hand-edit.",
        f"generated_at: {yaml_escape(generated_at)}",
        f"generator: {yaml_escape(GENERATOR_REL)}",
        "bundle_file: CONTEXT_SNAPSHOT.md",
        "sources:",
    ]
    for rel_path, digest, classification in manifest_entries:
        manifest_lines.append(f"  - path: {yaml_escape(rel_path)}")
        manifest_lines.append(f"    sha256: {yaml_escape(digest)}")
        manifest_lines.append(f"    classification: {classification}")
    MANIFEST_PATH.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    print(f"generate_claude_context_bundle: OK -- {len(manifest_entries)} sources, "
          f"snapshot {SNAPSHOT_PATH.stat().st_size} bytes"
          + (f", {total_redactions} secret-shaped substring(s) redacted" if total_redactions else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
