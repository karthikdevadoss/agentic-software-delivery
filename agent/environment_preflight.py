"""
Environment preflight -- fail-closed verification that the JDK actually
available to `java`/the Maven wrapper is new enough for app/pom.xml's
required release target, BEFORE any real compile/test is attempted.

REAL DEFECT this exists to prevent recurring (AEQ-021, 2026-09-15): the
platform-backend's Docker image had JDK 17 installed while app/pom.xml
required Java 21 -- every real mvnw compile/test silently failed with a
Maven "release version 21 not supported" error that looked like an
ordinary build failure, not an environment problem, until a live Triage
Lab run surfaced it. Nothing distinguished "the environment is wrong"
from "the code/tests are broken."

IMPORTANT, verified directly on this dev machine (not assumed): the
correct check is detected_major >= expected_major, NEVER exact equality.
This machine's own installed JDK is 24 while app/pom.xml targets
release 21 -- javac's --release flag is designed to cross-compile for
older targets from a newer JDK, and this has been working correctly the
entire time. An equality check would have made this exact module
fail-close on a perfectly healthy setup.
"""

import os
import re
import subprocess
import time
from datetime import datetime, timezone

import tools

APP_DIR = tools.REPO_ROOT / "app"
POM_FILE = APP_DIR / "pom.xml"
MVNW = APP_DIR / ("mvnw.cmd" if os.name == "nt" else "mvnw")


class PreflightError(Exception):
    """Raised only when the preflight check itself cannot even run (e.g.
    app/pom.xml is missing entirely) -- distinct from a completed
    preflight *result* reporting ENVIRONMENT_INVALID, which is returned
    normally as a dict so callers can react to it without a try/except."""


def required_java_major_version() -> int:
    """Reads app/pom.xml's <java.version> directly -- the single source
    of truth, never a hardcoded duplicate that could drift out of sync
    (exactly the class of gap that caused AEQ-021: a Dockerfile's JDK
    version and pom.xml's target version, maintained independently,
    silently disagreeing)."""
    if not POM_FILE.exists():
        raise PreflightError(f"pom.xml not found at {POM_FILE}")
    text = POM_FILE.read_text(encoding="utf-8")
    match = re.search(r"<java\.version>(\d+)</java\.version>", text)
    if not match:
        raise PreflightError("could not find <java.version> in app/pom.xml")
    return int(match.group(1))


def _detected_java_major_version(run_fn=None):
    """Returns (major_version_or_None, raw_version_output). run_fn is
    injectable (defaults to subprocess.run) so tests can simulate any
    JDK version/absence without needing to actually install one."""
    run_fn = run_fn or subprocess.run
    try:
        proc = run_fn(["java", "-version"], capture_output=True, text=True, timeout=15, shell=False)
    except FileNotFoundError:
        return None, "java executable not found on PATH"
    except subprocess.TimeoutExpired:
        return None, "java -version timed out after 15s"
    # `java -version` prints to stderr by convention, e.g.
    # openjdk version "21.0.2" 2024-01-16 -- but some JVMs/wrappers print
    # to stdout instead, so check both rather than assuming stderr only.
    raw = (proc.stderr or "") + (proc.stdout or "")
    match = re.search(r'version "(\d+)', raw)
    if not match:
        return None, raw
    return int(match.group(1)), raw


def check_java_toolchain(run_fn=None) -> dict:
    """The single, reusable preflight check every real Java
    compile/test path (Workbench's build_tools.py, the Triage Lab's
    verify step) calls before attempting any real mvnw invocation.

    PASS condition is detected_major >= expected_major (a newer JDK can
    always cross-compile to an older --release target; only an OLDER
    JDK than required is a genuine environment failure) -- never exact
    equality, verified against this dev machine's own real JDK 24 vs.
    app/pom.xml's real target of 21.

    Returns a machine-readable result dict -- never raises for a
    genuine mismatch (that IS the correctly-detected, expected case for
    a broken environment); only raises PreflightError if the check
    itself cannot determine what's required (e.g. pom.xml missing)."""
    start = time.monotonic()
    expected = required_java_major_version()
    detected, raw = _detected_java_major_version(run_fn=run_fn)
    valid = detected is not None and detected >= expected
    return {
        "status": "ENVIRONMENT_VALID" if valid else "ENVIRONMENT_INVALID",
        "expected_java_major_minimum": expected,
        "detected_java_major": detected,
        "raw_java_version_output": raw.strip()[:500],
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "duration_ms": round((time.monotonic() - start) * 1000, 1),
    }
