"""
Verifies the machine-local Claude Code hooks configuration actually
matches what's needed for development-telemetry capture — the canonical
check for docs/RECOVERY.md's "Recovering Claude Code development-
telemetry hooks" procedure and for the incident this exists to prevent
(see docs/LESSONS.md): a hooks section silently disappearing from
.claude/settings.local.json because Claude Code's own permission-
remember mechanism rewrites that specific file and drops any key it
doesn't manage. Hooks belong in the USER-LEVEL settings file instead
(~/.claude/settings.json on this machine, empirically confirmed immune
to that rewrite — see docs/DECISIONS.md), never in
.claude/settings.local.json.

This script only reads local files and never touches the network — it
proves the CONFIGURATION is present and structurally correct, not that
Claude Code has actually invoked it (that requires a real session — see
docs/RECOVERY.md and the test suite for what each layer actually proves).

Run: python agent/verify_claude_hooks_config.py
Exit code 0 = configuration present and correct. Non-zero = a real gap.
"""

import json
import os
import sys
from pathlib import Path

EXPECTED_HOOK_EVENTS = (
    "SessionStart", "SessionEnd", "UserPromptSubmit",
    "PreToolUse", "PostToolUse", "PostToolUseFailure",
    "PermissionRequest", "PermissionDenied", "Notification",
    "Stop", "SubagentStart", "SubagentStop",
)


def _user_settings_path() -> Path:
    home = Path(os.path.expanduser("~"))
    return home / ".claude" / "settings.json"


def _project_local_settings_path() -> Path:
    return Path(__file__).resolve().parent.parent / ".claude" / "settings.local.json"


def verify() -> list:
    """Returns a list of human-readable problems found. Empty list means
    everything checked out clean."""
    problems = []

    project_local_path = _project_local_settings_path()
    if project_local_path.exists():
        try:
            project_local = json.loads(project_local_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"{project_local_path} exists but is not valid JSON: {exc}")
            project_local = {}
        if "hooks" in project_local:
            problems.append(
                f"{project_local_path} has a 'hooks' key -- this is the exact "
                "known-bad location (Claude Code's permission-remember "
                "mechanism silently drops unmanaged keys here; see "
                "docs/LESSONS.md). Move it to the user-level settings file."
            )

    user_path = _user_settings_path()
    if not user_path.exists():
        problems.append(f"{user_path} does not exist -- hooks configuration is missing entirely.")
        return problems

    try:
        user_settings = json.loads(user_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        problems.append(f"{user_path} exists but is not valid JSON: {exc}")
        return problems

    hooks = user_settings.get("hooks")
    if not isinstance(hooks, dict):
        problems.append(f"{user_path} has no 'hooks' object.")
        return problems

    missing = [event for event in EXPECTED_HOOK_EVENTS if event not in hooks]
    if missing:
        problems.append(f"{user_path}'s hooks are missing event(s): {', '.join(missing)}")

    for event, entries in hooks.items():
        if not isinstance(entries, list) or not entries:
            problems.append(f"Hook '{event}' has no hook entries configured.")
            continue
        for entry in entries:
            commands = entry.get("hooks", [])
            if not commands:
                problems.append(f"Hook '{event}' entry has no commands.")
                continue
            for cmd in commands:
                command_str = cmd.get("command", "")
                if "claude_code_hook.py" not in command_str:
                    problems.append(
                        f"Hook '{event}' command does not reference "
                        f"claude_code_hook.py: {command_str!r}"
                    )
                if "${CLAUDE_PROJECT_DIR}" not in command_str:
                    problems.append(
                        f"Hook '{event}' command does not use "
                        f"${{CLAUDE_PROJECT_DIR}} (won't be portable across "
                        f"projects/machines): {command_str!r}"
                    )

    return problems


if __name__ == "__main__":
    problems = verify()
    if not problems:
        print("CLAUDE HOOKS CONFIG: OK -- all expected hooks present in the user-level settings file.")
        sys.exit(0)
    print("CLAUDE HOOKS CONFIG: PROBLEMS FOUND")
    for p in problems:
        print(f"  - {p}")
    sys.exit(1)
