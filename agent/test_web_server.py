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
import unittest

import web_server as ws


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
    TERMINAL_STATES = ["COMPLETED", "FAILED", "NO_CHANGE_NEEDED"]

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


if __name__ == "__main__":
    unittest.main()
