"""
Focused regression tests for agent/web_server.py's SSE terminal-state
logic — the exact bug behind incident trainer-209e94e7 (2026-09-10): a
run reached the newly-introduced NO_CHANGE_NEEDED status, but
stream_events()'s termination check only recognized COMPLETED/FAILED,
so the SSE generator never broke out of its poll loop and the browser's
EventSource sat open forever with nothing new arriving after the
terminal event, staying stuck at STARTING. See
knowledge/sessions/2026-09-10-trainer-idempotency-fix.md (Addendum section).

Run: python agent/test_web_server.py
"""

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import web_server as ws

# This file's Run(...) instantiations now also trigger a real write-through
# call to agent/event_ledger.py (a run_started event + a real git subprocess
# call for git_commit_before). That's correct production behavior, but it
# would make this otherwise-fast, offline SSE/status test suite silently
# depend on network reachability to the live Postgres ledger and write
# dozens of synthetic "test-run" rows into real durable evidence on every
# test run. Event-ledger correctness has its own dedicated, real-DB-backed
# suite (test_event_ledger.py) — here it's simply patched to a no-op so
# this file keeps testing exactly what its name says: web_server's SSE/
# status logic, nothing else.
_event_ledger_patcher = None


def setUpModule():
    global _event_ledger_patcher
    _event_ledger_patcher = mock.patch.object(
        ws.event_ledger, "record_event",
        return_value={"event_id": "patched-out-in-tests", "remote_persisted": False})
    _event_ledger_patcher.start()


def tearDownModule():
    _event_ledger_patcher.stop()


async def _always_connected():
    return False


async def _consume(agen, timeout=2.0):
    """Drains an async generator with a hard timeout. If the generator's
    termination logic regresses to not recognizing a real terminal
    run.status, this raises asyncio.TimeoutError (a fast, clear test
    failure) instead of hanging the test suite forever — which is
    exactly what the real bug did to the browser's EventSource."""
    events = []

    async def _drain():
        async for evt in agen:
            events.append(evt)

    await asyncio.wait_for(_drain(), timeout=timeout)
    return events


class TerminalStateDefinitionTestCase(unittest.TestCase):
    """Every run.status value actually assigned anywhere in web_server.py
    must be classified correctly — in-progress stages must NOT be treated
    as terminal (that would cut a live run's stream short), and every
    real terminal outcome must be."""

    IN_PROGRESS_STATES = [
        "PLANNING", "REPOSITORY INVESTIGATION", "WAITING FOR HUMAN APPROVAL",
        "PROPOSING CHANGE", "APPLYING CHANGE", "BUILDING", "TESTING",
        "COMMITTING", "DEPLOYING", "VERIFYING PRODUCTION",
    ]
    TERMINAL_STATES = ["COMPLETED", "FAILED", "NO_CHANGE_NEEDED", "DEPLOYMENT_STATUS_UNKNOWN"]

    def _run_with_status(self, status):
        run = ws.Run("test-run", "test requirement")
        run.status = status
        return run

    def test_every_in_progress_state_is_not_terminal(self):
        for status in self.IN_PROGRESS_STATES:
            with self.subTest(status=status):
                self.assertFalse(ws._run_is_terminal(self._run_with_status(status)))

    def test_every_terminal_state_is_terminal(self):
        for status in self.TERMINAL_STATES:
            with self.subTest(status=status):
                self.assertTrue(ws._run_is_terminal(self._run_with_status(status)))


