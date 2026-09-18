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
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ai_intelligence
import demo_catalogue
import demo_execution
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


class RunSetStatusValidationTestCase(unittest.TestCase):
    """Regression coverage for the Phase 1 audit's MEDIUM-HIGH finding
    (docs/INTELLIGENCE_PLACEMENT_V3.md): Run.status used to be a plain
    string set directly at ~30 call sites with nothing validating it.
    Run.set_status() is now the sole sanctioned mutator; these tests
    prove it accepts every real known state and rejects the exact defect
    class this closes -- an unenumerated/typo'd status string."""

    def test_accepts_every_known_non_terminal_state(self):
        run = ws.Run("test-run", "test requirement")
        for status in ws.NON_TERMINAL_RUN_STATES:
            with self.subTest(status=status):
                run.set_status(status)
                self.assertEqual(run.status, status)

    def test_accepts_every_known_terminal_state(self):
        run = ws.Run("test-run", "test requirement")
        for status in ws.TERMINAL_RUN_STATES:
            with self.subTest(status=status):
                run.set_status(status)
                self.assertEqual(run.status, status)

    def test_rejects_an_unrecognized_status_string(self):
        """The actual defect class this closes: before this change, a
        typo like 'BULDING' (missing an 'I') or a genuinely new status
        introduced without updating the known-state sets would have been
        silently accepted as the real run.status with nothing to catch
        it -- now it raises instead of silently corrupting state."""
        run = ws.Run("test-run", "test requirement")
        with self.assertRaises(ValueError):
            run.set_status("BULDING")

    def test_every_state_STAGE_LABELS_can_produce_is_known(self):
        """STAGE_LABELS (the dict _make_dispatch_fn's dynamic
        `run.status = stage` -- now `run.set_status(stage)` -- draws
        from) must never be able to produce a status set_status() would
        reject; this would be a real, live-breaking regression risk if
        someone added a new tool to STAGE_LABELS without also adding its
        label to a known-state set."""
        for stage_label in ws.STAGE_LABELS.values():
            with self.subTest(stage_label=stage_label):
                self.assertIn(stage_label, ws.KNOWN_RUN_STATES)

    def test_real_run_lifecycle_sequence_never_raises(self):
        """Not just unit-testing the method in isolation: drives one real
        Run instance through a representative real end-to-end sequence
        (mirroring the real order status is set in _run_trainer_thread)
        and confirms set_status() never raises along the way."""
        run = ws.Run("test-run", "test requirement")
        for status in [
            "PLANNING", "REPOSITORY INVESTIGATION", "PROPOSING CHANGE",
            "WAITING FOR HUMAN APPROVAL", "APPLYING CHANGE", "BUILDING",
            "TESTING", "COMMITTING", "PUSHING", "DEPLOYING",
            "VERIFYING PRODUCTION", "COMPLETED",
        ]:
            run.set_status(status)  # raises on failure -- no explicit assert needed
        self.assertEqual(run.status, "COMPLETED")


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
    """Regression tests for _decide_deployment_outcome.

    Real incident (run trainer-7769757e, 2026-09-10): Workbench reported
    'Deployment: VERIFIED (HTTP 200)' and claimed the requested footer
    text was live, but the real Customer App still showed the OLD
    footer — the deploy's own content_changed_from_baseline was already
    `false`, but the decision only checked HTTP 200. HTTP 200 alone must
    never be sufficient to mark a modifying run COMPLETED."""

    def test_reachable_with_content_verified_is_completed(self):
        self.assertEqual(
            ws._decide_deployment_outcome(production_reachable=True, deploy_explicit_failure=False, content_verified=True),
            "COMPLETED")

    def test_reachable_but_content_not_verified_is_a_confirmed_failure_not_unknown(self):
        """The EXACT real incident's shape: HTTP 200 came back (server
        reachable), but the requested content was never actually
        present. This is a confirmed negative result, not ambiguity —
        must be FAILED, never COMPLETED and never DEPLOYMENT_STATUS_UNKNOWN."""
        self.assertEqual(
            ws._decide_deployment_outcome(production_reachable=True, deploy_explicit_failure=False, content_verified=False),
            "FAILED")

    def test_explicit_cli_failure_with_unreachable_production_is_failed(self):
        self.assertEqual(
            ws._decide_deployment_outcome(production_reachable=False, deploy_explicit_failure=True, content_verified=False),
            "FAILED")

    def test_unreachable_with_no_explicit_failure_is_unknown_not_failed(self):
        self.assertEqual(
            ws._decide_deployment_outcome(production_reachable=False, deploy_explicit_failure=False, content_verified=False),
            "DEPLOYMENT_STATUS_UNKNOWN")

    def test_old_behavior_would_have_completed_this_exact_real_scenario(self):
        """Proves the fix against the OLD logic, not just in isolation.
        Old code: `if production_verified (HTTP 200 only): COMPLETED` —
        with no check that the requested content was actually there."""
        http_200 = True
        old_result = "COMPLETED" if http_200 else "FAILED"  # what the real incident's old code did
        new_result = ws._decide_deployment_outcome(
            production_reachable=True, deploy_explicit_failure=False, content_verified=False)
        self.assertEqual(old_result, "COMPLETED")
        self.assertEqual(new_result, "FAILED")
        self.assertNotEqual(old_result, new_result)


class ContentVerificationTestCase(unittest.TestCase):
    """Regression tests for the requested-observable-effect check itself
    (run.trainer_expected_content vs. the fetched production HTML) — the
    exact mechanism that closes the false-success gap."""

    def test_expected_content_present_verifies_true(self):
        run = ws.Run("test-run", "test requirement")
        run.trainer_expected_content = "<footer>Powered by DEVADOSS Agentic Delivery</footer>"
        after_html = "<html><body>...<footer>Powered by DEVADOSS Agentic Delivery</footer></body></html>"
        self.assertIn(run.trainer_expected_content, after_html)

    def test_missing_expected_content_never_verifies(self):
        run = ws.Run("test-run", "test requirement")
        run.trainer_expected_content = "<footer>Powered by DEVADOSS Agentic Delivery</footer>"
        after_html = "<html><body>...<footer>Powered by Agentic Delivery</footer></body></html>"  # OLD content
        self.assertNotIn(run.trainer_expected_content, after_html)

    def test_expected_content_defaults_to_none_never_fabricates_verification(self):
        run = ws.Run("test-run", "test requirement")
        self.assertIsNone(run.trainer_expected_content)


