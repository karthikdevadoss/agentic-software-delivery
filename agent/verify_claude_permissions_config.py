"""
Verifies this machine's real Claude Code permission configuration never
blanket-auto-allows an irreversible/production-mutating command family
without human confirmation -- the exact, concrete root cause of a real
capability-boundary incident (docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml
AEQ-023): .claude/settings.local.json's permissions.allow list contained
"Bash(railway up *)", pre-dating any Base Architecture V3 work, which let
a background fork subagent deploy to production with ZERO confirmation
prompt despite an explicit prompt-level instruction not to -- proving
"do not do X" in a task prompt is not a security boundary when the
permission layer underneath it says yes unconditionally.

Mirrors agent/verify_claude_hooks_config.py's established pattern: reads
this machine's REAL configuration files, not a mock, and proves the
CONFIGURATION is safe, not that a human has never manually approved a
deploy through the normal interactive prompt (which remains fine --
this only catches BLANKET, no-prompt auto-allow rules for dangerous
command families).

Run: python agent/verify_claude_permissions_config.py
Exit code 0 = no dangerous blanket auto-allow rule found. Non-zero = a
real gap.
"""

import fnmatch
import json
import os
import re
import sys
from pathlib import Path

# Each pattern is matched against the raw permission-rule STRING (e.g.
# "Bash(railway up *)") using fnmatch-style globbing on the command
# portion, after stripping the "Bash(...)" wrapper. Generalizes the one
# concrete incident (railway deploy) into the real failure CLASS this is
# meant to prevent: any command family that mutates production/deployment
# state or destroys data/history should never be blanket-auto-allowed.
DANGEROUS_COMMAND_FAMILIES = {
    "railway up*": "triggers a real production deployment",
    "railway deploy*": "triggers a real production deployment",
    "railway redeploy*": "triggers a real production deployment",
    "railway domain*": "mutates production DNS/routing configuration",
    "railway variable*set*": "mutates production environment/secrets",
    "git push*--force*": "destructive history rewrite",
    "git push*-f*": "destructive history rewrite (short flag)",
    "rm -rf*": "recursive destructive delete",
    "git reset*--hard*": "discards uncommitted work irreversibly",
}

_BASH_RULE_RE = re.compile(r"^Bash\((.*)\)$")


def _project_local_settings_path() -> Path:
    return Path(__file__).resolve().parent.parent / ".claude" / "settings.local.json"


def _project_settings_path() -> Path:
    return Path(__file__).resolve().parent.parent / ".claude" / "settings.json"


def _user_settings_path() -> Path:
    return Path(os.path.expanduser("~")) / ".claude" / "settings.json"


def _load_json_safe(path: Path) -> tuple[dict, str | None]:
    if not path.exists():
        return {}, None
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return {}, f"{path} exists but is not valid JSON: {exc}"


def _check_allow_list(path: Path, allow_list: list) -> list:
    problems = []
    for rule in allow_list:
        if not isinstance(rule, str):
            continue
        match = _BASH_RULE_RE.match(rule)
        command = match.group(1) if match else rule
        for pattern, why in DANGEROUS_COMMAND_FAMILIES.items():
            if fnmatch.fnmatch(command, pattern):
                problems.append(
                    f"{path}: permission rule {rule!r} blanket-auto-allows a "
                    f"dangerous command family ({why}) with NO confirmation "
                    f"prompt -- remove it so this always requires explicit "
                    f"human approval (see AEQ-023)."
                )
    return problems


def verify() -> list:
    """Returns a list of human-readable problems found across every real
    settings file that could carry an auto-allow rule on this machine.
    Empty list means no dangerous blanket auto-allow rule exists anywhere
    checked."""
    problems = []
    for path in (_project_local_settings_path(), _project_settings_path(), _user_settings_path()):
        data, parse_error = _load_json_safe(path)
        if parse_error:
            problems.append(parse_error)
            continue
        allow_list = (data.get("permissions") or {}).get("allow") or []
        problems.extend(_check_allow_list(path, allow_list))
    return problems


if __name__ == "__main__":
    problems = verify()
    if not problems:
        print("CLAUDE PERMISSIONS CONFIG: OK -- no dangerous command family is blanket-auto-allowed.")
        sys.exit(0)
    print("CLAUDE PERMISSIONS CONFIG: PROBLEMS FOUND")
    for p in problems:
        print(f"  - {p}")
    sys.exit(1)
