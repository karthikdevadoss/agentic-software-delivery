"""
V4 write/execution boundary foundation.

The agent must never receive unrestricted filesystem write authority. This
module implements a strict propose -> validate -> approve -> apply flow:

1. propose_edit(path, new_content) -> a PendingEdit (unified diff computed,
   nothing written to disk yet). Path/scope validated at propose time.
2. A human (or an explicit calling layer standing in for one, for now)
   inspects PendingEdit.diff.
3. approve_edit(edit_id) marks it approved. Nothing else does.
4. apply_edit(edit_id) writes the file — only if approved, only once, and
   only after re-validating the path/scope (in case anything changed
   between propose and apply).

Security is NOT reimplemented here. Path traversal, absolute paths,
symlinks, and secret-like filenames are rejected via the exact same
tools._resolve_safe_path() used by the read-only tools and the MCP adapter
— the one thing this module adds on top is an explicit whitelist of
writable source directories (reading is repo-wide; writing is not).

No shell access exists anywhere in this module.
"""

import dataclasses
import difflib
import hashlib
import time
import uuid
from pathlib import Path

import tools
import metrics

# Deliberately narrow: only the Customer app's own source, test, and
# static-UI trees. Not pom.xml, not docs/, not agent/ itself, not build
# config — expanding this list is a scope decision, not something to grow
# implicitly. static/ was added specifically for the risk-gated trainer
# demo flow (small visual/UI changes) — still .html only, still inside
# the same Customer app, still going through the same path-security and
# approval-binding checks as any other write.
ALLOWED_WRITE_PREFIXES = ("app/src/main/java/", "app/src/test/java/", "app/src/main/resources/static/")
ALLOWED_WRITE_EXTENSIONS = {".java", ".html"}


class WriteToolError(Exception):
    """Raised for any safely-reportable write validation failure. Never lets
    a write attempt crash the caller — always report, never proceed."""


@dataclasses.dataclass
class PendingEdit:
    id: str
    path: str
    old_content: str
    new_content: str
    diff: str
    is_new_file: bool
    approved: bool = False
    applied: bool = False
    approved_binding: str = None  # hash(path, new_content) captured at approval time


_pending_edits = {}


def _binding_hash(path: str, new_content: str) -> str:
    """Binds an approval to the exact (path, content) pair approved — not
    just 'this edit_id was approved at some point'. Recomputed and checked
    at apply time so any mutation of either field after approval (by any
    code path, however unlikely today) is detected and refused rather than
    silently applied. Deliberately just hashlib — no crypto library needed
    for this local, single-process, no-network-boundary MVP."""
    return hashlib.sha256(f"{path}\0{new_content}".encode("utf-8")).hexdigest()


def _validate_write_scope(path: str) -> Path:
    """Reuses tools._resolve_safe_path for traversal/absolute/symlink/secret-
    name checks, then adds the write-specific scope + extension restriction."""
    resolved = tools._resolve_safe_path(path)  # noqa: SLF001 - intentional reuse, not duplication
    rel = resolved.relative_to(tools.REPO_ROOT).as_posix()

    if not rel.startswith(ALLOWED_WRITE_PREFIXES):
        raise WriteToolError(
            f"write not allowed outside approved source scope {ALLOWED_WRITE_PREFIXES}: {path!r}"
        )
    if resolved.suffix.lower() not in ALLOWED_WRITE_EXTENSIONS:
        raise WriteToolError(f"write not allowed for file type: {path!r}")

    # No separate symlink check needed here: tools._resolve_safe_path()
    # already guarantees the returned path can never itself be a symlink
    # (its lexical-vs-resolved comparison rejects any symlink in the chain
    # before returning) — re-checking would be dead code, not extra safety.
    return resolved


def propose_edit(path: str, new_content: str) -> PendingEdit:
    """Validate + diff only. Nothing is written to disk."""
    start = time.monotonic()
    try:
        resolved = _validate_write_scope(path)
    except tools.RepoToolError as exc:
        _record("propose_edit", path, False, start, blocked_unsafe=metrics.is_security_block(str(exc)))
        raise WriteToolError(str(exc))
    except WriteToolError:
        _record("propose_edit", path, False, start)
        raise

    old_content = resolved.read_text(encoding="utf-8") if resolved.exists() else ""
    is_new_file = not resolved.exists()

    diff = "".join(difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{path}" if not is_new_file else "/dev/null",
        tofile=f"b/{path}",
    ))

    rel_path = resolved.relative_to(tools.REPO_ROOT).as_posix()
    edit = PendingEdit(
        id=uuid.uuid4().hex[:8],
        path=rel_path,
        old_content=old_content,
        new_content=new_content,
        diff=diff,
        is_new_file=is_new_file,
    )
    _pending_edits[edit.id] = edit
    _record("propose_edit", rel_path, True, start, result_size=len(diff))
    return edit


def approve_edit(edit_id: str) -> None:
    """Stands in for explicit human approval — this function itself is the
    trust boundary: it must only ever be called from the trusted host/CLI
    layer, never exposed as an LLM-callable tool. Marks a pending edit
    approved and binds approval to the exact (path, content) pair at this
    moment; does not write anything."""
    edit = _pending_edits.get(edit_id)
    if edit is None:
        raise WriteToolError(f"no such pending edit: {edit_id!r}")
    edit.approved = True
    edit.approved_binding = _binding_hash(edit.path, edit.new_content)


def reject_edit(edit_id: str) -> None:
    if edit_id not in _pending_edits:
        raise WriteToolError(f"no such pending edit: {edit_id!r}")
    del _pending_edits[edit_id]


def list_pending_edits() -> list:
    return list(_pending_edits.values())


def apply_edit(edit_id: str) -> str:
    """Writes to disk. Only succeeds if approved and not already applied."""
    start = time.monotonic()
    edit = _pending_edits.get(edit_id)

    if edit is None:
        _record("apply_edit", edit_id, False, start)
        raise WriteToolError(f"no such pending edit: {edit_id!r}")
    if not edit.approved:
        _record("apply_edit", edit.path, False, start)
        raise WriteToolError(f"edit {edit_id!r} has not been approved — cannot apply")
    if edit.applied:
        _record("apply_edit", edit.path, False, start)
        raise WriteToolError(f"edit {edit_id!r} was already applied")

    # The approval is bound to the exact (path, content) pair that existed
    # at approval time. If either changed since — however that happened —
    # refuse rather than apply something nobody actually approved.
    if _binding_hash(edit.path, edit.new_content) != edit.approved_binding:
        _record("apply_edit", edit.path, False, start, blocked_unsafe=True)
        raise WriteToolError(
            f"edit {edit_id!r} target/content changed since approval — refusing to apply"
        )

    # Re-validate at apply time — the world may have changed since propose.
    resolved = _validate_write_scope(edit.path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(edit.new_content, encoding="utf-8")
    edit.applied = True

    _record("apply_edit", edit.path, True, start, result_size=len(edit.new_content))
    return f"applied edit {edit_id} to {edit.path} ({len(edit.new_content)} chars)"


def _record(tool_name, input_summary, success, start, result_size=0, blocked_unsafe=False):
    metrics.record_tool_call(
        tool=tool_name, input_summary=input_summary, success=success,
        duration_ms=round((time.monotonic() - start) * 1000, 1),
        result_size=result_size, blocked_unsafe=blocked_unsafe,
    )