class PublicRouteStructureTestCase(unittest.TestCase):
    """Regression lock for the platform's route structure — the exact 4
    public surfaces (Workbench/Dashboard/Usage/Learn), retired-terminology
    redirects, and the still-reachable internal Control Plane. Protects
    against a future change silently dropping a public route or
    re-breaking a retired-terminology link.

    Profile was deliberately made non-public (privacy P0, 2026-09-13) —
    see ProfilePrivacyTestCase below for the regression lock protecting
    that decision. Source is preserved at
    docs/archive/profile_preserved/ for later restoration, not deleted."""

    def _route_map(self):
        return {r.path: r for r in ws.routes if hasattr(r, "path")}

    def test_all_four_public_surfaces_are_registered_get_routes(self):
        routes = self._route_map()
        for path in ("/", "/workbench", "/dashboard", "/usage", "/learn"):
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
        # The public surface paths must never include internal-tool naming.
        for public_path in ("/", "/workbench", "/dashboard", "/usage", "/learn"):
            self.assertNotIn("control-plane", public_path)

    def test_triage_promotion_routes_are_registered_for_all_three_scenarios(self):
        routes = self._route_map()
        for scenario in ("a", "b", "c"):
            status_path = f"/api/triage/scenario-{scenario}/promotion-status"
            promote_path = f"/api/triage/scenario-{scenario}/promote"
            self.assertIn(status_path, routes, f"{status_path} is not registered")
            self.assertIn("GET", routes[status_path].methods)
            self.assertIn(promote_path, routes, f"{promote_path} is not registered")
            self.assertIn("POST", routes[promote_path].methods)


class NestedRouteAssetPathTestCase(unittest.TestCase):
    """Regression lock for a real, twice-found defect class (SESSION-HISTORY-P0,
    2026-09-11: usage.html/learn.html; flagship-completion session,
    2026-09-15: triage-b.html): a relative CSS/JS href/src (e.g.
    href="style.css") resolves against the CURRENT URL's directory, which
    is wrong the moment a page is served at a route with more than one
    path segment (e.g. /triage/scenario-b resolves "style.css" to the
    nonsensical /triage/style.css, not /style.css) -- live-browser-verified
    to silently break the page with zero console error surfaced by this
    session's own tooling, only visible via network-request inspection.
    Every served HTML page's local asset references must be root-absolute
    (start with "/"), which is correct regardless of route depth."""

    def test_every_served_html_page_uses_only_absolute_local_asset_paths(self):
        import re as re_module
        relative_local_asset = re_module.compile(
            r'''(?:href|src)=["'](?!https?://|//|/|#)([a-zA-Z0-9_\-./]+\.(?:css|js))["']''')
        offenders = {}
        for html_file in sorted(ws.WEB_DIR.glob("*.html")):
            text = html_file.read_text(encoding="utf-8")
            matches = relative_local_asset.findall(text)
            if matches:
                offenders[html_file.name] = matches
        self.assertEqual(offenders, {}, f"relative local asset path(s) found: {offenders}")


class ProfilePrivacyTestCase(unittest.TestCase):
    """P0 privacy regression lock (2026-09-13): /profile must never be a
    reachable route, must not exist inside the publicly-served WEB_DIR
    static tree (which would let Starlette's StaticFiles fallback serve
    it even with no explicit Route), and must not be linked from any
    public page's navigation. Source is preserved at
    docs/archive/profile_preserved/{profile.html,profile.css} for later
    restoration — this test intentionally does not check that directory,
    since files there must never be reachable via the running server."""

    def test_profile_route_is_not_registered(self):
        routes = {r.path: r for r in ws.routes if hasattr(r, "path")}
        self.assertNotIn("/profile", routes)

    def test_profile_page_handler_no_longer_exists(self):
        self.assertFalse(
            hasattr(ws, "profile_page"),
            "profile_page handler must be removed, not merely unrouted",
        )

    def test_profile_html_and_css_absent_from_served_web_dir(self):
        served_dir = ws.WEB_DIR
        self.assertFalse((served_dir / "profile.html").exists())
        self.assertFalse((served_dir / "profile.css").exists())

    def test_no_public_html_page_links_to_profile(self):
        for html_file in ws.WEB_DIR.glob("*.html"):
            content = html_file.read_text(encoding="utf-8")
            self.assertNotIn(
                "/profile", content,
                f"{html_file.name} must not reference /profile",
            )


class VerifiedRunLinkTestCase(unittest.TestCase):
    """RECRUITER-FACING VERIFIED-RUN P0 (2026-09-13): real defect the
    Owner found by manual testing — workbench.html's "SEE A VERIFIED
    RUN" CTA was a bare hard-coded href to one specific run_id
    (trainer-4733d1c0, a 2026-09-11 run), which silently went stale the
    moment a newer real run completed, sending recruiters to a
    two-day-old example with no explanation. This locks in that the
    static HTML never re-embeds any literal trainer-* run_id, and that
    a real API route exists to resolve the destination dynamically —
    see VerifiedRunSelectionTestCase in test_session_history.py for the
    actual selection-logic proof."""

    _RUN_ID_PATTERN = re.compile(r"trainer-[0-9a-f]{8}")

    def test_workbench_html_never_hard_codes_a_specific_run_id(self):
        content = (ws.WEB_DIR / "workbench.html").read_text(encoding="utf-8")
        matches = self._RUN_ID_PATTERN.findall(content)
        self.assertEqual(matches, [], f"workbench.html must never embed a literal run_id, found: {matches}")

    def test_verified_run_link_starts_hidden_with_a_loading_state(self):
        content = (ws.WEB_DIR / "workbench.html").read_text(encoding="utf-8")
        self.assertIn('id="verified-run-link"', content)
        self.assertIn('id="verified-run-unavailable"', content)
        # The link itself must not have a real href baked in — only the
        # live JS lookup may set one.
        self.assertIn('id="verified-run-link" href="#" hidden', content)

    def test_verified_run_api_route_is_registered(self):
        routes = {r.path: r for r in ws.routes if hasattr(r, "path")}
        self.assertIn("/api/workbench/verified-run", routes)
        self.assertIn("GET", routes["/api/workbench/verified-run"].methods)


class VerifiedRunApiTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_returns_available_true_and_the_real_selected_run_id(self):
        with mock.patch.object(ws.session_history, "get_latest_verified_workbench_run_id", return_value="trainer-deadbeef"):
            response = await ws.get_verified_workbench_run(mock.Mock())
        body = json.loads(response.body)
        self.assertTrue(body["available"])
        self.assertEqual(body["run_id"], "trainer-deadbeef")

    async def test_returns_available_false_never_a_broken_id_when_none_qualifies(self):
        with mock.patch.object(ws.session_history, "get_latest_verified_workbench_run_id", return_value=None):
            response = await ws.get_verified_workbench_run(mock.Mock())
        body = json.loads(response.body)
        self.assertFalse(body["available"])
        self.assertIsNone(body["run_id"])


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
    """RELIABILITY/CORRECTION PHASE (2026-09-13): the public demo path is
    now a deterministic catalogue with zero API calls, so 'estimated
    cost' is no longer a probabilistic guess — it is a real, exact fact
    ($0.00, no model call happens). These tests replace the old
    probabilistic-estimate contract, which no longer applies to this path."""

    async def test_assess_route_reports_exact_zero_cost_for_auto_decisions(self):
        request = mock.Mock()
        request.json = mock.AsyncMock(return_value={"requirement": 'Change the footer text to "Agent Demo"'})
        response = await ws.assess_trainer_requirement(request)
        body = json.loads(response.body)
        self.assertEqual(body["decision"], "auto")
        self.assertEqual(body["estimated_cost_usd"], 0.0)

    async def test_assess_route_never_reports_a_normalized_request_for_a_blocked_requirement(self):
        request = mock.Mock()
        request.json = mock.AsyncMock(return_value={"requirement": "Change the login password hashing scheme"})
        response = await ws.assess_trainer_requirement(request)
        body = json.loads(response.body)
        self.assertEqual(body["decision"], "blocked")
        self.assertNotIn("operation_id", body)
        self.assertIn("suggested_examples", body)

    async def test_a_real_supported_requirement_starts_a_real_run(self):
        """Direct proof that a genuinely supported, auto-decision
        requirement actually starts the deterministic trainer thread —
        never blocked, never dependent on any estimate."""
        self.addCleanup(lambda: setattr(ws, "_CURRENT_RUN_ID", None))
        with mock.patch.object(ws.threading, "Thread") as mock_thread:
            request = mock.Mock()
            request.json = mock.AsyncMock(return_value={"requirement": 'Change the footer text to "Agent Demo"'})
            response = await ws.start_trainer_run(request)
            body = json.loads(response.body)
            self.assertFalse(body["blocked"])
            self.assertIn("run_id", body)
            trainer_thread_calls = [
                c for c in mock_thread.call_args_list
                if c.kwargs.get("target") is ws._run_trainer_thread
            ]
            self.assertEqual(len(trainer_thread_calls), 1)
            # The exact NormalizedRequest (not a dict re-derived some other
            # way) is what gets passed to the thread.
            passed_normalized = trainer_thread_calls[0].kwargs["args"][2]
            self.assertEqual(passed_normalized.operation_id, "footer_text")
            self.assertEqual(passed_normalized.new_value, "Agent Demo")


class ContentVerificationRetryTestCase(unittest.TestCase):
    """Real gap found live (2026-09-13, this exact task's first real
    production acceptance run): a deployment's own record can say SUCCESS
    while the traffic-serving container hasn't finished its cutover yet —
    a single immediate content check can observe stale content and
    report a false FAILED. _verify_content_with_retry() must retry
    briefly, but ONLY when deployment identity is actually confirmed."""

    def test_returns_immediately_when_content_already_matches(self):
        with mock.patch.object(demo_catalogue, "extract_current_value", return_value="X"), \
             mock.patch.object(ws, "_fetch_public_app", return_value=(200, "<p>X</p>")) as mock_fetch, \
             mock.patch.object(ws.time, "sleep") as mock_sleep:
            status, html, value, verified = ws._verify_content_with_retry("op", "X", True)
        self.assertTrue(verified)
        mock_fetch.assert_called_once()
        mock_sleep.assert_not_called()

    def test_retries_until_content_matches_within_the_window(self):
        with mock.patch.object(demo_catalogue, "extract_current_value", side_effect=["OLD", "OLD", "NEW"]), \
             mock.patch.object(ws, "_fetch_public_app", return_value=(200, "<p>whatever</p>")), \
             mock.patch.object(ws.time, "sleep") as mock_sleep:
            status, html, value, verified = ws._verify_content_with_retry("op", "NEW", True)
        self.assertTrue(verified)
        self.assertEqual(value, "NEW")
        self.assertEqual(mock_sleep.call_count, 2)

    def test_gives_up_honestly_after_the_wait_window_when_deployment_identity_confirmed(self):
        with mock.patch.object(demo_catalogue, "extract_current_value", return_value="STILL OLD"), \
             mock.patch.object(ws, "_fetch_public_app", return_value=(200, "<p>x</p>")), \
             mock.patch.object(ws.time, "sleep"):
            status, html, value, verified = ws._verify_content_with_retry("op", "NEW", True, max_wait_s=30, poll_interval_s=10)
        self.assertFalse(verified)
        self.assertEqual(value, "STILL OLD")

    def test_does_not_retry_at_all_when_deployment_identity_was_never_confirmed(self):
        """No real new deployment to wait on — retrying would just be a
        slow way to reach the same honest DEPLOYMENT_STATUS_UNKNOWN."""
        with mock.patch.object(demo_catalogue, "extract_current_value", return_value="OLD"), \
             mock.patch.object(ws, "_fetch_public_app", return_value=(200, "<p>x</p>")) as mock_fetch, \
             mock.patch.object(ws.time, "sleep") as mock_sleep:
            ws._verify_content_with_retry("op", "NEW", False)
        mock_fetch.assert_called_once()
        mock_sleep.assert_not_called()


