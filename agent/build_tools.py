"""
V4 controlled compile/test tool.

Deliberately NOT a general shell/command tool. Only two fixed operations
are possible (Maven compile, Maven test on the Customer app), selected by
an exact allowlist match — there is no way to pass an arbitrary command
string through this module. subprocess.run() is always called with an
explicit argv list, never shell=True, so no shell metacharacters in any
input could ever be interpreted.
"""

import os
import subprocess
import time

import tools
import metrics

APP_DIR = tools.REPO_ROOT / "app"
MVNW = APP_DIR / ("mvnw.cmd" if os.name == "nt" else "mvnw")

ALLOWED_GOALS = ("compile", "test")
MAX_OUTPUT_CHARS = 4000
DEFAULT_TIMEOUT_SECONDS = 300


class BuildToolError(Exception):
    """Raised for any safely-reportable build-tool failure. Never crashes
    the caller, never runs an unvalidated command."""


def run_maven(goal: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> dict:
    start = time.monotonic()

    if goal not in ALLOWED_GOALS:
        _record(f"maven_{goal}", False, start)
        raise BuildToolError(f"goal not allowed: {goal!r} (allowed: {ALLOWED_GOALS})")
    if not MVNW.exists():
        _record(f"maven_{goal}", False, start)
        raise BuildToolError(f"Maven wrapper not found at {MVNW}")

    try:
        proc = subprocess.run(
            [str(MVNW), "-q", goal],
            cwd=str(APP_DIR),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )
        success = proc.returncode == 0
        raw_output = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        success = False
        raw_output = f"timed out after {timeout_seconds}s"

    truncated = len(raw_output) > MAX_OUTPUT_CHARS
    output = raw_output[:MAX_OUTPUT_CHARS] + ("\n...(truncated)" if truncated else "")

    duration_ms = round((time.monotonic() - start) * 1000, 1)
    metrics.record_tool_call(
        tool=f"maven_{goal}", input_summary=goal, success=success,
        duration_ms=duration_ms, result_size=len(raw_output), truncated=truncated,
    )

    return {
        "goal": goal,
        "success": success,
        "duration_ms": duration_ms,
        "output": output,
    }


def _record(tool_name, success, start):
    metrics.record_tool_call(
        tool=tool_name, input_summary=tool_name, success=success,
        duration_ms=round((time.monotonic() - start) * 1000, 1), result_size=0,
    )
