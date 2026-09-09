"""
Read-only repository tools for the V3 tool-using planning agent.

Every tool is a plain function with primitive input/output so the exact
same logic can later be reused unchanged behind an MCP server. Nothing
here executes shell commands, writes files, follows symlinks, or touches
Git — this module is read-only and repository-bounded by construction.
"""

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

BLOCKED_DIR_NAMES = {".git", "target", ".mvn", "node_modules", "__pycache__", "venv", ".venv"}

BLOCKED_FILENAME_PATTERNS = (
    re.compile(r"^\.env(\..*)?$", re.IGNORECASE),
    re.compile(r".*secret.*", re.IGNORECASE),
    re.compile(r".*credential.*", re.IGNORECASE),
    re.compile(r"^id_rsa$|^id_dsa$|^id_ecdsa$|^id_ed25519$", re.IGNORECASE),
)

BLOCKED_EXTENSIONS = {
    ".env", ".jar", ".class", ".key", ".pem", ".p12", ".pfx", ".jks", ".keystore",
}

ALLOWED_READ_EXTENSIONS = {
    ".java", ".xml", ".properties", ".md", ".txt", ".html", ".json", ".yml", ".yaml",
}

MAX_FILES_LISTED = 200
MAX_FILE_BYTES = 20_000
MAX_SEARCH_RESULTS = 50
MAX_SEARCH_LINE_CHARS = 200


class RepoToolError(Exception):
    """Raised for any safely-reportable tool failure. Never lets a tool crash the app."""


# --- lightweight, deterministic secret redaction -----------------------
# Not an exhaustive scanner — a small, predictable safety net so obvious
# credential-shaped values never reach Claude or a log line, even from
# files we are otherwise allowed to read (.properties/.yml/.json/.xml).

_SECRET_LITERAL_PATTERNS = (
    re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),  # JWT-like
)

_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r'(?i)\b(api[_-]?key|apikey|secret|password|passwd|access[_-]?key|'
    r'private[_-]?key|token)\b(\s*[:=]\s*)["\']?([A-Za-z0-9_\-./+=]{6,})["\']?'
)


def redact_secrets(text: str) -> str:
    """Mask obvious credential-shaped values before they leave this module."""
    redacted = text
    for pattern in _SECRET_LITERAL_PATTERNS:
        redacted = pattern.sub("***REDACTED***", redacted)
    redacted = _SECRET_ASSIGNMENT_PATTERN.sub(r"\1\2***REDACTED***", redacted)
    return redacted


def _is_blocked_name(name: str) -> bool:
    return any(pattern.match(name) for pattern in BLOCKED_FILENAME_PATTERNS)


def _resolve_safe_path(user_path: str) -> Path:
    raw = user_path if user_path not in (None, "") else "."

    if ".." in Path(raw).parts:
        raise RepoToolError(f"path traversal is not allowed: {raw!r}")
    if Path(raw).is_absolute():
        raise RepoToolError(f"absolute paths are not allowed: {raw!r}")

    joined = REPO_ROOT / raw
    lexical = Path(os.path.normpath(str(joined)))
    resolved = joined.resolve()

    if resolved != lexical:
        # Something along the path was a symlink and changed where it
        # actually points. Reject unconditionally rather than following it.
        raise RepoToolError(f"symlinks are not allowed: {raw!r}")

    try:
        rel_parts = resolved.relative_to(REPO_ROOT).parts
    except ValueError:
        raise RepoToolError(f"path resolves outside the repository: {raw!r}")

    if any(part in BLOCKED_DIR_NAMES for part in rel_parts):
        raise RepoToolError(f"path is inside a blocked directory: {raw!r}")

    # Checked regardless of whether the file exists yet: for reads this is
    # equivalent (a nonexistent file can't be read either way), but for
    # writes it matters — a secret-named file that doesn't exist YET must
    # still be blocked, not silently allowed because "it's not a file".
    if _is_blocked_name(resolved.name):
        raise RepoToolError(f"file is blocked for safety: {raw!r}")
    if resolved.suffix.lower() in BLOCKED_EXTENSIONS:
        raise RepoToolError(f"file type is blocked for safety: {raw!r}")

    return resolved


def list_repository_files(directory: str = ".") -> str:
    base = _resolve_safe_path(directory)

    if not base.exists():
        raise RepoToolError(f"directory not found: {directory!r}")
    if not base.is_dir():
        raise RepoToolError(f"not a directory: {directory!r}")

    entries = []
    for root, dirs, files in os.walk(base, followlinks=False):
        root_path = Path(root)
        dirs[:] = [
            d for d in dirs
            if d not in BLOCKED_DIR_NAMES and not (root_path / d).is_symlink()
        ]
        for name in files:
            if _is_blocked_name(name):
                continue
            file_path = root_path / name
            if file_path.is_symlink():
                continue
            entries.append(file_path.relative_to(REPO_ROOT).as_posix())

    entries.sort()
    if not entries:
        return "(no files found)"

    total = len(entries)
    shown = entries[:MAX_FILES_LISTED]
    result = "\n".join(shown)
    if total > MAX_FILES_LISTED:
        result += f"\n... ({total - MAX_FILES_LISTED} more omitted)"
    return result