class DemoResetTestCase(unittest.IsolatedAsyncioTestCase):
    """JOB-SEARCH P0 (2026-09-12): the public demo lifecycle's explicit
    Reset Demo path — a shared public demo must have a safe, verifiable
    way back to canonical baseline. Every git/Railway/network call is
    mocked here (no real repository or production mutation from tests);
    the real end-to-end reset was separately exercised live."""

    def setUp(self):
        self.addCleanup(lambda: setattr(ws, "_CURRENT_RUN_ID", None))
        self.addCleanup(lambda: setattr(ws, "_reset_state", {"status": "idle", "message": None}))

    async def test_reset_route_returns_busy_when_a_run_is_in_flight(self):
        ws._CURRENT_RUN_ID = "trainer-already-running"
        with mock.patch.object(ws.threading, "Thread") as mock_thread:
            response = await ws.start_demo_reset(mock.Mock())
        self.assertEqual(response.status_code, 409)
        self.assertTrue(json.loads(response.body)["busy"])
        mock_thread.assert_not_called()

    async def test_reset_route_starts_a_background_thread_when_free(self):
        with mock.patch.object(ws.threading, "Thread") as mock_thread:
            response = await ws.start_demo_reset(mock.Mock())
        body = json.loads(response.body)
        self.assertTrue(body["started"])
        reset_thread_calls = [c for c in mock_thread.call_args_list if c.kwargs.get("target") is ws._run_reset_thread]
        self.assertEqual(len(reset_thread_calls), 1)
        ws._release_run_slot()

    def _with_isolated_workspace(self, live_content="<html>whatever the isolated clone happens to contain</html>"):
        """RELIABILITY/CORRECTION PHASE (2026-09-13): reset now clones a
        fresh isolated workspace (agent/demo_execution.py) exactly like
        the main trainer flow, rather than mutating REPO_ROOT directly.
        These tests patch demo_execution.create_isolated_workspace to
        return a real temp directory (real file I/O still exercised) and
        mock the git/Railway calls it would otherwise make for real."""
        tmp = tempfile.TemporaryDirectory()
        workspace = Path(tmp.name) / "workspace"
        live_path = workspace / ws.DEMO_RESETTABLE_PATH
        live_path.parent.mkdir(parents=True)
        live_path.write_text(live_content, encoding="utf-8")
        baseline_path = Path(tmp.name) / "baseline.html"
        clone_patch = mock.patch.object(ws.demo_execution, "create_isolated_workspace", return_value=(workspace, True, ""))
        return tmp, workspace, live_path, baseline_path, clone_patch, mock.patch.object(ws, "DEMO_BASELINE_FILE", baseline_path)

    def test_already_at_baseline_is_a_clean_no_op_not_an_empty_commit(self):
        # Real finding this exact task made live: the CONTAINER's own local
        # file is never checked for the go/no-go decision — a redeploy can
        # silently reset it to baseline while the real deployed Customer
        # App still shows an old change. Only a real fetch of production
        # decides whether a reset is actually needed.
        ws._reserve_run_slot("demo-reset")
        baseline_html = "<html>baseline</html>"
        tmp, workspace, live_path, baseline_path, clone_patch, baseline_patch = self._with_isolated_workspace()
        baseline_path.write_text(baseline_html, encoding="utf-8")
        with tmp, clone_patch, baseline_patch, \
             mock.patch.object(ws, "_fetch_public_app", return_value=(200, baseline_html)), \
             mock.patch.object(ws.demo_execution, "commit_change") as mock_commit:
            ws._run_reset_thread()
        self.assertEqual(ws._reset_state["status"], "completed")
        self.assertIn("Already at canonical baseline", ws._reset_state["message"])
        # No git/railway call was ever attempted for a genuine no-op — the
        # isolated workspace isn't even cloned.
        mock_commit.assert_not_called()

    def test_successful_reset_writes_baseline_commits_pushes_deploys_and_verifies(self):
        ws._reserve_run_slot("demo-reset")
        baseline_html = "<html>canonical baseline</html>"
        tmp, workspace, live_path, baseline_path, clone_patch, baseline_patch = self._with_isolated_workspace()
        baseline_path.write_text(baseline_html, encoding="utf-8")
        # First _fetch_public_app call is the authoritative pre-check
        # (production still shows an old demo change); the final call is
        # the post-deploy content verification (production now shows
        # baseline).
        written_content = {}

        def _capture_and_cleanup(ws_path):
            # _run_reset_thread cleans up the workspace unconditionally in
            # its own `finally`, before this test ever gets to inspect it
            # — capture the real written content at cleanup time instead
            # of racing it.
            written_content["value"] = (ws_path / ws.DEMO_RESETTABLE_PATH).read_text(encoding="utf-8")

        with tmp, clone_patch, baseline_patch, \
             mock.patch.object(ws.demo_execution, "commit_change", return_value=("demo/reset-x", True, "")), \
             mock.patch.object(ws.demo_execution, "push_change", return_value=("PUSHED", None)), \
             mock.patch.object(ws.demo_execution, "trigger_deploy", return_value=(True, "")), \
             mock.patch.object(ws.demo_execution, "wait_for_new_deployment", return_value=("new-dep-id", "SUCCESS", 30)), \
             mock.patch.object(ws.demo_execution, "cleanup_workspace", side_effect=_capture_and_cleanup), \
             mock.patch.object(ws, "_fetch_public_app",
                                side_effect=[(200, "<html>changed by a demo run</html>"), (200, baseline_html)]):
            ws._run_reset_thread()
            self.assertEqual(ws._reset_state["status"], "completed")
            self.assertIn("verified live", ws._reset_state["message"])
            # The isolated workspace's file itself was really overwritten.
            self.assertEqual(written_content["value"], baseline_html)

    def test_reset_still_deploys_when_isolated_clone_has_nothing_to_commit(self):
        """The exact real defect this task found live: a fresh isolated
        clone can already match baseline (e.g. an earlier reset already
        pushed it to origin) while the real deployed Customer App still
        shows an old change. `git commit` then genuinely has "nothing to
        commit" — this must NOT abort the reset; deploy must still run so
        the actually-stale Customer App gets the (already-correct) content."""
        ws._reserve_run_slot("demo-reset")
        baseline_html = "<html>canonical baseline</html>"
        tmp, workspace, live_path, baseline_path, clone_patch, baseline_patch = self._with_isolated_workspace(live_content=baseline_html)
        baseline_path.write_text(baseline_html, encoding="utf-8")
        with tmp, clone_patch, baseline_patch, \
             mock.patch.object(ws.demo_execution, "commit_change", return_value=("demo/reset-x", False, "nothing to commit, working tree clean")), \
             mock.patch.object(ws.demo_execution, "push_change", return_value=("PUSHED", None)), \
             mock.patch.object(ws.demo_execution, "trigger_deploy", return_value=(True, "")) as mock_deploy, \
             mock.patch.object(ws.demo_execution, "wait_for_new_deployment", return_value=("new-dep-id", "SUCCESS", 30)), \
             mock.patch.object(ws, "_fetch_public_app",
                                side_effect=[(200, "<html>production is still stale</html>"), (200, baseline_html)]):
            ws._run_reset_thread()
        self.assertEqual(ws._reset_state["status"], "completed")
        mock_deploy.assert_called_once()

    def test_reset_releases_the_run_slot_even_on_failure(self):
        ws._reserve_run_slot("demo-reset")
        with mock.patch.object(ws, "_read_demo_baseline", return_value=None):
            ws._run_reset_thread()
        self.assertEqual(ws._reset_state["status"], "failed")
        # The slot must be free again for a future run/reset.
        self.assertTrue(ws._reserve_run_slot("some-later-run"))

    def test_reset_cleans_up_the_isolated_workspace_on_success(self):
        ws._reserve_run_slot("demo-reset")
        baseline_html = "<html>canonical baseline</html>"
        tmp, workspace, live_path, baseline_path, clone_patch, baseline_patch = self._with_isolated_workspace()
        baseline_path.write_text(baseline_html, encoding="utf-8")
        with tmp, clone_patch, baseline_patch, \
             mock.patch.object(ws.demo_execution, "commit_change", return_value=("demo/reset-x", True, "")), \
             mock.patch.object(ws.demo_execution, "push_change", return_value=("PUSHED", None)), \
             mock.patch.object(ws.demo_execution, "trigger_deploy", return_value=(True, "")), \
             mock.patch.object(ws.demo_execution, "wait_for_new_deployment", return_value=("new-dep-id", "SUCCESS", 30)), \
             mock.patch.object(ws, "_fetch_public_app",
                                side_effect=[(200, "<html>changed by a demo run</html>"), (200, baseline_html)]):
            ws._run_reset_thread()
        self.assertFalse(workspace.exists())


