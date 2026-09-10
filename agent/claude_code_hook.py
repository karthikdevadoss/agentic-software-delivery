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
     call in every future Claude Code session in this repo.
  2. MUST NEVER raise/exit non-zero in a way that blocks Claude Code.
     SessionStart/SessionEnd cannot block by design, but PreToolUse/
     PermissionRequest CAN (a non-zero exit can deny a tool call) — so
     every code path here is wrapped to fail safe (exit 0) rather than
     accidentally deny a real, legitimate action because telemetry broke.
  3. Never captures hidden chain-of-thought — the hook JSON Claude Code
     provides on stdin does not expose it (verified: no such field exists
     in the installed binary's own hook payload construction), and this
     script does not read transcript_path's file contents, only records
     its path for reference.

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
