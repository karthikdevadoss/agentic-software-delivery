"""
Claude Code development-telemetry hook — the single entrypoint every wired
hook event (see .claude/settings.local.json) invokes.

Distinct source from Workbench runtime telemetry (CLAUDE.md P0 "no more
lost engineering events" ledger): source="claude_code",
activity_class="PRODUCT_DEVELOPMENT". Same underlying event ledger/spool
(agent/event_ledger.py) — not a second telemetry architecture.

CRITICAL invariants:
  1. MUST return in milliseconds. Uses event_ledger.spool_only() — zero
     network I/O in the synchronous path — plus a best-effort, detached,
     non-blocking background sync trigger. A hook that blocks on a
     TCP-proxied Postgres connection would visibly slow down every tool
     call in every future Claude Code session in this repo. DELIBERATE
     EXCEPTION (Owner directive, task-level AI cost accounting,
     2026-09-18): SessionEnd specifically also does a local, streaming
     read of the session's own transcript file to extract real token
     usage (see _extract_usage_from_transcript below) — a one-time cost
     paid once per whole session, not per tool call, so it does not
     compound the way a per-PreToolUse cost would; still local disk I/O
     only, never network.
  2. MUST NEVER raise/exit non-zero in a way that blocks Claude Code.
     SessionStart/SessionEnd cannot block by design, but PreToolUse/
     PermissionRequest CAN (a non-zero exit can deny a tool call) — so
     every code path here is wrapped to fail safe (exit 0) rather than
     accidentally deny a real, legitimate action because telemetry broke.
  3. AMENDED (2026-09-18): never captures hidden chain-of-thought or any
     message CONTENT/text — the hook JSON Claude Code provides on stdin
     does not expose chain-of-thought (verified: no such field exists in
     the installed binary's own hook payload construction), and for
     transcript_path specifically, this script reads ONLY each recorded
     message's `usage` object (real, provider-returned token counts —
     structurally the same category of fact as an HTTP response's
     Content-Length header, not the message's own text) — it never reads,
     stores, or logs any message's `content`/text field. This distinction
     is enforced in code, not just in this comment: see
     _extract_usage_from_transcript's own docstring and the assertion in
     its test coverage that content is never touched.

Hook JSON field names (session_id, hook_event_name, cwd, tool_name,
tool_input, tool_response, prompt, transcript_path, permission_mode,
stop_hook_active) were verified directly against literal property access
in the installed Claude Code v2.1.263 binary itself, not assumed from
documentation. Every field is still read defensively via .get() — a
future version changing shape must never crash this script.

Run (invoked by Claude Code itself, not manually):
  python agent/claude_code_hook.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

MAX_TEXT_CHARS = 2000  # bounded excerpt, not full content — same discipline as web_server.py's _bounded_summary

_HOOK_EVENT_TO_CANONICAL_TYPE = {
    "SessionStart": "dev_session_started",
    "SessionEnd": "dev_session_ended",
    "UserPromptSubmit": "user_prompt_submitted",
    "PreToolUse": "tool_call_started",
    "PostToolUse": "tool_call_completed",
    "PostToolUseFailure": "tool_call_failed",
    "PermissionRequest": "authorization_requested",
    "PermissionDenied": "authorization_decision",
    "Notification": "human_input_requested",
    "Stop": "dev_turn_stopped",
    "SubagentStart": "subagent_started",
    "SubagentStop": "subagent_stopped",
}

# Which hook events represent Claude genuinely waiting on the human —
# these (and only these) trigger the Windows notifier. Kept narrow
# deliberately: "one notification per pending request, do not spam".
_ATTENTION_REQUIRED_EVENTS = {"PermissionRequest", "Notification"}

_ACTOR_TYPE_BY_HOOK_EVENT = {
    "SessionStart": "system",
    "SessionEnd": "system",
    "UserPromptSubmit": "human",
}


def _bounded(value, limit=MAX_TEXT_CHARS):
    if value is None:
        return None
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    if len(text) <= limit:
        return text
    return text[:limit] + f"...[truncated, {len(text)} chars total]"


def _extract_usage_from_transcript(transcript_path):
    """Streams the session's own transcript JSONL line by line, reading
    ONLY each assistant message's `usage` object (real, provider-returned
    token counts) and `model` field — NEVER `content`/text, on any line,
    for any reason. Returns a summed-usage dict, or None if the file is
    missing/unreadable/contains no usage data (never a fabricated zero).

    Each transcript line's top-level shape (verified directly against a
    real transcript file, not assumed from documentation):
      {"type": "assistant", "message": {"role": "assistant", "model": ...,
       "usage": {"input_tokens": ..., "output_tokens": ...,
                 "cache_creation_input_tokens": ...,
                 "cache_read_input_tokens": ...,
                 "output_tokens_details": {"thinking_tokens": ...}, ...},
       "content": [...]}, ...}
    Only `message.usage` and `message.model` are ever accessed below —
    `message.content` is never read, copied, or referenced, by design."""
    if not transcript_path:
        return None
    path = Path(transcript_path)
    if not path.exists():
        return None

    totals = {
        "input_tokens": 0, "output_tokens": 0,
        "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
        "message_count": 0,
    }
    model = None
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if obj.get("type") != "assistant":
                    continue
                message = obj.get("message") or {}
                usage = message.get("usage")
                if not usage:
                    continue
                totals["input_tokens"] += usage.get("input_tokens") or 0
                totals["output_tokens"] += usage.get("output_tokens") or 0
                totals["cache_creation_input_tokens"] += usage.get("cache_creation_input_tokens") or 0
                totals["cache_read_input_tokens"] += usage.get("cache_read_input_tokens") or 0
                totals["message_count"] += 1
                model = message.get("model") or model
    except OSError:
        return None

    if totals["message_count"] == 0:
        return None
    totals["model"] = model
    return totals


def _iter_subagent_transcripts(main_transcript_path):
    """Yields (meta_dict, usage_dict) for every subagent spawned during this
    session -- real gap found 2026-09-18 (the 40 EUR overnight-session
    incident): closing this required a from-scratch manual forensic
    investigation (locating <session>/subagents/*.jsonl by hand, matching
    each .meta.json sidecar). Claude Code's own SubagentStop hook payload
    does not expose which specific subagent just finished or its
    transcript path (verified: only cwd/transcript_path[=the MAIN
    session's]/permission_mode/stop_hook_active are present -- see this
    module's own field-verification note at the top of the file), so a
    live per-subagent hook is not reliable. Instead, called once at
    SessionEnd (a point already proven reliable) and walks the on-disk
    convention observed directly in a real installed Claude Code version:
    <project_dir>/<session_id>/subagents/agent-<id>.jsonl plus a sibling
    agent-<id>.meta.json (agentType, description, worktreeBranch when a
    fork used an isolated worktree). This convention is NOT documented
    anywhere; if a future Claude Code version changes it, this silently
    yields nothing (never raises) -- the whole-session model_usage total
    from _extract_usage_from_transcript remains correct and complete
    regardless, since it is computed independently from the main
    transcript alone. Never double-counts: subagent turns are NOT present
    in the main transcript (verified: every real transcript inspected had
    isSidechain=false / absent for 100% of its own entries)."""
    main_path = Path(main_transcript_path) if main_transcript_path else None
    if not main_path or not main_path.exists():
        return
    subagents_dir = main_path.parent / main_path.stem / "subagents"
    if not subagents_dir.is_dir():
        return
    for meta_path in sorted(subagents_dir.glob("agent-*.meta.json")):
        agent_id = meta_path.name[: -len(".meta.json")]
        transcript_path = subagents_dir / f"{agent_id}.jsonl"
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
        usage = _extract_usage_from_transcript(transcript_path)
        if usage is None:
            continue
        meta["agent_id"] = agent_id
        yield meta, usage


def _notify_async(title, message):
    """Best-effort, detached, non-blocking — never awaited, never allowed
    to raise into the caller. See agent/claude_notify.ps1."""
    try:
        import subprocess
        script = Path(__file__).resolve().parent / "claude_notify.ps1"
        if not script.exists():
            return
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(script), "-Title", title, "-Message", message],
            creationflags=creationflags, close_fds=True,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:  # noqa: BLE001 - a notification failure must never break the hook
        pass


def main():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:  # noqa: BLE001 - malformed stdin must never crash the hook
        payload = {}

    hook_event = payload.get("hook_event_name") or "Unknown"
    canonical_type = _HOOK_EVENT_TO_CANONICAL_TYPE.get(hook_event, f"claude_code_{hook_event.lower()}")

    event_payload = {
        "hook_event_name": hook_event,
        "cwd": payload.get("cwd"),
        "transcript_path": payload.get("transcript_path"),
        "permission_mode": payload.get("permission_mode"),
        "stop_hook_active": payload.get("stop_hook_active"),
    }

    if hook_event == "UserPromptSubmit":
        prompt_text = payload.get("prompt") or ""
        event_payload["prompt_char_count"] = len(prompt_text)
        event_payload["prompt_word_count"] = len(prompt_text.split())
        event_payload["prompt_excerpt"] = _bounded(prompt_text)

    if hook_event in ("PreToolUse", "PostToolUse", "PostToolUseFailure", "PermissionRequest", "PermissionDenied"):
        event_payload["tool_input_excerpt"] = _bounded(payload.get("tool_input"))

    if hook_event in ("PostToolUse", "PostToolUseFailure"):
        event_payload["tool_response_excerpt"] = _bounded(payload.get("tool_response"))

    if hook_event == "Notification":
        event_payload["notification_message"] = _bounded(payload.get("message"))

    try:
        import event_ledger
        event_ledger.spool_only(
            canonical_type,
            source="claude_code",
            activity_class=event_ledger.ACTIVITY_CLASS_PRODUCT_DEVELOPMENT,
            session_id=payload.get("session_id"),
            actor_type=_ACTOR_TYPE_BY_HOOK_EVENT.get(hook_event, "ai"),
            tool_name=payload.get("tool_name"),
            status=hook_event,
            payload=event_payload,
        )

        if hook_event == "SessionEnd":
            usage = _extract_usage_from_transcript(payload.get("transcript_path"))
            if usage is not None:
                event_ledger.spool_only(
                    "model_usage",
                    source="claude_code",
                    activity_class=event_ledger.ACTIVITY_CLASS_PRODUCT_DEVELOPMENT,
                    session_id=payload.get("session_id"),
                    actor_type="ai",
                    provider="anthropic",
                    model=usage.get("model"),
                    input_tokens=usage["input_tokens"],
                    output_tokens=usage["output_tokens"],
                    cache_write_tokens=usage["cache_creation_input_tokens"],
                    cache_read_tokens=usage["cache_read_input_tokens"],
                    status="SessionEnd",
                    payload={"real_assistant_message_count": usage["message_count"]},
                )

            # Real gap found 2026-09-18 (the 40 EUR overnight-session
            # incident): explaining "why did this cost what it cost"
            # required manually locating and parsing each spawned
            # subagent's own separate transcript file by hand. Captured
            # here as a DISTINCT event_type (never "model_usage") so it
            # can never be summed into -- and silently inflate or duplicate
            # -- the whole-session total above; this is supplementary
            # per-task detail, not a second measurement of the same thing.
            for meta, sub_usage in _iter_subagent_transcripts(payload.get("transcript_path")):
                event_ledger.spool_only(
                    "claude_code_subagent_usage",
                    source="claude_code",
                    activity_class=event_ledger.ACTIVITY_CLASS_PRODUCT_DEVELOPMENT,
                    session_id=payload.get("session_id"),
                    actor_type="ai",
                    provider="anthropic",
                    model=sub_usage.get("model"),
                    tool_name=meta.get("agentType"),
                    input_tokens=sub_usage["input_tokens"],
                    output_tokens=sub_usage["output_tokens"],
                    cache_write_tokens=sub_usage["cache_creation_input_tokens"],
                    cache_read_tokens=sub_usage["cache_read_input_tokens"],
                    status="SessionEnd",
                    payload={
                        "agent_id": meta.get("agent_id"),
                        "agent_type": meta.get("agentType"),
                        "description": _bounded(meta.get("description"), 300),
                        "worktree_branch": meta.get("worktreeBranch"),
                        "is_fork": meta.get("isFork", False),
                        "real_assistant_message_count": sub_usage["message_count"],
                    },
                )

        event_ledger.trigger_background_sync()
    except Exception:  # noqa: BLE001 - telemetry must never break Claude Code itself
        pass

    if hook_event in _ATTENTION_REQUIRED_EVENTS:
        tool_name = payload.get("tool_name")
        if hook_event == "PermissionRequest" and tool_name:
            _notify_async("Claude needs your approval", f"Waiting on: {tool_name}")
        elif hook_event == "Notification":
            _notify_async("Claude needs your attention", _bounded(payload.get("message"), 200) or "Claude is waiting.")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - absolute last resort: never let this script break Claude Code
        pass
    sys.exit(0)