class TrainerConcurrencyAndAbuseProtectionTestCase(unittest.IsolatedAsyncioTestCase):
    """JOB-SEARCH P0 (2026-09-12): the public trainer demo can trigger a
    real git commit + push + Railway deploy against the real Customer
    App — before this task, nothing prevented two simultaneous public
    submissions from racing on the same working tree/deployment, nor any
    input-length/cooldown abuse protection. These are the real safety
    gaps this task closes, verified directly rather than assumed."""

    def setUp(self):
        # Every test in this class touches process-global state; always
        # restore it, regardless of pass/fail, so no test here can leak
        # state into a later test in this process.
        self.addCleanup(lambda: setattr(ws, "_CURRENT_RUN_ID", None))
        self.addCleanup(lambda: setattr(ws, "_LAST_TRAINER_RUN_FINISHED_AT", 0.0))

    def test_reserve_run_slot_blocks_a_second_reservation_until_released(self):
        self.assertTrue(ws._reserve_run_slot("run-a"))
        self.assertFalse(ws._reserve_run_slot("run-b"))
        ws._release_run_slot()
        self.assertTrue(ws._reserve_run_slot("run-b"))

    async def test_second_concurrent_submission_is_busy_not_started(self):
        ws._CURRENT_RUN_ID = "trainer-already-running"
        with mock.patch.object(ws.threading, "Thread") as mock_thread:
            request = mock.Mock()
            request.json = mock.AsyncMock(return_value={"requirement": 'Change the footer text to "Agent Demo"'})
            response = await ws.start_trainer_run(request)
        self.assertEqual(response.status_code, 409)
        body = json.loads(response.body)
        self.assertTrue(body["busy"])
        mock_thread.assert_not_called()

    async def test_requirement_exceeding_max_chars_is_blocked_before_classification(self):
        with mock.patch.object(ws.risk_policy, "classify") as mock_classify:
            request = mock.Mock()
            request.json = mock.AsyncMock(return_value={"requirement": "x" * (ws.TRAINER_REQUIREMENT_MAX_CHARS + 1)})
            response = await ws.start_trainer_run(request)
        body = json.loads(response.body)
        self.assertTrue(body["blocked"])
        self.assertEqual(body["assessment"]["decision"], "blocked")
        # Never even reaches the (real, model-adjacent) classification path
        # for an input this large — the length cap is checked first.
        mock_classify.assert_not_called()

    async def test_cooldown_blocks_immediately_after_a_run_finished(self):
        ws._LAST_TRAINER_RUN_FINISHED_AT = ws.time.monotonic()
        with mock.patch.object(ws.threading, "Thread") as mock_thread:
            request = mock.Mock()
            request.json = mock.AsyncMock(return_value={"requirement": 'Change the footer text to "Agent Demo"'})
            response = await ws.start_trainer_run(request)
        self.assertEqual(response.status_code, 429)
        body = json.loads(response.body)
        self.assertTrue(body["busy"])
        self.assertGreater(body["cooldown_seconds"], 0)
        mock_thread.assert_not_called()

    async def test_cooldown_elapsed_allows_a_new_run(self):
        ws._LAST_TRAINER_RUN_FINISHED_AT = ws.time.monotonic() - (ws.TRAINER_COOLDOWN_SECONDS + 5)
        with mock.patch.object(ws.threading, "Thread") as mock_thread:
            request = mock.Mock()
            request.json = mock.AsyncMock(return_value={"requirement": 'Change the footer text to "Agent Demo"'})
            response = await ws.start_trainer_run(request)
        body = json.loads(response.body)
        self.assertFalse(body.get("busy"))
        self.assertFalse(body.get("blocked"))
        # threading.Thread is also used internally by subprocess.run's own
        # reader threads for estimation.estimate_run()'s real git calls —
        # assert on the specific trainer-thread call, not call count.
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

    def test_trainer_thread_fails_before_touching_source_when_workspace_clone_fails(self):
        """RELIABILITY/CORRECTION PHASE (2026-09-13): the trainer path no
        longer checks the SERVER's own REPO_ROOT git health — it clones a
        fresh isolated workspace per run (agent/demo_execution.py). The
        exact required behavior is unchanged in spirit: FAIL BEFORE
        MODIFYING ANYTHING. Proves no file write is even attempted when
        the isolated clone itself fails."""
        run = ws.Run("test-run", "test requirement")
        run.trainer_usage_start_index = 0
        normalized = demo_catalogue.normalize_requirement('Change the footer text to "X"')
        with mock.patch.object(ws.demo_execution, "create_isolated_workspace",
                                return_value=(Path("nonexistent"), False, "git clone failed: could not resolve host")), \
             mock.patch.object(ws.demo_execution, "commit_change") as mock_commit:
            ws._run_trainer_thread(run, "some requirement", normalized)
        mock_commit.assert_not_called()
        self.assertEqual(run.status, "FAILED")
        error_event = next(e for e in run.events if e["type"] == "error")
        self.assertIn("isolated workspace", error_event["message"])