class SSEStreamTerminatesOnTerminalStateTestCase(unittest.IsolatedAsyncioTestCase):
    async def _run_to_status(self, status):
        run = ws.Run("test-run", "test requirement")
        run.emit("stage", {"stage": status})
        run.status = status
        return run

    async def test_no_change_needed_terminates_the_stream(self):
        """The exact real-incident regression: before the fix, this status
        was missing from the terminal-state check, so this generator would
        loop forever (await asyncio.sleep(0.3) indefinitely) instead of
        ending — _consume's timeout turns that hang into a clean failure."""
        run = await self._run_to_status("NO_CHANGE_NEEDED")
        events = await _consume(ws._generate_run_events(run, _always_connected))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "stage")

    async def test_completed_terminates_the_stream(self):
        run = await self._run_to_status("COMPLETED")
        events = await _consume(ws._generate_run_events(run, _always_connected))
        self.assertEqual(len(events), 1)

    async def test_failed_terminates_the_stream(self):
        run = await self._run_to_status("FAILED")
        events = await _consume(ws._generate_run_events(run, _always_connected))
        self.assertEqual(len(events), 1)

    async def test_in_progress_state_does_not_terminate_the_stream(self):
        """A run still in a real in-progress stage must NOT cause the
        stream to end — only client disconnect or a terminal run.status
        may do that. Proven here via the disconnect path, since letting
        this genuinely poll forever would hang the test."""
        run = await self._run_to_status("BUILDING")

        calls = {"n": 0}

        async def disconnect_after_two_polls():
            calls["n"] += 1
            return calls["n"] > 2  # let it poll a couple of times, then end the test

        events = await _consume(ws._generate_run_events(run, disconnect_after_two_polls))
        self.assertEqual(len(events), 1)  # the one real event, not more, not fewer
        self.assertGreater(calls["n"], 2)  # proves it actually kept polling, not exited on the terminal check


class SubprocessEncodingTestCase(unittest.TestCase):
    """Regression tests for incident trainer-e8ed222c (2026-09-10): Railway
    CLI output is genuine UTF-8 (confirmed byte-for-byte — its "●" status
    bullet is U+25CF, encoded as E2 97 8F), but _run_controlled() called
    subprocess.run(text=True) with no explicit encoding, which on this
    Windows machine defaults to cp1252 — undefined for byte 0x8F, the
    last byte of that exact sequence. Uses the real Python interpreter
    running these tests as a controlled subprocess to produce exact,
    real byte sequences — not a mock of subprocess.run's behavior."""

    def _run_snippet(self, code):
        return ws._run_controlled([sys.executable, "-c", code], ".", 15)

    def test_a_ordinary_ascii_output_decodes_correctly(self):
        ok, out = self._run_snippet("print('Online')")
        self.assertTrue(ok)
        self.assertIn("Online", out)

    def test_b_unicode_status_bullet_decodes_correctly(self):
        # The exact real character from Railway's own "● Online" line.
        ok, out = self._run_snippet(
            "import sys; sys.stdout.buffer.write('\\u25cf Online'.encode('utf-8'))")
        self.assertTrue(ok)
        self.assertIn("● Online", out)

    def test_c_unicode_divider_line_decodes_correctly(self):
        # The horizontal rule Railway prints between sections.
        ok, out = self._run_snippet(
            "import sys; sys.stdout.buffer.write(('\\u2500' * 10).encode('utf-8'))")
        self.assertTrue(ok)
        self.assertEqual(out, "─" * 10)

    def test_g_the_real_problem_byte_is_genuinely_undefined_under_cp1252(self):
        """Confirms WHY the fix is needed, not just that it works: the
        exact byte that crashed (0x8F, from encoding U+25CF as UTF-8)
        has no mapping in cp1252 at all — this isn't a niche edge case,
        it's the codepage Windows would silently fall back to without
        the explicit encoding="utf-8" this function now passes."""
        raw_utf8_bytes = "●".encode("utf-8")
        self.assertEqual(raw_utf8_bytes, b"\xe2\x97\x8f")
        with self.assertRaises(UnicodeDecodeError):
            raw_utf8_bytes.decode("cp1252")


