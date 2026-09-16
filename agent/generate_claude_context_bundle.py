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
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_REPOSITORY_NAME = "agentic-software-delivery"

# The two repositories that together make up canonical context for this
# project (see claude-project-context/README.md). Only this repo's own
# files are read into THIS bundle's content -- the sibling's HEAD is
# recorded too, best-effort, purely as situational awareness for a prompt
# architect reading both bundles side by side. Resolved as a sibling
# checkout next to this repo; if it isn't present at generation time
# (e.g. a CI runner that only checked out this one repo), that is
# recorded honestly rather than guessed.
SIBLING_REPOS = {
    "agentic-software-delivery": REPO_ROOT,
    "karthik-ai-context": REPO_ROOT.parent / "karthik-ai-context",
}

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


def _git(*args: str, cwd: Path = REPO_ROOT) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _head_sha_for(repo_path: Path) -> str | None:
    if not (repo_path / ".git").exists():
        return None
    try:
        return _git("rev-parse", "HEAD", cwd=repo_path)
    except subprocess.CalledProcessError:
        return None


def git_provenance() -> dict:
    """Provenance for THIS repo's own content is tied to actual observed
    source-repo identity (HEAD SHA + its own commit timestamp +
    working-tree-dirty flag) -- that part stays deterministic: two runs
    against the same committed HEAD with no working-tree changes produce
    the same provenance block for those fields. `generated_at` is a
    separate, explicit wall-clock field requested for this bundle's
    freshness header; unlike the fields above it necessarily differs on
    every run, which reintroduces the "regeneration dirties the tree even
    with no substantive change" issue docs/LESSONS.md previously recorded
    and fixed by dropping wall-clock time entirely -- kept anyway here
    because it was explicitly requested; do not rely on it for
    idempotency checks, rely on the *_head_sha/source_files fields."""
    head_sha = _git("rev-parse", "HEAD")
    head_commit_time = _git("log", "-1", "--format=%cI", "HEAD")
    dirty = bool(_git("status", "--porcelain"))
    source_repo_head = {name: _head_sha_for(path) for name, path in SIBLING_REPOS.items()}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_repository": SOURCE_REPOSITORY_NAME,
        "source_repository_head_sha": head_sha,
        "source_repository_head_commit_time": head_commit_time,
        "source_working_tree_clean_at_generation": not dirty,
        "source_repo_head": source_repo_head,
    }


def resolve_sources() -> list[tuple[str, str]]:
    sources = list(FIXED_SOURCES)
    training_files = sorted(REPO_ROOT.glob(TRAINING_GLOB))
    for f in training_files:
        rel = f.relative_to(REPO_ROOT).as_posix()
        sources.append((rel, TRAINING_CLASSIFICATION))
    return sources


FAST_CHANGING_CLASSIFICATIONS = {"current", "historical"}