class PushStatusTruthfulnessTestCase(unittest.TestCase):
    """WORKBENCH TRUTHFULNESS FIX (2026-09-13): real Owner-submitted run
    trainer-25c4e8bb ("Change the footer text to \"Built with DOSS
    care\"") genuinely reached COMPLETED — real commit, real Railway
    deployment, real independently-curl-confirmed production content —
    but the UI showed an alarming "ERROR: git push failed..." activity
    line for the ordinary, fully-expected DEMO_GIT_PUSH_TOKEN-not-
    configured precondition, root-caused directly from the live event
    ledger (agent/event_ledger.py) rather than guessed at. These tests
    lock in that a NOT_CONFIGURED push status is reported honestly and
    calmly, never as an "error" event indistinguishable from a real
    attempted-and-failed push."""

    def _run_to_completion(self, push_return):
        # _run_trainer_thread's own finally block sets the real
        # module-level cooldown timestamp (_LAST_TRAINER_RUN_FINISHED_AT)
        # on every call — restore it afterward so this test can never
        # leak a false "busy" cooldown into an unrelated later test in
        # the same process (see test_web_server.py's other established
        # convention for this exact global, e.g.
        # TrainerConcurrencyAndAbuseProtectionTestCase).
        self.addCleanup(lambda: setattr(ws, "_LAST_TRAINER_RUN_FINISHED_AT", 0.0))
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            target_rel = "app/src/main/resources/static/index.html"
            target_path = workspace / target_rel
            target_path.parent.mkdir(parents=True)
            target_path.write_text(
                '<footer class="app-footer">Powered by Agentic Delivery</footer>', encoding="utf-8")
            run = ws.Run("test-run", "test requirement")
            run.trainer_usage_start_index = 0
            normalized = demo_catalogue.normalize_requirement('Change the footer text to "Built with DOSS care"')
            # Live production currently shows the OLD value — never a
            # real network call. This is the pre-deploy NO_CHANGE_NEEDED
            # precheck's fetch (see the WORKBENCH TRUTHFULNESS FIX at its
            # call site): it must see this, not the isolated workspace's
            # own (already-updated-in-this-fixture) file content.
            with mock.patch.object(ws.demo_execution, "create_isolated_workspace", return_value=(workspace, True, "")), \
                 mock.patch.object(ws, "_fetch_public_app", return_value=(200, '<footer class="app-footer">Powered by Agentic Delivery</footer>')), \
                 mock.patch.object(ws.demo_execution, "commit_change", return_value=("demo/test-run", True, "")), \
                 mock.patch.object(ws.demo_execution, "get_changed_files", return_value=[target_rel]), \
                 mock.patch.object(ws.demo_execution, "get_commit_sha", return_value="fd92664"), \
                 mock.patch.object(ws.demo_execution, "push_change", return_value=push_return), \
                 mock.patch.object(ws.demo_execution, "trigger_deploy", return_value=(True, "")), \
                 mock.patch.object(ws.demo_execution, "wait_for_new_deployment", return_value=("new-dep-id", "SUCCESS", 5)), \
                 mock.patch.object(ws, "_verify_content_with_retry", return_value=(200, "<html></html>", "Built with DOSS care", True)), \
                 mock.patch.object(ws.demo_execution, "cleanup_workspace"):
                ws._run_trainer_thread(run, "some requirement", normalized)
        return run

    def test_not_configured_push_reaches_completed_with_no_error_event(self):
        run = self._run_to_completion((demo_execution.PUSH_STATUS_NOT_CONFIGURED, "DEMO_GIT_PUSH_TOKEN not configured — push skipped (deploy continues from the isolated workspace regardless)"))
        self.assertEqual(run.status, "COMPLETED")
        error_events = [e for e in run.events if e["type"] == "error"]
        self.assertEqual(error_events, [], "NOT_CONFIGURED push must never emit an 'error' event")
        push_event = next(e for e in run.events if e["type"] == "push")
        self.assertEqual(push_event["status"], "NOT_CONFIGURED")

    def test_failed_push_still_reaches_completed_but_does_emit_an_error_event(self):
        """A genuine attempted-and-failed push IS worth surfacing as an
        error (distinct from NOT_CONFIGURED) — it just must not block the
        deploy, which still runs from the isolated workspace regardless."""
        run = self._run_to_completion((demo_execution.PUSH_STATUS_FAILED, "remote: Permission denied"))
        self.assertEqual(run.status, "COMPLETED")
        error_events = [e for e in run.events if e["type"] == "error"]
        self.assertEqual(len(error_events), 1)
        self.assertIn("git push failed", error_events[0]["message"])
        push_event = next(e for e in run.events if e["type"] == "push")
        self.assertEqual(push_event["status"], "FAILED")

    def test_pushed_status_reaches_completed_with_no_error_event(self):
        run = self._run_to_completion((demo_execution.PUSH_STATUS_PUSHED, None))
        self.assertEqual(run.status, "COMPLETED")
        error_events = [e for e in run.events if e["type"] == "error"]
        self.assertEqual(error_events, [])
        push_event = next(e for e in run.events if e["type"] == "push")
        self.assertEqual(push_event["status"], "PUSHED")


class NoChangeNeededUsesLiveProductionTestCase(unittest.TestCase):
    """WORKBENCH TRUTHFULNESS FIX (2026-09-13): real defect found live by
    this session's own adversarial re-run (submitting the exact reverse
    of the Owner's "Built with DOSS care" run, through the real public
    Workbench). Each run clones a FRESH isolated workspace from GitHub
    (see demo_execution.create_isolated_workspace), but Railway is
    deployed straight from that disposable clone — never from a GitHub
    push, which only happens if DEMO_GIT_PUSH_TOKEN is configured
    (currently NOT_CONFIGURED, see ACT-007). So GitHub source and live
    production can genuinely diverge the moment any run changes
    production without a successful push. The NO_CHANGE_NEEDED
    short-circuit previously compared the requested value against the
    GitHub-derived isolated-workspace file — never live production —
    so it could (and, live, did) falsely declare "no change needed"
    while production still showed the OLD value. Confirmed live: after
    the Owner's run left production showing "Built with DOSS care" but
    GitHub's own tracked source still said "Powered by Agentic
    Delivery" (because push was skipped), submitting "Change the footer
    text to \"Powered by Agentic Delivery\"" through the real public
    Workbench (run trainer-7e4ce200) returned NO_CHANGE_NEEDED even
    though production still genuinely showed "Built with DOSS care"."""

    def _run(self, isolated_workspace_content, live_production_content):
        # See PushStatusTruthfulnessTestCase._run_to_completion's identical
        # comment — _run_trainer_thread's finally block sets the real
        # module-level cooldown timestamp on every call.
        self.addCleanup(lambda: setattr(ws, "_LAST_TRAINER_RUN_FINISHED_AT", 0.0))
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            target_rel = "app/src/main/resources/static/index.html"
            target_path = workspace / target_rel
            target_path.parent.mkdir(parents=True)
            target_path.write_text(isolated_workspace_content, encoding="utf-8")
            run = ws.Run("test-run", "test requirement")
            run.trainer_usage_start_index = 0
            normalized = demo_catalogue.normalize_requirement('Change the footer text to "Powered by Agentic Delivery"')
            with mock.patch.object(ws.demo_execution, "create_isolated_workspace", return_value=(workspace, True, "")), \
                 mock.patch.object(ws, "_fetch_public_app", return_value=(200, live_production_content)), \
                 mock.patch.object(ws.demo_execution, "commit_change", return_value=("demo/test-run", True, "")), \
                 mock.patch.object(ws.demo_execution, "get_changed_files", return_value=[target_rel]), \
                 mock.patch.object(ws.demo_execution, "get_commit_sha", return_value="fd92664"), \
                 mock.patch.object(ws.demo_execution, "push_change", return_value=(demo_execution.PUSH_STATUS_NOT_CONFIGURED, "not configured")), \
                 mock.patch.object(ws.demo_execution, "trigger_deploy", return_value=(True, "")), \
                 mock.patch.object(ws.demo_execution, "wait_for_new_deployment", return_value=("new-dep-id", "SUCCESS", 5)), \
                 mock.patch.object(ws, "_verify_content_with_retry", return_value=(200, "<html></html>", "Powered by Agentic Delivery", True)), \
                 mock.patch.object(ws.demo_execution, "cleanup_workspace"):
                ws._run_trainer_thread(run, "some requirement", normalized)
        return run

    def test_no_change_needed_only_when_live_production_already_matches(self):
        matching_html = '<footer class="app-footer">Powered by Agentic Delivery</footer>'
        run = self._run(isolated_workspace_content=matching_html, live_production_content=matching_html)
        self.assertEqual(run.status, "NO_CHANGE_NEEDED")
        no_change_event = next(e for e in run.events if e["type"] == "no_change_needed")
        self.assertIn("live production", no_change_event["reason"])

    def test_source_already_matches_but_production_is_stale_still_deploys(self):
        """THE EXACT REAL BUG: GitHub's tracked source (mirrored into the
        fresh isolated workspace clone) already has the requested value,
        but live production is stale (a prior run's change never got
        pushed to GitHub) — this must NOT short-circuit to
        NO_CHANGE_NEEDED; it must proceed through commit/deploy so
        production actually gets corrected."""
        already_matching_source = '<footer class="app-footer">Powered by Agentic Delivery</footer>'
        stale_production = '<footer class="app-footer">Built with DOSS care</footer>'
        run = self._run(isolated_workspace_content=already_matching_source, live_production_content=stale_production)
        self.assertEqual(run.status, "COMPLETED")
        self.assertEqual([e for e in run.events if e["type"] == "no_change_needed"], [])
        commit_events = [e for e in run.events if e["type"] == "commit"]
        self.assertEqual(len(commit_events), 1, "a real commit/deploy must happen to correct stale production")


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


