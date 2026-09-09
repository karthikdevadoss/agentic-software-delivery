"""
V3 tool-using planning agent loop.

Claude receives the ticket but not a prebuilt repository summary. It
decides what to inspect by calling the read-only tools in tools.py; this
module executes exactly what Claude requests, feeds the result back, and
repeats until Claude is ready to answer or the tool budget is exhausted.

Sonnet 5 thinks by default, so an assistant turn's content list may start
with a thinking block before any tool_use/text block. That full content
list is preserved and replayed back to the API exactly as returned —
never filtered, reordered, or rebuilt — since Anthropic requires the
original assistant turn (thinking included) to remain intact across a
tool-use round trip. Only the final text is ever extracted for display.
"""

import os
import sys
import time

from anthropic import Anthropic

from tools import TOOL_SCHEMAS, dispatch_tool_call
import metrics

DEFAULT_MODEL = "claude-sonnet-5"
MODEL = os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL)

# Counts individual tool CALLS actually executed, not Claude conversation
# turns — if one turn requests multiple tools at once, each counts
# separately and the cap is enforced strictly (see run_agent_loop): any
# call beyond the cap within the same turn is skipped, not executed.
MAX_TOOL_CALLS = 8
MAX_TOKENS = 6000

SYSTEM_PROMPT = """You are a senior software engineer helping plan a change to an \
existing Spring Boot (Java 17) application.

You are NOT given a prebuilt repository summary. Instead you have three \
read-only tools to inspect the actual repository yourself:

- list_repository_files: list files under a directory
- read_file: read one file's contents
- search_code: search for a literal string across source files

Call these tools as many times as you need, in any order, before answering. \
Only rely on what the tools actually return — never invent files, classes, \
methods, or endpoints. If something you would expect is not found through \
these tools, say so explicitly using the exact phrase "not found via \
repository tools" instead of guessing.

When you have enough evidence, stop calling tools and produce a numbered \
implementation plan with these sections:

1. Existing components (verified via repository tools)
   - List the actual existing files/classes relevant to the ticket, using \
their real package and class names as found through the tools. If something \
relevant is not present, state plainly that it was "not found via \
repository tools".
2. Required changes (from the ticket)
   - What must change to satisfy the ticket, referencing existing files/classes \
by their real names where possible.
3. Recommended changes / assumptions needing confirmation
   - Anything you are recommending or assuming beyond the literal ticket text \
that should be confirmed with the team before implementation.
4. Order of implementation
5. Tests that should be added
6. Risks or edge cases

If you are forced to stop before you are fully confident, clearly mark any \
unverified claim as "unable to verify — tool budget exhausted" rather than \
presenting it as fact.
"""

FINALIZE_NOTICE = (
    "You have reached the maximum number of tool calls for this session. "
    "Produce your best implementation plan now using only the evidence "
    "already gathered. Clearly mark anything you could not verify as "
    "'unable to verify — tool budget exhausted'."
)


def _extract_text_blocks(content):
    return [block.text for block in content if getattr(block, "type", None) == "text"]


def _extract_tool_use_blocks(content):
    return [block for block in content if getattr(block, "type", None) == "tool_use"]


def _sanitize_tool_input(name: str, tool_input) -> str:
    tool_input = tool_input or {}
    if name == "read_file":
        return repr(tool_input.get("path", ""))
    if name == "list_repository_files":
        return repr(tool_input.get("directory", "."))
    if name == "search_code":
        query = tool_input.get("query", "")
        glob = tool_input.get("glob")
        if glob and glob != "**/*.java":
            return f"{query!r}, glob={glob!r}"
        return f"{query!r}"
    if name == "semantic_repository_search":
        return f"{tool_input.get('query', '')!r}, top_k={tool_input.get('top_k', 5)}"
    if name == "propose_source_change":
        return repr(tool_input.get("path", ""))
    if name == "apply_approved_source_change":
        return repr(tool_input.get("edit_id", ""))
    if name in ("run_controlled_compile", "run_controlled_tests"):
        return "()"
    return repr(tool_input)


def _result_note(tool_name: str, result_text: str, is_error: bool) -> str:
    truncated = any(
        marker in result_text
        for marker in ("(truncated)", "more omitted", "stopped at")
    )

    if is_error:
        # Error strings are prose ("tool error: ..."), not listings/matches —
        # counting them as "entries"/"matches" would be misleading.
        note = f"{len(result_text)} chars"
    elif tool_name == "list_repository_files":
        if result_text == "(no files found)":
            note = "0 entries"
        else:
            count = sum(1 for line in result_text.splitlines() if line and not line.startswith("..."))
            note = f"{count} entries"
    elif tool_name == "search_code":
        if result_text == "(no matches found)":
            note = "0 matches"
        else:
            count = sum(1 for line in result_text.splitlines() if line and not line.startswith("..."))
            note = f"{count} matches"
    elif tool_name == "semantic_repository_search":
        if result_text == "(no semantic matches found)":
            note = "0 candidates"
        else:
            count = sum(
                1 for line in result_text.splitlines()
                if line and ":" in line and "score=" in line
            )
            note = f"{count} candidates"
    else:
        note = f"{len(result_text)} chars"

    if truncated:
        note += ", truncated"
    return note