class DeploymentOutcomeDecisionTestCase(unittest.TestCase):
    """Regression tests for _decide_deployment_outcome — the exact
    decision that mislabeled 3 genuinely successful deploys as FAILED
    this session because it trusted CLI polling as the sole verdict."""

    def test_d_explicit_cli_failure_with_unreachable_production_is_failed(self):
        self.assertEqual(
            ws._decide_deployment_outcome(deploy_online=False, deploy_explicit_failure=True, production_verified=False),
            "FAILED")

    def test_e_poll_timeout_with_no_production_confirmation_is_unknown_not_failed(self):
        self.assertEqual(
            ws._decide_deployment_outcome(deploy_online=False, deploy_explicit_failure=False, production_verified=False),
            "DEPLOYMENT_STATUS_UNKNOWN")

    def test_f_cli_confirmed_online_and_production_verified_is_completed(self):
        self.assertEqual(
            ws._decide_deployment_outcome(deploy_online=True, deploy_explicit_failure=False, production_verified=True),
            "COMPLETED")

    def test_g_production_verified_overrides_cli_never_confirming_online(self):
        """The exact real incident's shape: CLI polling timed out
        (deploy_online=False — it never saw "Online" due to the encoding
        crash), but production was genuinely reachable and correct. A
        decoding/timeout problem must never become a false failure."""
        self.assertEqual(
            ws._decide_deployment_outcome(deploy_online=False, deploy_explicit_failure=False, production_verified=True),
            "COMPLETED")

    def test_h_verified_production_cannot_coexist_with_failed_even_if_cli_disagrees(self):
        # Production verification succeeding must never be overridden,
        # even by a contradictory explicit CLI failure signal.
        self.assertEqual(
            ws._decide_deployment_outcome(deploy_online=False, deploy_explicit_failure=True, production_verified=True),
            "COMPLETED")

    def test_h_cli_saying_online_is_not_sufficient_without_production_verification(self):
        self.assertEqual(
            ws._decide_deployment_outcome(deploy_online=True, deploy_explicit_failure=False, production_verified=False),
            "DEPLOYMENT_STATUS_UNKNOWN")

    def test_old_behavior_would_have_failed_this_exact_real_scenario(self):
        """Proves the fix against the OLD logic, not just in isolation.
        Old code: `if not deploy_online: FAILED` — unconditional, with no
        production-verification override at all."""
        deploy_online = False  # what the real incident actually saw
        old_result = "FAILED" if not deploy_online else "COMPLETED"
        new_result = ws._decide_deployment_outcome(
            deploy_online=False, deploy_explicit_failure=False, production_verified=True)
        self.assertEqual(old_result, "FAILED")
        self.assertEqual(new_result, "COMPLETED")
        self.assertNotEqual(old_result, new_result)


class PublicRouteStructureTestCase(unittest.TestCase):
    """Regression lock for TRAINER PREVIEW V1's route structure — the
    exact 5 public surfaces (Workbench/Dashboard/Usage/Learn/Profile),
    retired-terminology redirects, and the still-reachable internal
    Control Plane. Protects against a future change silently dropping a
    public route or re-breaking a retired-terminology link."""

    def _route_map(self):
        return {r.path: r for r in ws.routes if hasattr(r, "path")}

    def test_all_five_public_surfaces_are_registered_get_routes(self):
        routes = self._route_map()
        for path in ("/", "/workbench", "/dashboard", "/usage", "/learn", "/profile"):
            self.assertIn(path, routes, f"{path} is not registered")
            self.assertIn("GET", routes[path].methods)

    def test_root_and_workbench_serve_the_same_handler(self):
        routes = self._route_map()
        self.assertIs(routes["/"].endpoint, routes["/workbench"].endpoint)
        self.assertIs(routes["/"].endpoint, ws.workbench_page)

    def test_retired_terminology_redirects_not_dead_links(self):
        routes = self._route_map()
        self.assertIn("/trainer", routes)
        self.assertIn("/sessions", routes)
        self.assertIs(routes["/trainer"].endpoint, ws.redirect_trainer_to_workbench)
        self.assertIs(routes["/sessions"].endpoint, ws.redirect_sessions_to_usage)

    def test_control_plane_still_reachable_but_not_a_public_surface_name(self):
        routes = self._route_map()
        self.assertIn("/control-plane", routes)
        self.assertIs(routes["/control-plane"].endpoint, ws.control_plane_page)
        # The 5 public surface paths must never include internal-tool naming.
        for public_path in ("/", "/workbench", "/dashboard", "/usage", "/learn", "/profile"):
            self.assertNotIn("control-plane", public_path)