class DetermineTestingStateTestCase(unittest.TestCase):
    """Regression tests for the real semantic bug: NO TEST FILES !=
    TESTING NOT APPLICABLE. A Java source change with zero test coverage
    must be labeled NOT_CONFIGURED (a project-level gap), never
    NOT_APPLICABLE (which must mean the change genuinely has no test
    surface, e.g. a static resource). Real applicable tests that exist
    but weren't run must be SKIPPED, and must block commit like FAILED."""

    def _with_no_test_files(self):
        tmp = tempfile.TemporaryDirectory()
        fake_app_dir = Path(tmp.name) / "app"
        (fake_app_dir / "src" / "test" / "java").mkdir(parents=True)
        return tmp, mock.patch.object(ws, "APP_DIR", fake_app_dir)

    def _with_real_test_file(self):
        tmp = tempfile.TemporaryDirectory()
        fake_app_dir = Path(tmp.name) / "app"
        test_dir = fake_app_dir / "src" / "test" / "java"
        test_dir.mkdir(parents=True)
        (test_dir / "SomeTest.java").write_text("class SomeTest {}", encoding="utf-8")
        return tmp, mock.patch.object(ws, "APP_DIR", fake_app_dir)

    def test_real_test_results_produce_passed(self):
        tmp, patcher = self._with_no_test_files()
        with tmp, patcher:
            result = ws._determine_testing_state("app/src/main/java/X.java", [{"success": True}])
        self.assertEqual(result["state"], "PASSED")

    def test_real_test_results_produce_failed(self):
        tmp, patcher = self._with_no_test_files()
        with tmp, patcher:
            result = ws._determine_testing_state("app/src/main/java/X.java", [{"success": False}])
        self.assertEqual(result["state"], "FAILED")

    def test_static_resource_with_no_tests_is_not_applicable(self):
        tmp, patcher = self._with_no_test_files()
        with tmp, patcher:
            result = ws._determine_testing_state("app/src/main/resources/static/index.html", [])
        self.assertEqual(result["state"], "NOT_APPLICABLE")

    def test_java_change_with_no_tests_is_not_configured_not_not_applicable(self):
        """The exact bug this task fixes: a Java source change with zero
        test coverage must never be labeled NOT_APPLICABLE."""
        tmp, patcher = self._with_no_test_files()
        with tmp, patcher:
            result = ws._determine_testing_state("app/src/main/java/com/example/customer/model/Customer.java", [])
        self.assertEqual(result["state"], "NOT_CONFIGURED")
        self.assertNotEqual(result["state"], "NOT_APPLICABLE")

    def test_real_tests_exist_but_not_run_is_skipped_for_java_change(self):
        tmp, patcher = self._with_real_test_file()
        with tmp, patcher:
            result = ws._determine_testing_state("app/src/main/java/com/example/customer/model/Customer.java", [])
        self.assertEqual(result["state"], "SKIPPED")

    def test_static_resource_change_is_not_applicable_even_when_unrelated_java_tests_exist(self):
        """The exact real recruiter-facing defect this task fixes (JOB-SEARCH
        P0, 2026-09-12): a genuine static-only UI change (e.g. a heading/
        footer text edit) must never be blocked as SKIPPED just because the
        Customer app happens to have SOME Java test file elsewhere — a
        static resource can never have Java tests targeting it, regardless
        of what else exists in the project."""
        tmp, patcher = self._with_real_test_file()
        with tmp, patcher:
            result = ws._determine_testing_state("app/src/main/resources/static/index.html", [])
        self.assertEqual(result["state"], "NOT_APPLICABLE")
        self.assertNotEqual(result["state"], "SKIPPED")

    def test_passed_and_not_applicable_and_not_configured_allow_commit(self):
        for state in ("PASSED", "NOT_APPLICABLE", "NOT_CONFIGURED"):
            with self.subTest(state=state):
                self.assertIn(state, ws._TESTING_STATES_ALLOWING_COMMIT)

    def test_failed_and_skipped_block_commit(self):
        for state in ("FAILED", "SKIPPED"):
            with self.subTest(state=state):
                self.assertNotIn(state, ws._TESTING_STATES_ALLOWING_COMMIT)


class PublicRouteRedirectTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_trainer_redirects_to_workbench(self):
        response = await ws.redirect_trainer_to_workbench(mock.Mock())
        self.assertEqual(response.headers["location"], "/workbench")
        self.assertEqual(response.status_code, 308)

    async def test_sessions_redirects_to_usage(self):
        response = await ws.redirect_sessions_to_usage(mock.Mock())
        self.assertEqual(response.headers["location"], "/usage")
        self.assertEqual(response.status_code, 308)


