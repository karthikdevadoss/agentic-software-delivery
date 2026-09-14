"""
Mechanics for the INTERNAL/GATED backend (Java/Spring) verification
scenario -- ACT-008 foundation (docs/ACTION_QUEUE.json).

Reuses agent/demo_execution.py's isolated-workspace/git/deploy machinery
wholesale (create_isolated_workspace, commit_change, push_change,
trigger_deploy, wait_for_new_deployment, cleanup_workspace, utc_now_iso
-- zero duplication of that logic, since none of it is HTML-specific).
This module adds only the two things a compiled Java/Spring change needs
that a static HTML change does not:

1. A real `mvnw compile` + targeted `mvnw test` run inside the isolated
   workspace's own app/ directory -- proving the change is not just a
   valid text substitution but genuinely compiles and behaves correctly
   BEFORE anything is ever deployed.
2. A live production API assertion (a JSON field extracted via
   backend_catalogue.extract_value_from_not_found_api_response), never a
   whole-response substring containment check.

NOT wired into any public Workbench route. See
docs/ACTION_QUEUE.json's ACT-008 entry for the exact gating status and
the full 15-point backend change contract this module was built to
satisfy, and agent/backend_acceptance.py for the one real, manually-run
end-to-end proof this foundation was verified with.
"""

import platform
import time
from pathlib import Path

import demo_execution

MAVEN_COMPILE_TIMEOUT_S = 120
MAVEN_TEST_TIMEOUT_S = 180

# The exact test classes this scenario's own change can affect --
# targeted, not the full suite, so this pipeline's runtime and evidence
# stay precisely scoped to the change actually made (CustomerServiceTest
# covers the unit-level message contract, CustomerControllerIntegrationTest
# covers the real HTTP/JSON contract via a real embedded Spring context).
RELEVANT_TEST_CLASSES = (
    "com.example.customer.service.CustomerServiceTest",
    "com.example.customer.controller.CustomerControllerIntegrationTest",
)


def _mvnw_path(app_dir: Path) -> str:
    """Windows/POSIX-correct wrapper invocation -- same convention this
    project's own CLAUDE.md documents (.\\mvnw.cmd on Windows)."""
    return str(app_dir / ("mvnw.cmd" if platform.system() == "Windows" else "mvnw"))


def run_maven_compile(app_dir: Path):
    """Real `mvnw compile` inside the isolated workspace's own app/
    directory -- never the long-lived platform-backend server's own
    checkout. Returns (ok, output)."""
    return demo_execution.run_controlled([_mvnw_path(app_dir), "compile", "-q"], app_dir, MAVEN_COMPILE_TIMEOUT_S)


def run_maven_targeted_tests(app_dir: Path, test_classes: tuple = RELEVANT_TEST_CLASSES):
    """Real `mvnw test -Dtest=...`, restricted to the exact test classes
    relevant to this scenario. Returns (ok, output)."""
    test_arg = ",".join(test_classes)
    return demo_execution.run_controlled(
        [_mvnw_path(app_dir), "test", f"-Dtest={test_arg}", "-q"], app_dir, MAVEN_TEST_TIMEOUT_S)


def assert_production_field(fetch_fn, url: str, extract_fn, expected_value: str):
    """A targeted assertion against a REAL live API response -- never a
    whole-response substring containment check.

    `fetch_fn(url)` must return (status, body_text) (the same shape as
    web_server._fetch_public_app). `extract_fn(body_text)` must return
    the one field's current value, or None if it could not be
    determined. Returns (status, body_text, live_value, matched: bool)
    -- `matched` is only ever True when live_value is not None AND
    equals expected_value exactly, so a fetch/parse failure can never be
    mistaken for a match."""
    status, body = fetch_fn(url)
    live_value = extract_fn(body) if body else None
    return status, body, live_value, live_value is not None and live_value == expected_value


def assert_production_field_with_retry(fetch_fn, url: str, extract_fn, expected_value: str,
                                        deployment_identity_confirmed: bool,
                                        max_wait_s: int = 90, poll_interval_s: int = 10):
    """Real gap found live (2026-09-14, this exact ACT-008 pipeline's
    first genuine end-to-end run, TWICE in the same run): Railway's own
    deployment record can report SUCCESS while the actual traffic-
    serving container has not yet fully replaced the old one (or is
    still mid-startup -- this project's real embedded H2/Postgres +
    Flyway + Hibernate + Actuator startup genuinely takes ~25-30s). A
    single immediate content check right after deployment-identity
    confirmation observed real, transient HTTP 502s ("Application
    failed to respond") both times, even though the real deploy had
    already reached SUCCESS and (independently re-verified moments
    later via a fresh curl) was serving the exact correct content —
    mirrors the identical real gap web_server.py's
    _verify_content_with_retry already fixed for the static demo path;
    this internal ACT-008 script predates that fix and never got it.
    Retries the SAME targeted, never-whole-response-substring assertion
    for a bounded window, but ONLY when deployment identity is already
    confirmed (a single fetch is enough when there's no real deployment
    to wait a cutover on)."""
    max_wait_s = max_wait_s if deployment_identity_confirmed else 0
    waited = 0
    while True:
        status, body, live_value, matched = assert_production_field(fetch_fn, url, extract_fn, expected_value)
        if matched or waited >= max_wait_s:
            return status, body, live_value, matched
        time.sleep(poll_interval_s)
        waited += poll_interval_s