class TargetApplicationTestCase(unittest.IsolatedAsyncioTestCase):
    """Section 1 of the Workbench target-app/cost-transparency task: the
    trainer must be shown which real application a requirement targets,
    before submitting anything, via a single backend-owned source of
    truth (never a second hardcoded copy of the URL in the frontend)."""

    def test_target_app_route_is_registered(self):
        routes = {r.path: r for r in ws.routes if hasattr(r, "path")}
        self.assertIn("/api/target-app", routes)
        self.assertIn("GET", routes["/api/target-app"].methods)

    async def test_target_app_payload_has_the_required_fields(self):
        response = await ws.get_target_app(mock.Mock())
        body = json.loads(response.body)
        for key in ("name", "url", "environment", "description"):
            self.assertIn(key, body)

    async def test_target_app_url_matches_the_real_deploy_verification_url(self):
        """Same constant used for the actual deploy/verification path
        (_fetch_public_app) — never a second, independently-typed URL that
        could silently drift from what the backend actually operates on."""
        response = await ws.get_target_app(mock.Mock())
        body = json.loads(response.body)
        self.assertEqual(body["url"], ws.PUBLIC_CUSTOMER_APP_URL)
        self.assertTrue(body["url"].startswith("https://"))


class PreRunEstimateTestCase(unittest.IsolatedAsyncioTestCase):
    """Section 2: an ESTIMATED (never fabricated-precision) token/cost
    range must be produced before execution for an auto-execute
    requirement, and a thin/missing estimate must never block a safe
    TINY/LOW auto-execute run."""

    async def test_assess_route_attaches_an_estimate_for_auto_decisions(self):
        request = mock.Mock()
        request.json = mock.AsyncMock(return_value={"requirement": 'Add a small "Agent Demo" status badge'})
        response = await ws.assess_trainer_requirement(request)
        body = json.loads(response.body)
        self.assertEqual(body["decision"], "auto")
        self.assertIn("estimate", body)
        self.assertTrue(body["estimate"]["available"])
        self.assertIn(body["estimate"]["confidence"], ("LOW", "MEDIUM", "HIGH"))

    async def test_assess_route_never_estimates_a_blocked_requirement(self):
        request = mock.Mock()
        request.json = mock.AsyncMock(return_value={"requirement": "Change the login password hashing scheme"})
        response = await ws.assess_trainer_requirement(request)
        body = json.loads(response.body)
        self.assertEqual(body["decision"], "blocked")
        self.assertNotIn("estimate", body)  # nothing to estimate — it will never execute

    async def test_missing_estimate_never_blocks_a_safe_auto_execute_run(self):
        """Direct test of the exact requirement: 'Do not prevent a safe
        TINY/LOW request from running only because an estimate is
        unavailable.' Forces estimation to report ESTIMATE NOT AVAILABLE
        and proves start_trainer_run still creates and starts a real run
        for an auto-decision requirement."""
        with mock.patch.object(ws.estimation, "estimate_run",
                                return_value={"available": False, "reason": "ESTIMATE NOT AVAILABLE — test", "method_version": "test"}), \
             mock.patch.object(ws.threading, "Thread") as mock_thread:
            request = mock.Mock()
            request.json = mock.AsyncMock(return_value={"requirement": 'Add a small "Agent Demo" status badge'})
            response = await ws.start_trainer_run(request)
            body = json.loads(response.body)
            self.assertFalse(body["blocked"])
            self.assertIn("run_id", body)
            self.assertFalse(body["assessment"]["estimate"]["available"])
            # The run genuinely started despite the unavailable estimate.
            # (threading.Thread is also used internally by subprocess.run's
            # reader threads for the run's own `git rev-parse` call, so
            # assert on the specific call rather than call count.)
            trainer_thread_calls = [
                c for c in mock_thread.call_args_list
                if c.kwargs.get("target") is ws._run_trainer_thread
            ]
            self.assertEqual(len(trainer_thread_calls), 1)


