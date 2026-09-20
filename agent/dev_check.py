"""
Reusable, project-native test/verification runner -- CONTINUOUS
IMPROVEMENT (2026-09-13): this exact session repeatedly hand-typed the
same handful of `python -m unittest discover`/`node test_*.js`/`mvnw
test`/`railway deployment list`/`curl` invocations. This is a thin
dispatcher over those same real commands, not a new framework:

- prints exactly which real command it ran (never hides what happened)
- propagates the real subprocess exit code via sys.exit (fail closed)
- never converts a skip/timeout/error into a fabricated success
- takes zero new dependencies (stdlib only)
- contains no secrets (railway/curl calls use whatever is already
  configured in the environment; nothing is read/printed from .env)

Usage (from the repository root, or agent/ -- both resolve correctly):
    python agent/dev_check.py python-regression
    python agent/dev_check.py node-regression
    python agent/dev_check.py customer-app-tests
    python agent/dev_check.py backend-catalogue-tests [--real-maven]
    python agent/dev_check.py deployment-status
    python agent/dev_check.py production-verify
    python agent/dev_check.py verify-change [--base <ref>] [--dry-run]  # Testing Architecture V1 -- see agent/verify_change.py
    python agent/dev_check.py aggregate-evidence [--json]  # cross-run metrics over verify-change's evidence -- see agent/aggregate_evidence.py
    python agent/dev_check.py all               # python + node + customer-app-tests

Each subcommand exits 0 only on genuine success; any other outcome exits
non-zero with the real command's own output already printed above it.
"""

import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parent
APP_DIR = REPO_ROOT / "app"

PLATFORM_BACKEND_URL = "https://agentic-platform-backend-production.up.railway.app"
CUSTOMER_APP_URL = "https://agentic-delivery-customer-app-production.up.railway.app"


def _run(argv, cwd) -> int:
    print(f"$ {' '.join(argv)}   (cwd={cwd})")
    result = subprocess.run(argv, cwd=str(cwd))
    return result.returncode


def python_regression() -> int:
    return _run([sys.executable, "-m", "unittest", "discover", "-p", "test_*.py"], AGENT_DIR)


def node_regression() -> int:
    rc = 0
    for script in ("test_trainer_frontend.js", "test_usage_frontend.js", "test_learn_frontend.js"):
        rc = _run(["node", script], AGENT_DIR) or rc
    return rc


def customer_app_tests() -> int:
    mvnw = "mvnw.cmd" if sys.platform == "win32" else "mvnw"
    return _run([str(APP_DIR / mvnw), "test"], APP_DIR)


def backend_catalogue_tests(real_maven: bool = False) -> int:
    targets = ["test_backend_catalogue"]
    if real_maven:
        targets.append("test_backend_execution")
    else:
        print("(skipping the real-Maven RealMavenInIsolatedWorkspaceTestCase — pass --real-maven to include it; it runs genuine mvnw compile/test and takes real wall-clock time)")
        targets.append("test_backend_execution.ProductionFieldAssertionTestCase")
    return _run([sys.executable, "-m", "unittest", "-v", *targets], AGENT_DIR)


def deployment_status() -> int:
    """Real `railway deployment list --json` for both services this
    project deploys — never trusted alone for "is the new content really
    serving" (see production_verify), but useful for a quick real status
    read without re-deriving the exact CLI invocation each time."""
    rc = 0
    for service in ("agentic-platform-backend", "agentic-delivery-customer-app"):
        print(f"--- {service} ---")
        rc = _run(["railway", "deployment", "list", "--service", service, "--json"], REPO_ROOT) or rc
    return rc


def production_verify() -> int:
    """Real, read-only HTTP checks against both live services — an
    honest HTTP-status read, never a substitute for a targeted
    requested-effect assertion (see agent/demo_catalogue.py /
    agent/backend_catalogue.py for that)."""
    checks = [
        (f"{PLATFORM_BACKEND_URL}/workbench", 200),
        (f"{PLATFORM_BACKEND_URL}/dashboard", 200),
        (f"{PLATFORM_BACKEND_URL}/usage", 200),
        (f"{PLATFORM_BACKEND_URL}/learn", 200),
        (f"{PLATFORM_BACKEND_URL}/profile", 404),  # privacy P0 — must stay hidden
        (f"{CUSTOMER_APP_URL}/", 200),
    ]
    ok = True
    for url, expected in checks:
        status = None
        last_exc = None
        # One retry for a transient network blip (observed live this
        # session: a single TLS-handshake timeout against an otherwise-
        # healthy endpoint) — never more than one, and a genuine failure
        # after the retry is still reported honestly, not hidden.
        for attempt in range(2):
            try:
                with urllib.request.urlopen(url, timeout=15) as resp:
                    status = resp.status
                break
            except urllib.error.HTTPError as exc:
                status = exc.code
                break
            except (urllib.error.URLError, OSError) as exc:
                last_exc = exc
        if status is None:
            print(f"FAIL  {url}  -> could not connect after 2 attempts: {last_exc}")
            ok = False
            continue
        mark = "ok  " if status == expected else "FAIL"
        if status != expected:
            ok = False
        print(f"{mark}  {url}  -> HTTP {status} (expected {expected})")
    return 0 if ok else 1


def verify_change(args) -> int:
    """Delegates to agent/verify_change.py -- the selective regression
    engine (Testing Architecture V1). A thin passthrough, not a
    reimplementation, so this dispatcher stays the single place a
    developer starts from."""
    return _run([sys.executable, str(AGENT_DIR / "verify_change.py"), *args], REPO_ROOT)


def aggregate_evidence(args) -> int:
    """Delegates to agent/aggregate_evidence.py -- real cross-run metrics
    (first-pass yield, time rollup, honest insufficient-data reporting for
    cost/rework) over verify_change.py's real evidence JSON files. Same
    thin-passthrough pattern as verify_change() above."""
    return _run([sys.executable, str(AGENT_DIR / "aggregate_evidence.py"), *args], REPO_ROOT)


COMMANDS = {
    "python-regression": lambda args: python_regression(),
    "node-regression": lambda args: node_regression(),
    "customer-app-tests": lambda args: customer_app_tests(),
    "backend-catalogue-tests": lambda args: backend_catalogue_tests(real_maven="--real-maven" in args),
    "deployment-status": lambda args: deployment_status(),
    "production-verify": lambda args: production_verify(),
    "verify-change": verify_change,
    "aggregate-evidence": aggregate_evidence,
}


def run_all(args) -> int:
    rc = 0
    for name in ("python-regression", "node-regression", "customer-app-tests"):
        print(f"\n==== {name} ====")
        rc = COMMANDS[name](args) or rc
    return rc


COMMANDS["all"] = run_all


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        print(f"Available commands: {', '.join(sorted(COMMANDS))}")
        sys.exit(2)
    command = sys.argv[1]
    rc = COMMANDS[command](sys.argv[2:])
    sys.exit(rc)


if __name__ == "__main__":
    main()
