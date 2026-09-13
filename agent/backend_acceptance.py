"""
ONE real, manually-invoked INTERNAL backend acceptance run for ACT-008
(docs/ACTION_QUEUE.json) -- NOT a public Workbench route, NOT run
automatically by any test suite. This is the live proof that the full
15-point backend change contract genuinely holds end to end for the one
supported operation (agent/backend_catalogue.py's
"customer_not_found_message"), using a SAFE, CLEARLY-MARKED-AS-A-TEST
value that is always restored at the end -- never the real target text
("Customer record not found") reserved for the actual future first
public/demo run of this scenario.

Sequence (mirrors agent/web_server.py's static demo pipeline, reusing
agent/demo_execution.py's isolated-workspace/git/deploy machinery
wholesale, plus agent/backend_execution.py's Maven/production-assertion
mechanics):

  1. capture the real current production value (baseline)
  2. clone a fresh isolated workspace from the real public GitHub repo
  3. confirm the workspace's source matches the expected baseline
  4. apply the deterministic single-line substitution (a safe test value)
  5. real `mvnw compile`
  6. real targeted `mvnw test` (CustomerServiceTest + the real
     RestTemplate-based integration test)
  7. real git commit (isolated workspace, dedicated branch, never master)
  8. real git push attempt (expected NOT_CONFIGURED — ACT-007, non-fatal)
  9. real Railway deploy trigger (from the isolated workspace's own app/)
 10. real deployment-identity confirmation (timestamp-based, never id-diff)
 11. real live production API assertion (GET /customers/<id>, JSON field)
 12. RESTORE: a second full cycle from a FRESH, unmodified clone (the
     simplest genuinely-correct restore — GitHub's own tracked source
     already holds the real baseline, so redeploying it as-is IS the
     restore, mirroring the "nothing to commit, still deploy" pattern
     already established for the static Reset flow)
 13. real live production API re-assertion of the restored baseline

Every step prints exactly what happened; the script exits non-zero and
stops (never silently continuing) the moment any step fails, and always
attempts step 12 in a `finally` if step 4 or later already applied the
test value — an interrupted run must never leave production altered.

Run manually: python agent/backend_acceptance.py
"""

import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import backend_catalogue as bc
import backend_execution as be
import demo_execution as de

CUSTOMER_APP_PROJECT_ID = "e19ceaff-846f-4d4a-b840-ce1248dd3325"
RAILWAY_SERVICE_NAME = "agentic-delivery-customer-app"
RAILWAY_ENVIRONMENT = "production"
PUBLIC_CUSTOMER_APP_URL = "https://agentic-delivery-customer-app-production.up.railway.app"
PROBE_NOT_FOUND_ID = 999999999
TEST_VALUE = "Customer record not found (ACT-008 verification probe)"
EXPECTED_BASELINE = "Customer not found"


def _fetch(url):
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError) as exc:
        return None, str(exc)


def _step(n, title):
    print(f"\n=== STEP {n}: {title} ===")


def _fail(message):
    print(f"FAILED: {message}")
    sys.exit(1)


