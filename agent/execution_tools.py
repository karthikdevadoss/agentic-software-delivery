"""
V4.1 live execution tool surface — the ONLY module that wires
write_tools.py/build_tools.py into the live Claude tool-calling loop.

Composes on top of tools.py's read-only TOOL_SCHEMAS/dispatch_tool_call
(imported and reused, not duplicated) with four new capabilities:

- propose_source_change: create a pending edit AND synchronously gate it
  behind a real human approve/reject decision (default: a CLI prompt reading
  real stdin). This is the ONLY place approval happens.
- apply_approved_source_change: write a previously-approved edit to disk.
  Fails safely if it was never approved.
- run_controlled_compile / run_controlled_tests: thin wrappers over
  build_tools.run_maven.

CRITICAL INVARIANT: write_tools.approve_edit()/reject_edit() are called only
from inside this module's approval-gate function, driven by a real human
decision (stdin by default, or an injected test double). They are NEVER
registered as tool schemas and NEVER reachable via dispatch_execution_tool_call
by any name the model could supply. The model's propose_source_change
input_schema has no field that can carry an approval decision — there is no
path, direct or indirect, for the model to approve its own change.
"""

import sys

import tools
import write_tools
import build_tools
import metrics


def _default_approval_prompt(edit) -> bool:
    """Real human gate: blocks on real terminal input. Swap via
    set_approval_prompt() for tests or a future non-CLI host — the model
    can never reach this function or supply its return value itself."""
    print("\n" + "=" * 60, file=sys.stderr)
    print(f"PROPOSED CHANGE {edit.id} -> {edit.path}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(edit.diff or "(new empty file)", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    while True:
        try:
            choice = input(f"Approve edit {edit.id}? [y/N]: ").strip().lower()
        except EOFError:
            # No real interactive terminal is attached — fail closed. A
            # missing human is not the same as an approving one; silently
            # defaulting to approve here would defeat the entire boundary.
            print(
                "\nNo interactive terminal available to collect a real "
                "approval decision — defaulting to REJECT.",
                file=sys.stderr,
            )
            return False
        if choice in ("y", "yes"):
            return True
        if choice in ("n", "no", ""):
            return False
        print("Please answer y or n.", file=sys.stderr)


_approval_prompt_fn = _default_approval_prompt


def set_approval_prompt(fn) -> None:
    """Test/host hook. fn(edit) -> bool. Never call this from model-facing
    code — it exists for automated tests and for a future non-CLI trusted
    host, not for the agent loop."""
    global _approval_prompt_fn
    _approval_prompt_fn = fn


def _tool_propose_source_change(path, new_content):
    try:
        edit = write_tools.propose_edit(path, new_content)
    except write_tools.WriteToolError as exc:
        return str(exc), True

    approved = _approval_prompt_fn(edit)
    if approved:
        write_tools.approve_edit(edit.id)
        metrics.record_tool_call(
            tool="approval_decision", input_summary=edit.id, success=True,
            duration_ms=0, result_size=0,
        )
        return (
            f"Proposal {edit.id} for {edit.path} was APPROVED by the human "
            f"operator. Call apply_approved_source_change({edit.id!r}) to write it."
        ), False

    write_tools.reject_edit(edit.id)
    metrics.record_tool_call(
        tool="approval_decision", input_summary=edit.id, success=False,
        duration_ms=0, result_size=0,
    )
    return f"Proposal for {path} was REJECTED by the human operator.", False


def _tool_apply_approved_source_change(edit_id):
    try:
        result = write_tools.apply_edit(edit_id)
        return result, False
    except write_tools.WriteToolError as exc:
        return str(exc), True


def _tool_run_controlled_compile(_input=None):
    try:
        result = build_tools.run_maven("compile")
    except build_tools.BuildToolError as exc:
        return str(exc), True
    text = f"compile {'SUCCEEDED' if result['success'] else 'FAILED'} in {result['duration_ms']}ms\n{result['output']}"
    return text, not result["success"]


def _tool_run_controlled_tests(_input=None):
    try:
        result = build_tools.run_maven("test")
    except build_tools.BuildToolError as exc:
        return str(exc), True
    text = f"test {'SUCCEEDED' if result['success'] else 'FAILED'} in {result['duration_ms']}ms\n{result['output']}"
    return text, not result["success"]


_EXECUTION_ONLY_SCHEMAS = [
    {
        "name": "propose_source_change",
        "description": (
            "Propose a source code change for human review. Presents the "
            "proposed diff to a human operator and pauses for their explicit "
            "approve/reject decision before this call returns. You cannot "
            "approve your own proposal — there is no tool or field that lets "
            "you supply an approval decision; only the human operator can "
            "approve or reject. Writing is restricted to "
            "app/src/main/java and app/src/test/java, .java files only."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Repository-relative .java file path to create or modify.",
                },
                "new_content": {
                    "type": "string",
                    "description": "The complete new content of the file (not a diff/patch).",
                },
            },
            "required": ["path", "new_content"],
        },
    },
    {
        "name": "apply_approved_source_change",
        "description": (
            "Apply a previously proposed change to disk. Only succeeds if a "
            "human operator already approved this exact proposal via "
            "propose_source_change, and only if the path/content are "
            "unchanged since that approval — there is no way to approve a "
            "proposal through this or any other tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "edit_id": {
                    "type": "string",
                    "description": "The id returned by propose_source_change.",
                },
            },
            "required": ["edit_id"],
        },
    },
    {
        "name": "run_controlled_compile",
        "description": (
            "Run 'mvn compile' on the Customer Spring Boot app. No arbitrary "
            "commands are possible — this always runs exactly this one "
            "allowlisted operation."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "run_controlled_tests",
        "description": (
            "Run 'mvn test' on the Customer Spring Boot app. No arbitrary "
            "commands are possible — this always runs exactly this one "
            "allowlisted operation."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

EXECUTION_TOOL_SCHEMAS = tools.TOOL_SCHEMAS + _EXECUTION_ONLY_SCHEMAS

_EXECUTION_DISPATCH = {
    "propose_source_change": lambda i: _tool_propose_source_change(
        i.get("path"), i.get("new_content")
    ),
    "apply_approved_source_change": lambda i: _tool_apply_approved_source_change(
        i.get("edit_id")
    ),
    "run_controlled_compile": lambda i: _tool_run_controlled_compile(),
    "run_controlled_tests": lambda i: _tool_run_controlled_tests(),
}


def dispatch_execution_tool_call(name: str, tool_input: dict):
    """Drop-in replacement for tools.dispatch_tool_call with 4 more
    capabilities layered on top. Falls through to the read-only dispatcher
    for every name it doesn't recognize — approve_edit/reject_edit are not,
    and will never be, in this mapping."""
    tool_input = tool_input or {}
    handler = _EXECUTION_DISPATCH.get(name)
    if handler is not None:
        return handler(tool_input)
    return tools.dispatch_tool_call(name, tool_input)