def render_source_section(rel_path: str, classification: str, content: str, digest: str, as_of_marker: str | None) -> str:
    is_json = Path(rel_path).suffix.lower() in JSON_EXTENSIONS
    lines = [
        f"## Source: `{rel_path}` ({classification})",
        "",
        f"sha256: `{digest}`",
        "",
    ]
    if as_of_marker:
        lines.append(as_of_marker)
        lines.append("")
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
    provenance = git_provenance()
    sources = resolve_sources()
    source_files = [rel for rel, _ in sources]

    missing = [rel for rel, _ in sources if not (REPO_ROOT / rel).exists()]
    if missing:
        print("generate_claude_context_bundle: ABORTED -- required canonical "
              "source(s) missing, refusing to generate a bundle that silently "
              "drops content:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        return 1

    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)

    repo_head_lines = "; ".join(
        f"`{name}` HEAD `{sha}`" if sha else f"`{name}` HEAD (not available at generation time)"
        for name, sha in provenance["source_repo_head"].items()
    )
    as_of_marker = (
        f"**as of:** `generated_at` `{provenance['generated_at']}`, "
        f"{repo_head_lines} -- same generation-time values as this "
        "bundle's header, not a separately fabricated timestamp. Treat as "
        "\"last recorded as of\" only, never as verified current truth."
    )

    dirty_note = (
        "" if provenance["source_working_tree_clean_at_generation"] else
        " **WARNING: the source working tree had uncommitted changes at "
        "generation time** -- some section content below may reflect "
        "changes newer than the HEAD commit named here."
    )
    snapshot_parts = [
        "# Claude Project Context Snapshot (agentic-software-delivery)",
        "",
        "**DERIVED VIEW -- not a new source of truth.** Generated by "
        f"`{GENERATOR_REL}` from the canonical files listed in "
        "`SOURCE_MANIFEST.yaml`, verbatim, with no summarization or "
        "invention. If this snapshot and a canonical source disagree, or "
        "`agent/validate_claude_context_bundle.py` reports the bundle "
        "STALE, the canonical source wins -- regenerate this file, never "
        "hand-edit it.",
        "",
        f"**Source state:** repository `{provenance['source_repository']}`, "
        f"HEAD `{provenance['source_repository_head_sha']}`, that commit "
        f"authored `{provenance['source_repository_head_commit_time']}`."
        f"{dirty_note} That commit-authored timestamp is the source "
        "repository's own commit timestamp, not this generator's run "
        "time -- prefer it as freshness evidence over `generated_at` "
        "below. **Bundle generation time is not fact observation time**: "
        "a fact below was true as of the source state named here, not "
        "necessarily as of whenever you are reading this.",
        "",
        f"**Bundle-level freshness header:** `generated_at` "
        f"`{provenance['generated_at']}` (UTC, this generator's actual "
        "run time -- unlike the commit timestamp above, this value "
        "differs on every run even with zero source changes, so it "
        "proves nothing about whether facts changed; kept only because "
        "a wall-clock generation timestamp was explicitly requested). "
        "`source_repo_head`: " + ", ".join(
            f"`{name}` = `{sha}`" if sha else f"`{name}` = not available at generation time"
            for name, sha in provenance["source_repo_head"].items()
        ) + f". `source_files`: {len(source_files)} paths, listed in "
        "`SOURCE_MANIFEST.yaml`'s `source_files` list and per-section "
        "below.",
        "",
        "## Freshness contract for a prompt architect reading this bundle",
        "",
        "Each source section below is labeled `(canonical)`, `(current)`, "
        "or `(historical)`:",
        "",
        "- **`(canonical)`** -- stable law/principles (architecture rules, "
        "engineering principles, model roles, resume/claim rules). May be "
        "stated normally as durable fact unless a live source says it was "
        "superseded.",
        "- **`(current)` or `(historical)`** -- fast-changing or point-in-"
        "time state (Git HEAD, CI/production status, blockers, action "
        "queue, run results). Each such section below carries its own "
        "**`as of:`** marker directly under its `sha256:` line, sourced "
        "from this same header's `generated_at`/`source_repo_head` "
        "values. State any fact from these sections only as \"last "
        "recorded as of\" that marker -- never as verified current truth. "
        "Never imply it was re-checked merely because this bundle was "
        "regenerated.",
        "- **If the task actually requires current engineering truth** "
        "(what's true right now in the real repo/CI/runtime/production/"
        "tests), this snapshot cannot substitute for that -- the resulting "
        "Claude Code task contract must require inspecting the real "
        "current source (actual Git repository, CI, runtime, production, "
        "deployment, or test/eval execution, as applicable) rather than "
        "trusting this snapshot.",
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
        section_as_of = as_of_marker if classification in FAST_CHANGING_CLASSIFICATIONS else None
        snapshot_parts.append(render_source_section(rel_path, classification, rendered_content, digest, section_as_of))
        manifest_entries.append((rel_path, digest, classification))

    SNAPSHOT_PATH.write_text("\n".join(snapshot_parts), encoding="utf-8")

    manifest_lines = [
        "# Auto-generated by agent/generate_claude_context_bundle.py -- do not hand-edit.",
        f"generator: {yaml_escape(GENERATOR_REL)}",
        "bundle_file: CONTEXT_SNAPSHOT.md",
        f"generated_at: {yaml_escape(provenance['generated_at'])}",
        f"source_repository: {yaml_escape(provenance['source_repository'])}",
        f"source_repository_head_sha: {yaml_escape(provenance['source_repository_head_sha'])}",
        f"source_repository_head_commit_time: {yaml_escape(provenance['source_repository_head_commit_time'])}",
        f"source_working_tree_clean_at_generation: {'true' if provenance['source_working_tree_clean_at_generation'] else 'false'}",
        "source_repo_head:",
    ]
    for name, sha in provenance["source_repo_head"].items():
        manifest_lines.append(f"  {name}: {yaml_escape(sha) if sha else 'null'}")
    manifest_lines.append("source_files:")
    for rel_path in source_files:
        manifest_lines.append(f"  - {yaml_escape(rel_path)}")
    manifest_lines.append("sources:")
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