def _trace(iteration: int, message: str) -> None:
    print(f"Iteration {iteration}: {message}", file=sys.stderr)


def run_agent_loop(
    ticket: str,
    api_key: str,
    tool_schemas=None,
    dispatch_fn=None,
    system_prompt_suffix: str = "",
) -> str:
    """tool_schemas/dispatch_fn default to the read-only V3 tool set (safe,
    unchanged behavior for existing callers). Passing an expanded schema
    list + dispatcher (e.g. execution_tools.EXECUTION_TOOL_SCHEMAS /
    dispatch_execution_tool_call) is how V4.1 grants write/build capability
    — this loop has no idea which tools it's running and never hardcodes
    their names beyond the cosmetic trace-formatting helpers above."""
    tool_schemas = tool_schemas if tool_schemas is not None else TOOL_SCHEMAS
    dispatch_fn = dispatch_fn if dispatch_fn is not None else dispatch_tool_call
    system_prompt = SYSTEM_PROMPT + system_prompt_suffix

    client = Anthropic(api_key=api_key)
    messages = [{"role": "user", "content": f"Ticket:\n{ticket}"}]
    tool_call_count = 0

    while True:
        tools_enabled = tool_call_count < MAX_TOOL_CALLS

        create_kwargs = {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "system": system_prompt,
            "messages": messages,
        }
        if tools_enabled:
            create_kwargs["tools"] = tool_schemas

        response = client.messages.create(**create_kwargs)

        # Real usage straight from the API response's own `.usage` field —
        # never estimated, never scraped from a UI counter.
        metrics.record_model_usage(
            provider="anthropic", model=MODEL,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cache_creation_input_tokens=getattr(response.usage, "cache_creation_input_tokens", None),
            cache_read_input_tokens=getattr(response.usage, "cache_read_input_tokens", None),
        )

        # Preserve the assistant turn EXACTLY as returned by Anthropic.
        # Do not filter thinking blocks, reconstruct them, reorder them,
        # or extract only text/tool_use before sending this turn back —
        # the complete original content list must round-trip untouched.
        messages.append({"role": "assistant", "content": response.content})

        tool_use_blocks = _extract_tool_use_blocks(response.content)

        # Gate on the presence of actual tool_use blocks, not on
        # stop_reason == "tool_use" alone. If a response is cut short by
        # max_tokens but still contains one or more complete, valid
        # tool_use blocks, those calls must still be answered with a
        # tool_result — treating a non-"tool_use" stop_reason as
        # automatically final would silently drop a real tool request.
        if not (tools_enabled and tool_use_blocks):
            text_blocks = _extract_text_blocks(response.content)
            if text_blocks:
                plan = "".join(text_blocks)
                if response.stop_reason == "max_tokens":
                    plan += (
                        "\n\n[warning: response stopped due to max_tokens — "
                        "this plan may be cut off / incomplete]"
                    )
            else:
                plan = (
                    "Unable to produce a plan — no final text was returned "
                    f"(stop_reason={response.stop_reason!r})."
                )
            print(f"Final answer after {tool_call_count} tool call(s)", file=sys.stderr)
            return plan

        tool_results = []
        for block in tool_use_blocks:
            sanitized = _sanitize_tool_input(block.name, block.input)

            if tool_call_count >= MAX_TOOL_CALLS:
                # Strict cap: even if this call arrived in the same turn as
                # ones already executed, never exceed MAX_TOOL_CALLS actual
                # executions. It still needs a tool_result to keep the
                # conversation valid, so report the skip without running it.
                _trace(tool_call_count, f"{block.name}({sanitized}) -> SKIPPED, tool budget exhausted")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "tool budget exhausted — this call was not executed",
                    "is_error": True,
                })
                continue

            tool_call_count += 1
            call_start = time.monotonic()
            result_text, is_error = dispatch_fn(block.name, block.input)
            duration_ms = round((time.monotonic() - call_start) * 1000, 1)
            status = "ERROR" if is_error else "OK"
            note = _result_note(block.name, result_text, is_error)
            _trace(tool_call_count, f"{block.name}({sanitized}) -> {status}, {note}")
            metrics.record_tool_call(
                tool=block.name, input_summary=sanitized, success=not is_error,
                duration_ms=duration_ms, result_size=len(result_text),
                truncated="truncated" in note or "omitted" in note or "stopped at" in note,
                blocked_unsafe=is_error and metrics.is_security_block(result_text),
            )

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_text,
                "is_error": is_error,
            })

        if tool_call_count >= MAX_TOOL_CALLS:
            tool_results.append({"type": "text", "text": FINALIZE_NOTICE})

        messages.append({"role": "user", "content": tool_results})