class ActualUsageSummaryTestCase(unittest.TestCase):
    """Section 3: actual (never estimated) usage must be reported for
    every terminal outcome when real usage exists, and truthfully
    reported as not captured when it doesn't — never fabricated."""

    def setUp(self):
        ws.metrics.reset()

    def tearDown(self):
        ws.metrics.reset()

    def test_no_api_calls_reports_not_captured(self):
        summary = ws._build_usage_summary(usage_start_index=0)
        self.assertFalse(summary["captured"])

    def test_real_usage_is_aggregated_and_priced(self):
        start_index = len(ws.metrics.get_model_usage_events())
        ws.metrics.record_model_usage(
            provider="anthropic", model="claude-sonnet-5",
            input_tokens=1000, output_tokens=500,
            cache_creation_input_tokens=100, cache_read_input_tokens=200,
        )
        summary = ws._build_usage_summary(start_index)
        self.assertTrue(summary["captured"])
        self.assertEqual(summary["input_tokens"], 1000)
        self.assertEqual(summary["output_tokens"], 500)
        self.assertEqual(summary["cache_write_tokens"], 100)
        self.assertEqual(summary["cache_read_tokens"], 200)
        self.assertTrue(summary["cost_available"])
        self.assertGreater(summary["cost_usd"], 0)
        self.assertEqual(summary["pricing_version"], ws.pricing_config.PRICING_VERSION)

    def test_usage_summary_maps_to_a_canonical_ledger_event_type(self):
        self.assertEqual(ws._canonical_event_type("usage_summary", {}), "run_usage_summary")

    def test_unpriced_model_reports_cost_unavailable_not_zero(self):
        start_index = len(ws.metrics.get_model_usage_events())
        ws.metrics.record_model_usage(provider="anthropic", model="claude-nonexistent-9", input_tokens=100, output_tokens=50)
        summary = ws._build_usage_summary(start_index)
        self.assertTrue(summary["captured"])
        self.assertFalse(summary["cost_available"])
        self.assertIsNone(summary["cost_usd"])


class EstimateErrorTestCase(unittest.TestCase):
    """Section 5: a run's own estimate vs. its real captured usage should
    be comparable for future estimate-accuracy measurement, and this
    comparison must never be fabricated when there's nothing real to
    compare against."""

    def test_no_usage_captured_means_no_estimate_error(self):
        run = ws.Run("test-run", "test requirement")
        self.assertIsNone(ws._estimate_error(run, {"captured": False}))

    def test_no_prior_estimate_means_no_estimate_error(self):
        run = ws.Run("test-run", "test requirement")
        run.emit("risk_assessment", {"complexity": "TINY", "risk": "LOW"})  # no "estimate" key
        self.assertIsNone(ws._estimate_error(run, {"captured": True, "input_tokens": 1000, "output_tokens": 500}))

    def test_real_comparison_is_produced_when_both_exist(self):
        run = ws.Run("test-run", "test requirement")
        run.emit("risk_assessment", {
            "complexity": "TINY", "risk": "LOW",
            "estimate": {"available": True, "estimated_total_tokens_range": [1000, 2000], "method_version": "test-v1"},
        })
        result = ws._estimate_error(run, {"captured": True, "input_tokens": 1000, "output_tokens": 500})
        self.assertEqual(result["actual_total_tokens"], 1500)
        self.assertTrue(result["within_estimated_range"])
        self.assertEqual(result["estimate_method_version"], "test-v1")


