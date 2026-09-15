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
import environment_preflight

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

    # FAIL CLOSED (AEQ-021): never attempt a real compile/test with a JDK
    # older than app/pom.xml's own required release target -- that
    # produces a Maven error indistinguishable from a real code/test
    # defect unless this is checked FIRST and reported as its own,
    # distinct, machine-readable status.
    preflight = environment_preflight.check_java_toolchain()
    if preflight["status"] != "ENVIRONMENT_VALID":
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        metrics.record_tool_call(
            tool=f"maven_{goal}", input_summary=goal, success=False,
            duration_ms=duration_ms, result_size=0,
        )
        return {
            "goal": goal,
            "success": False,
            "status": "ENVIRONMENT_INVALID",
            "duration_ms": duration_ms,
            "output": (
                f"ENVIRONMENT_INVALID: required Java {preflight['expected_java_major_minimum']}+ "
                f"but detected {preflight['detected_java_major']!r} -- refusing to run a real "
                f"{goal} that would fail for an environment reason, not a code reason. "
                f"Raw: {preflight['raw_java_version_output']}"
            ),
            "environment_preflight": preflight,
        }

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
        "status": "VERIFIED" if success else "FAILED",
        "duration_ms": duration_ms,
        "output": output,
    }


def _record(tool_name, success, start):
    metrics.record_tool_call(
        tool=tool_name, input_summary=tool_name, success=success,
        duration_ms=round((time.monotonic() - start) * 1000, 1), result_size=0,
    )
