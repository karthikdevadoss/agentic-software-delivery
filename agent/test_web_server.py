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
import sys
import unittest
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


if __name__ == "__main__":
    unittest.main()