class RepositoryWorkspaceReadyTestCase(unittest.TestCase):
    """Regression tests for real production incident trainer-6aedf022
    (2026-09-10): `railway up` does not upload .git, so a source-mutating
    run reached COMMITTING — after real API cost was spent — before
    discovering there was no usable git repository at all. The
    workspace must be verified BEFORE the agent loop runs, not after."""

    def test_real_repository_on_this_machine_is_ready(self):
        """This dev checkout has a real .git — sanity-checks the positive
        path isn't itself broken."""
        result = ws._check_repository_workspace_ready()
        self.assertTrue(result["ready"])
        self.assertTrue(result["checks"]["git_repository_usable"])
        self.assertTrue(result["checks"]["head_resolvable"])

    def test_missing_git_repository_is_detected_not_assumed(self):
        """Reproduces the exact real incident: a directory with real
        source files but genuinely no .git anywhere up the tree."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp)
            (fake_root / "app" / "src").mkdir(parents=True)
            with mock.patch.object(ws, "REPO_ROOT", fake_root), \
                 mock.patch.object(ws, "APP_DIR", fake_root / "app"):
                result = ws._check_repository_workspace_ready()
                self.assertFalse(result["ready"])
                self.assertFalse(result["checks"]["git_repository_usable"])

    def test_trainer_thread_fails_before_touching_source_when_workspace_not_ready(self):
        """The exact required behavior: FAIL BEFORE MODIFYING SOURCE.
        run_agent_loop must never even be called when the precondition
        fails — proves zero source mutation was attempted, not just that
        the final status happens to say FAILED."""
        run = ws.Run("test-run", "test requirement")
        run.trainer_usage_start_index = 0
        with mock.patch.object(ws, "_check_repository_workspace_ready",
                                return_value={"ready": False, "checks": {"git_repository_usable": False}}), \
             mock.patch.object(ws, "_fetch_public_app", return_value=(200, "<html></html>")), \
             mock.patch("web_server.run_agent_loop") as mock_agent_loop:
            ws._run_trainer_thread(run, "some requirement", {"complexity": "TINY", "risk": "LOW"})
        mock_agent_loop.assert_not_called()
        self.assertEqual(run.status, "FAILED")
        error_event = next(e for e in run.events if e["type"] == "error")
        self.assertIn("REPOSITORY_WORKSPACE_READY", error_event["message"])


class TestApplicabilityGateTestCase(unittest.TestCase):
    """Regression tests for the real observed defect: Testing did not
    visibly reach PASS before Commit. Root cause: an empty test_events
    list was silently treated as 'tests passed.' Must now be an explicit,
    truthful decision keyed off a real fact (does app/src/test/java have
    any test files at all right now), never a silent default."""

    def test_real_app_test_directory_reflects_actual_repo_state(self):
        """Sanity-checks the real fact this repo currently has, so the
        rest of this task's tests aren't built on an assumption."""
        test_dir = ws.APP_DIR / "src" / "test" / "java"
        has_real_tests = test_dir.is_dir() and any(test_dir.rglob("*.java"))
        self.assertEqual(ws._tests_applicable(), has_real_tests)

    def test_tests_not_applicable_when_no_test_files_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_app_dir = Path(tmp) / "app"
            (fake_app_dir / "src" / "test" / "java").mkdir(parents=True)
            with mock.patch.object(ws, "APP_DIR", fake_app_dir):
                self.assertFalse(ws._tests_applicable())

    def test_tests_applicable_when_a_real_test_file_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_app_dir = Path(tmp) / "app"
            test_dir = fake_app_dir / "src" / "test" / "java"
            test_dir.mkdir(parents=True)
            (test_dir / "SomeTest.java").write_text("class SomeTest {}", encoding="utf-8")
            with mock.patch.object(ws, "APP_DIR", fake_app_dir):
                self.assertTrue(ws._tests_applicable())


class PublicRouteRedirectTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_trainer_redirects_to_workbench(self):
        response = await ws.redirect_trainer_to_workbench(mock.Mock())
        self.assertEqual(response.headers["location"], "/workbench")
        self.assertEqual(response.status_code, 308)

    async def test_sessions_redirects_to_usage(self):
        response = await ws.redirect_sessions_to_usage(mock.Mock())
        self.assertEqual(response.headers["location"], "/usage")
        self.assertEqual(response.status_code, 308)


if __name__ == "__main__":
    unittest.main()