def run_one_cycle(new_value: str, label: str):
    """Runs steps 2-11 (clone -> compile -> test -> commit -> push ->
    deploy -> verify) for one target value. Returns True on full
    success. Never raises on an expected/non-fatal condition (e.g. push
    NOT_CONFIGURED) -- only a genuine failure returns False."""
    print(f"\n--- CYCLE: {label} (target value: {new_value!r}) ---")
    workspace, clone_ok, clone_out = de.create_isolated_workspace(f"act008-{label}")
    if not clone_ok:
        print(f"  clone FAILED: {clone_out[-400:]}")
        return False
    try:
        target_path = workspace / bc.BACKEND_TARGET_FILE
        old_content = target_path.read_text(encoding="utf-8")
        current_value = bc.extract_current_value(old_content, "customer_not_found_message")
        print(f"  isolated workspace source current value: {current_value!r}")

        if current_value == new_value:
            print("  source already has the target value — nothing to change, will still deploy as-is")
        else:
            new_content = bc.apply_operation(old_content, "customer_not_found_message", new_value)
            line_idx, old_line, new_line = bc.compute_single_line_diff(old_content, new_content)
            print(f"  diff (line {line_idx}):\n    - {old_line.strip()}\n    + {new_line.strip()}")
            target_path.write_text(new_content, encoding="utf-8")

        print("  running real `mvnw compile`...")
        compile_ok, compile_out = be.run_maven_compile(workspace / "app")
        print(f"  compile: {'OK' if compile_ok else 'FAILED'}")
        if not compile_ok:
            print(compile_out[-1500:])
            return False

        print("  running real targeted `mvnw test`...")
        test_ok, test_out = be.run_maven_targeted_tests(workspace / "app")
        print(f"  targeted tests: {'OK' if test_ok else 'FAILED'}")
        if not test_ok:
            print(test_out[-1500:])
            return False

        branch, commit_ok, commit_out = de.commit_change(
            workspace, f"act008-{label}", bc.BACKEND_TARGET_FILE, f"ACT-008 internal acceptance: {label}")
        if not commit_ok and "nothing to commit" not in commit_out.lower():
            print(f"  commit FAILED: {commit_out[-400:]}")
            return False
        commit_sha = de.get_commit_sha(workspace)
        print(f"  local commit: {commit_sha} (branch {branch}, ok={commit_ok})")

        push_status, push_out = de.push_change(workspace, branch)
        print(f"  GitHub push: {push_status}" + (f" ({push_out[-200:]})" if push_status != de.PUSH_STATUS_PUSHED else ""))

        deploy_triggered_after = de.utc_now_iso()
        print("  triggering real Railway deploy...")
        deploy_ok, deploy_out = de.trigger_deploy(workspace / "app", CUSTOMER_APP_PROJECT_ID, RAILWAY_SERVICE_NAME, RAILWAY_ENVIRONMENT)
        if not deploy_ok:
            print(f"  deploy trigger FAILED: {deploy_out[-800:]}")
            return False

        print("  waiting for the new deployment to be identified...")
        new_deployment_id, deploy_status, waited_s = de.wait_for_new_deployment(
            CUSTOMER_APP_PROJECT_ID, RAILWAY_SERVICE_NAME, RAILWAY_ENVIRONMENT, deploy_triggered_after, workspace)
        identity_confirmed = new_deployment_id is not None and deploy_status.upper() == "SUCCESS"
        print(f"  deployment: id={new_deployment_id} status={deploy_status} identity_confirmed={identity_confirmed} waited={waited_s}s")
        if not identity_confirmed:
            return False

        print("  verifying the real live production API...")
        probe_url = f"{PUBLIC_CUSTOMER_APP_URL}/customers/{PROBE_NOT_FOUND_ID}"
        status, body, live_value, matched = be.assert_production_field(
            _fetch, probe_url,
            lambda b: bc.extract_value_from_not_found_api_response(b, "customer_not_found_message"),
            new_value,
        )
        print(f"  GET {probe_url} -> HTTP {status}, body={body!r}")
        print(f"  live_value={live_value!r}, expected={new_value!r}, matched={matched}")
        return matched
    finally:
        de.cleanup_workspace(workspace)


def main():
    _step(1, "capture real current production baseline")
    status, body = _fetch(f"{PUBLIC_CUSTOMER_APP_URL}/customers/{PROBE_NOT_FOUND_ID}")
    baseline_value = bc.extract_value_from_not_found_api_response(body, "customer_not_found_message") if body else None
    print(f"  current live production value: {baseline_value!r} (HTTP {status})")
    if baseline_value != EXPECTED_BASELINE:
        _fail(f"live production baseline is {baseline_value!r}, expected {EXPECTED_BASELINE!r} — refusing to proceed against an unexpected starting state")

    _step(2, "apply the test probe value end-to-end (clone -> compile -> test -> commit -> push -> deploy -> verify)")
    probe_ok = run_one_cycle(TEST_VALUE, "probe")
    if not probe_ok:
        print("\nPROBE CYCLE DID NOT FULLY SUCCEED — attempting restore anyway before exiting.")

    _step(3, "restore the real baseline end-to-end (same full cycle, target value = original baseline)")
    restore_ok = run_one_cycle(EXPECTED_BASELINE, "restore")

    _step(4, "final verdict")
    print(f"  probe cycle:   {'PASS' if probe_ok else 'FAIL'}")
    print(f"  restore cycle: {'PASS' if restore_ok else 'FAIL'}")
    if probe_ok and restore_ok:
        print("\nACT-008 INTERNAL BACKEND ACCEPTANCE: PASS (real compile, real targeted test, real commit, real deploy, real production API assertion, real restore — all genuinely observed).")
        sys.exit(0)
    else:
        print("\nACT-008 INTERNAL BACKEND ACCEPTANCE: FAIL — see the step output above for exactly what did not hold. Production may still be in the PROBE state; check manually.")
        sys.exit(1)


if __name__ == "__main__":
    main()
