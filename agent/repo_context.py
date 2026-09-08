"""
Repository context collection for the ticket-to-implementation-plan agent (V2).

Scans the local Spring Boot repository for Java source structure and
project docs, and produces a compact, human-readable summary so Claude has
real, verifiable context about what already exists before proposing a plan.

Does not read target/, .git/, .env, or any build output — only Java source
under app/src/main/java and the two docs listed below.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JAVA_SRC_ROOT = REPO_ROOT / "app" / "src" / "main" / "java"
DOC_PATHS = [
    REPO_ROOT / "docs" / "ARCHITECTURE.md",
    REPO_ROOT / "docs" / "ENGINEERING_RULES.md",
]

MAX_DOC_CHARS = 4000

PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)
TYPE_RE = re.compile(r"\b(?:public\s+)?(?:class|interface)\s+(\w+)")
CLASS_DECL_RE = re.compile(r"\b(?:public\s+)?(?:class|interface)\s+\w+")
CLASS_REQUEST_MAPPING_RE = re.compile(r'@RequestMapping\((?:value\s*=\s*)?"([^"]*)"\)')
METHOD_MAPPING_RE = re.compile(
    r'@(Get|Post|Put|Patch|Delete)Mapping'
    r'(?:\((?:value\s*=\s*)?"?([^")]*)"?\))?'
)
EXTENDS_RE = re.compile(r"extends\s+([\w<>,\s]+?)\s*\{")
FIELD_RE = re.compile(r"^\s*private\s+[\w<>,\[\]\s]+?\s(\w+)\s*;", re.MULTILINE)
METHOD_RE = re.compile(r"^\s*public\s+[\w<>,\[\]\s]+?\s(\w+)\s*\([^)]*\)", re.MULTILINE)


def _classify(path: Path) -> str:
    parts = {p.lower() for p in path.parts}
    if "controller" in parts:
        return "controller"
    if "service" in parts:
        return "service"
    if "repository" in parts:
        return "repository"
    if "model" in parts:
        return "entity/model"
    return "other"


def _summarize_java_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(REPO_ROOT).as_posix()

    package_match = PACKAGE_RE.search(text)
    package = package_match.group(1) if package_match else "(no package declared)"

    type_match = TYPE_RE.search(text)
    type_name = type_match.group(1) if type_match else path.stem

    kind = _classify(path)
    lines = [f"- {package}.{type_name}  ({rel})  [{kind}]"]

    if kind == "controller":
        class_decl_match = CLASS_DECL_RE.search(text)
        header = text[: class_decl_match.start()] if class_decl_match else text
        base_path_match = CLASS_REQUEST_MAPPING_RE.search(header)
        base_path = base_path_match.group(1) if base_path_match else ""

        for verb, route in METHOD_MAPPING_RE.findall(text):
            if route:
                full_path = base_path.rstrip("/") + "/" + route.lstrip("/")
            else:
                full_path = base_path
            lines.append(f"    endpoint: {verb.upper()} {full_path or '/'}")
    elif kind == "repository":
        extends_match = EXTENDS_RE.search(text)
        if extends_match:
            lines.append(f"    extends: {extends_match.group(1).strip()}")
    elif kind == "entity/model":
        fields = FIELD_RE.findall(text)
        if fields:
            lines.append(f"    fields: {', '.join(fields)}")
    elif kind == "service":
        methods = [m for m in METHOD_RE.findall(text) if m != type_name]
        if methods:
            lines.append(f"    methods: {', '.join(methods)}")

    return "\n".join(lines)


def _collect_java_summaries() -> str:
    if not JAVA_SRC_ROOT.exists():
        return "(no Java source found under app/src/main/java — not found in repository context)"

    java_files = sorted(JAVA_SRC_ROOT.rglob("*.java"))
    if not java_files:
        return "(no .java files found — not found in repository context)"

    return "\n".join(_summarize_java_file(f) for f in java_files)


def _collect_docs() -> str:
    sections = []
    for doc_path in DOC_PATHS:
        rel = doc_path.relative_to(REPO_ROOT).as_posix()
        if not doc_path.exists():
            sections.append(f"--- {rel} ---\n(not found in repository context)")
            continue
        content = doc_path.read_text(encoding="utf-8").strip()
        if len(content) > MAX_DOC_CHARS:
            content = content[:MAX_DOC_CHARS] + "\n... (truncated)"
        sections.append(f"--- {rel} ---\n{content}")
    return "\n\n".join(sections)


def build_repository_context() -> str:
    """Build a compact, bounded text summary of the repository for the prompt."""
    java_summary = _collect_java_summaries()
    docs_summary = _collect_docs()

    return (
        "Java source structure (app/src/main/java):\n"
        f"{java_summary}\n\n"
        f"{docs_summary}"
    )