def read_file(path: str) -> str:
    if not path:
        raise RepoToolError("path is required")

    resolved = _resolve_safe_path(path)

    if not resolved.exists():
        raise RepoToolError(f"file not found: {path!r}")
    if not resolved.is_file():
        raise RepoToolError(f"not a file: {path!r}")
    if resolved.suffix.lower() not in ALLOWED_READ_EXTENSIONS:
        raise RepoToolError(f"file type not allowed for reading: {path!r}")

    raw_bytes = resolved.read_bytes()
    truncated = len(raw_bytes) > MAX_FILE_BYTES
    raw_bytes = raw_bytes[:MAX_FILE_BYTES]

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise RepoToolError(f"file is not valid UTF-8 text: {path!r}")

    text = redact_secrets(text)
    rel = resolved.relative_to(REPO_ROOT).as_posix()
    header = f"--- {rel} ---\n"

    if truncated:
        return header + text + "\n... (truncated)"
    return header + text


def search_code(query: str, glob: str = "**/*.java") -> str:
    if not query:
        raise RepoToolError("query is required")
    if len(query) < 2:
        raise RepoToolError("query is too short")
    if ".." in glob or Path(glob).is_absolute():
        raise RepoToolError(f"glob is not allowed: {glob!r}")

    query_lower = query.lower()
    matches = []

    for path in sorted(REPO_ROOT.glob(glob)):
        if not path.is_file() or path.is_symlink():
            continue
        rel_parts = path.relative_to(REPO_ROOT).parts
        if any(part in BLOCKED_DIR_NAMES for part in rel_parts):
            continue
        if _is_blocked_name(path.name):
            continue
        if path.suffix.lower() not in ALLOWED_READ_EXTENSIONS:
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        rel = path.relative_to(REPO_ROOT).as_posix()
        for line_no, line in enumerate(text.splitlines(), start=1):
            if query_lower in line.lower():
                snippet = line.strip()[:MAX_SEARCH_LINE_CHARS]
                matches.append(f"{rel}:{line_no}: {snippet}")
                if len(matches) >= MAX_SEARCH_RESULTS:
                    break
        if len(matches) >= MAX_SEARCH_RESULTS:
            break

    if not matches:
        return "(no matches found)"

    result = redact_secrets("\n".join(matches))
    if len(matches) >= MAX_SEARCH_RESULTS:
        result += f"\n... (stopped at {MAX_SEARCH_RESULTS} matches; refine the query)"
    return result


def semantic_repository_search(query: str, top_k: int = 5) -> str:
    """Candidate-finding only (Phase B RAG). Never authoritative on its own —
    callers must confirm with read_file/search_code before relying on results."""
    if not query:
        raise RepoToolError("query is required")
    if len(query) < 2:
        raise RepoToolError("query is too short")
    top_k = max(1, min(int(top_k), 20))

    import rag_index  # local import: rag_index.py imports from this module

    try:
        results = rag_index.semantic_search(query, top_k=top_k)
    except RuntimeError as exc:
        raise RepoToolError(str(exc))

    if not results:
        return "(no semantic matches found)"

    lines = [
        f"{r['path']}:{r['start_line']}-{r['end_line']} (score={r['score']})"
        for r in results
    ]
    lines.append(
        "Note: these are candidate matches by semantic similarity only — "
        "use read_file or search_code to verify actual current content "
        "before relying on them."
    )
    return "\n".join(lines)


TOOL_SCHEMAS = [
    {
        "name": "list_repository_files",
        "description": (
            "List files under a repository-relative directory (default: repository "
            "root). Excludes .git, target/, build output, caches, and .env files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": (
                        "Repository-relative directory, e.g. 'app/src/main/java' or "
                        "'.' for the repository root. Must not contain '..'."
                    ),
                }
            },
            "required": [],
        },
    },
    {
        "name": "read_file",
        "description": (
            "Read the text contents of one repository file by its repository-relative "
            "path. Refuses .env files, .git internals, build output, and binary files. "
            "Large files are truncated with a clear marker."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Repository-relative file path, e.g. "
                        "'app/src/main/java/com/example/customer/model/Customer.java'. "
                        "Must not contain '..' or be absolute."
                    ),
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "search_code",
        "description": (
            "Case-insensitive literal substring search across repository source files. "
            "Returns matching file:line with a short snippet. Excludes .git, target/, "
            "build output, and .env files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Literal text to search for (not a regex).",
                },
                "glob": {
                    "type": "string",
                    "description": "Optional glob restricting the search, default '**/*.java'.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "semantic_repository_search",
        "description": (
            "Semantic (meaning-based) search over an index of repository files/docs. "
            "Finds likely-relevant candidates even without exact keyword matches — "
            "e.g. a query about 'customer email uniqueness' can surface relevant code "
            "even if it doesn't contain that exact phrase. Candidates only: always "
            "confirm with read_file or search_code before relying on results, since "
            "this reflects a snapshot index that may be stale relative to current files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural-language description of what you're looking for.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of candidates to return (default 5, max 20).",
                },
            },
            "required": ["query"],
        },
    },
]


def dispatch_tool_call(name: str, tool_input: dict):
    """Execute one tool call and return (result_text, is_error). Never raises."""
    tool_input = tool_input or {}
    try:
        if name == "list_repository_files":
            return list_repository_files(tool_input.get("directory", ".")), False
        if name == "read_file":
            return read_file(tool_input.get("path")), False
        if name == "search_code":
            return search_code(tool_input.get("query"), tool_input.get("glob", "**/*.java")), False
        if name == "semantic_repository_search":
            return semantic_repository_search(tool_input.get("query"), tool_input.get("top_k", 5)), False
        return f"unknown tool: {name!r}", True
    except RepoToolError as exc:
        return f"tool error: {exc}", True
    except Exception as exc:  # noqa: BLE001 - last-resort safety net, never crash the loop
        return f"unexpected tool error: {type(exc).__name__}", True