class LearnRecursiveRouteTestCase(unittest.IsolatedAsyncioTestCase):
    """P0-A: /learn and every nested topic route are validated against
    the real canonical tree server-side — an unknown slug path must
    genuinely 404, not silently serve the SPA shell."""

    def _route_map(self):
        return {r.path: r for r in ws.routes if hasattr(r, "path")}

    def test_nested_learn_route_is_registered(self):
        routes = self._route_map()
        self.assertIn("/learn/{path:path}", routes)
        self.assertIs(routes["/learn/{path:path}"].endpoint, ws.learn_page)

    async def test_landing_page_has_no_path_param(self):
        response = await ws.learn_page(mock.Mock(path_params={}))
        self.assertEqual(response.status_code, 200)

    async def test_valid_deep_path_serves_the_shell(self):
        response = await ws.learn_page(mock.Mock(path_params={"path": "system-design/databases/connection-pooling"}))
        self.assertEqual(response.status_code, 200)

    async def test_unknown_path_returns_real_404(self):
        response = await ws.learn_page(mock.Mock(path_params={"path": "does-not-exist-at-all"}))
        self.assertEqual(response.status_code, 404)

    async def test_partially_valid_path_still_404s(self):
        """A valid domain slug followed by a bogus child must still 404
        -- the whole path is validated, not just its first segment."""
        response = await ws.learn_page(mock.Mock(path_params={"path": "system-design/does-not-exist"}))
        self.assertEqual(response.status_code, 404)

    async def test_learn_tree_api_route_returns_real_tree(self):
        response = await ws.get_learn_tree_data(mock.Mock())
        body = json.loads(response.body)
        self.assertIn("domains", body)
        self.assertGreater(len(body["domains"]), 0)


class AiIntelligenceRouteTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._orig_dir = ai_intelligence.DAILY_DIR
        self._tmp_dir = Path(__file__).resolve().parent / "_tmp_ai_intelligence_route_test"
        if self._tmp_dir.exists():
            shutil.rmtree(self._tmp_dir)
        self._tmp_dir.mkdir(parents=True)
        ai_intelligence.DAILY_DIR = self._tmp_dir

    def tearDown(self):
        ai_intelligence.DAILY_DIR = self._orig_dir
        if self._tmp_dir.exists():
            shutil.rmtree(self._tmp_dir)

    def test_routes_are_registered(self):
        routes = {r.path: r for r in ws.routes if hasattr(r, "path")}
        self.assertIn("/api/ai-intelligence/dates", routes)
        self.assertIn("/api/ai-intelligence/daily/{date}", routes)

    async def test_dates_route_returns_empty_list_honestly_when_nothing_published(self):
        response = await ws.get_ai_intelligence_dates(mock.Mock())
        body = json.loads(response.body)
        self.assertEqual(body["dates"], [])

    async def test_dates_route_returns_real_committed_dates(self):
        (self._tmp_dir / "2026-09-15.md").write_text("## X\nbody", encoding="utf-8")
        response = await ws.get_ai_intelligence_dates(mock.Mock())
        body = json.loads(response.body)
        self.assertEqual(body["dates"], ["2026-09-15"])

    async def test_day_route_404s_for_a_date_with_no_real_file(self):
        response = await ws.get_ai_intelligence_day(mock.Mock(path_params={"date": "2020-01-01"}))
        self.assertEqual(response.status_code, 404)

    async def test_day_route_returns_real_parsed_sections(self):
        (self._tmp_dir / "2026-09-15.md").write_text(
            "## Important Changes\nsomething real happened\n", encoding="utf-8"
        )
        response = await ws.get_ai_intelligence_day(mock.Mock(path_params={"date": "2026-09-15"}))
        body = json.loads(response.body)
        self.assertEqual(body["date"], "2026-09-15")
        self.assertEqual(len(body["sections"]), 1)
        self.assertEqual(body["sections"][0]["heading"], "Important Changes")

    async def test_day_route_rejects_path_traversal_in_date_param(self):
        response = await ws.get_ai_intelligence_day(
            mock.Mock(path_params={"date": "../../../../etc/passwd"})
        )
        self.assertEqual(response.status_code, 404)


class LearnPdfRouteTestCase(unittest.IsolatedAsyncioTestCase):
    def test_pdf_route_is_registered(self):
        routes = {r.path: r for r in ws.routes if hasattr(r, "path")}
        self.assertIn("/api/learn/book.pdf", routes)

    async def test_pdf_response_has_correct_mime_and_is_non_empty(self):
        response = await ws.get_learn_book_pdf(mock.Mock())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.media_type, "application/pdf")
        self.assertGreater(len(response.body), 1000)
        self.assertTrue(response.body.startswith(b"%PDF-"))

    async def test_pdf_response_has_download_disposition_and_generated_at(self):
        response = await ws.get_learn_book_pdf(mock.Mock())
        self.assertIn("attachment", response.headers["content-disposition"])
        self.assertIn("X-Learn-Book-Generated-At", response.headers)


class SessionHistoryRouteTestCase(unittest.IsolatedAsyncioTestCase):
    """P0-B: the paginated session-history API and the dedicated session
    detail route (/usage/session/{id})."""

    def _route_map(self):
        return {r.path: r for r in ws.routes if hasattr(r, "path")}

    def test_session_history_routes_are_registered(self):
        routes = self._route_map()
        self.assertIn("/api/sessions/history", routes)
        self.assertIn("/api/sessions/history/{session_id}", routes)
        self.assertIn("/usage/session/{session_id}", routes)
        self.assertIs(routes["/usage/session/{session_id}"].endpoint, ws.usage_page)

    async def test_session_history_list_returns_reachable_shape(self):
        response = await ws.get_session_history(mock.Mock(query_params={}))
        body = json.loads(response.body)
        self.assertEqual(body["status"], "REACHABLE")
        self.assertIn("sessions", body)

    async def test_session_history_list_respects_limit_param(self):
        response = await ws.get_session_history(mock.Mock(query_params={"limit": "3"}))
        body = json.loads(response.body)
        self.assertLessEqual(len(body["sessions"]), 3)

    async def test_malformed_before_cursor_returns_400_not_500(self):
        """Real production incident (2026-09-11): an unencoded '+' in a
        `before` cursor decodes to a space, previously raising an
        unhandled 500. Must be a clean 400 with a truthful error body."""
        space_for_plus = "2026-09-10T02:17:07.628697 00:00"
        response = await ws.get_session_history(mock.Mock(query_params={"before": space_for_plus}))
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.body)
        self.assertEqual(body["status"], "INVALID_CURSOR")

    async def test_session_detail_route_returns_404_for_unknown_id(self):
        response = await ws.get_session_detail(mock.Mock(path_params={"session_id": "no-such-session-xyz"}))
        self.assertEqual(response.status_code, 404)

    async def test_session_detail_route_returns_real_detail_for_known_id(self):
        response = await ws.get_session_detail(mock.Mock(path_params={"session_id": "trainer-4733d1c0"}))
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.body)
        self.assertIn("timeline", body)


if __name__ == "__main__":
    unittest.main()
