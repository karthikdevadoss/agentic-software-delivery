"""
Focused tests for agent/claude_code_hook.py + the claude_code source added
to agent/event_ledger.py (CLAUDE DEVELOPMENT TELEMETRY task).

Most tests call claude_code_hook.main() in-process with a redirected
SPOOL_PATH (fast, deterministic, no real subprocess/network needed) — the
hook script's actual job is "parse stdin JSON, append to spool", which is
fully exercised this way. One test spawns the REAL script as a subprocess
to prove the whole invocation path works end to end and measures real
wall-clock time. A couple of tests go through to the real live database
(sync_spool()) to prove the claude_code source lands there correctly and
stays distinguishable from Workbench (PRODUCT_RUNTIME) events.

Run: python agent/test_claude_code_hook.py
"""

import io
import json
import subprocess
import sys
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

import claude_code_hook
import event_ledger as el


def _run_hook_inprocess(stdin_json: dict):
    with mock.patch.object(sys, "stdin", io.StringIO(json.dumps(stdin_json))):
        claude_code_hook.main()


class SpoolIsolatedTestCase(unittest.TestCase):
    """Redirects event_ledger.SPOOL_PATH to a throwaway file per test so
    these never touch the real local spool a live session might be using,
    and never require network access."""

    def setUp(self):
        self.spool_path = Path(el.SPOOL_PATH).parent / f"claude_hook_test_spool_{uuid.uuid4().hex[:8]}.jsonl"
        self._spool_patcher = mock.patch.object(el, "SPOOL_PATH", self.spool_path)
        self._spool_patcher.start()
        # Never let a test accidentally spawn a real background sync process.
        self._sync_patcher = mock.patch.object(el, "trigger_background_sync", return_value={"spawned": False})
        self._sync_patcher.start()

    def tearDown(self):
        self._sync_patcher.stop()
        self._spool_patcher.stop()
        if self.spool_path.exists():
            self.spool_path.unlink()

    def _spooled_events(self):
        if not self.spool_path.exists():
            return []
        return [json.loads(l) for l in self.spool_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def test_user_prompt_submit_captured(self):
        _run_hook_inprocess({
            "hook_event_name": "UserPromptSubmit", "session_id": "sess-a",
            "prompt": "Add a health check endpoint please.",
        })
        events = self._spooled_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "user_prompt_submitted")
        self.assertEqual(events[0]["source"], "claude_code")
        self.assertEqual(events[0]["payload"]["prompt_char_count"], len("Add a health check endpoint please."))
        self.assertEqual(events[0]["payload"]["prompt_word_count"], 6)

    def test_tool_start_and_completion_captured(self):
        _run_hook_inprocess({"hook_event_name": "PreToolUse", "session_id": "sess-b", "tool_name": "Bash", "tool_input": {"command": "git status"}})
        _run_hook_inprocess({"hook_event_name": "PostToolUse", "session_id": "sess-b", "tool_name": "Bash", "tool_response": "nothing to commit"})
        events = self._spooled_events()
        self.assertEqual([e["event_type"] for e in events], ["tool_call_started", "tool_call_completed"])
        self.assertTrue(all(e["tool_name"] == "Bash" for e in events))

    def test_failed_tool_event_captured(self):
        _run_hook_inprocess({"hook_event_name": "PostToolUseFailure", "session_id": "sess-c", "tool_name": "Bash", "tool_response": "command not found"})
        events = self._spooled_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "tool_call_failed")

    def test_session_correlation(self):
        for hook_event in ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "SessionEnd"):
            _run_hook_inprocess({"hook_event_name": hook_event, "session_id": "sess-correlated", "tool_name": "Bash"})
        events = self._spooled_events()
        self.assertEqual(len(events), 6)
        self.assertTrue(all(e["session_id"] == "sess-correlated" for e in events))

    def test_timestamps_support_duration_reconstruction(self):
        _run_hook_inprocess({"hook_event_name": "SessionStart", "session_id": "sess-d"})
        time.sleep(0.05)
        _run_hook_inprocess({"hook_event_name": "SessionEnd", "session_id": "sess-d"})
        events = self._spooled_events()
        from datetime import datetime
        t0 = datetime.fromisoformat(events[0]["timestamp_utc"])
        t1 = datetime.fromisoformat(events[1]["timestamp_utc"])
        self.assertGreater((t1 - t0).total_seconds(), 0)

    def test_secret_shaped_prompt_text_is_redacted(self):
        _run_hook_inprocess({
            "hook_event_name": "UserPromptSubmit", "session_id": "sess-e",
            "prompt": "here is my key sk-ant-realsecretvalue1234567890 please use it",
        })
        events = self._spooled_events()
        excerpt = events[0]["payload"]["prompt_excerpt"]
        self.assertNotIn("sk-ant-realsecretvalue1234567890", excerpt)
        self.assertIn("REDACTED", excerpt)

    def test_malformed_stdin_does_not_raise(self):
        with mock.patch.object(sys, "stdin", io.StringIO("not valid json {{{")):
            claude_code_hook.main()  # must not raise
        # Doesn't crash AND doesn't silently drop the occurrence — it's
        # recorded as an honestly-unrecognized event, never fabricated
        # into a real hook_event_name that didn't actually parse.
        events = self._spooled_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "claude_code_unknown")

    def test_unknown_hook_event_name_does_not_crash_and_is_labeled_honestly(self):
        _run_hook_inprocess({"hook_event_name": "SomeFutureHookNobodyToldUsAbout", "session_id": "sess-f"})
        events = self._spooled_events()
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0]["event_type"].startswith("claude_code_"))


class RealSubprocessSpeedTestCase(unittest.TestCase):
    """Proves the ACTUAL script (not just the imported function) returns
    fast when run exactly as Claude Code itself would invoke it — zero
    network calls in the synchronous path is the whole point of
    spool_only(); this is the regression test for that invariant."""

    def test_real_hook_invocation_completes_quickly(self):
        script = Path(__file__).resolve().parent / "claude_code_hook.py"
        stdin_payload = json.dumps({
            "hook_event_name": "PreToolUse", "session_id": "sess-speed-test",
            "tool_name": "Bash", "tool_input": {"command": "echo hi"},
        })
        start = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, str(script)], input=stdin_payload,
            capture_output=True, text=True, timeout=10, cwd=str(script.parent),
        )
        elapsed_s = time.perf_counter() - start
        self.assertEqual(proc.returncode, 0)
        # Generous bound: real measured cost is Python interpreter startup
        # (~0.2-0.3s), never a multi-second network round trip.
        self.assertLess(elapsed_s, 3.0, f"hook took {elapsed_s:.2f}s — should never block on network")


class RealLedgerDistinctnessTestCase(unittest.TestCase):
    """Proves claude_code/PRODUCT_DEVELOPMENT events genuinely land in and
    stay distinguishable from PRODUCT_RUNTIME (Workbench) events in the
    real live database — not just in the spool file."""

    def test_dev_event_is_queryable_and_distinct_from_workbench_source(self):
        session_id = f"sess-distinct-{uuid.uuid4().hex[:8]}"
        result = el.record_event(
            "user_prompt_submitted", session_id=session_id, source="claude_code",
            activity_class=el.ACTIVITY_CLASS_PRODUCT_DEVELOPMENT,
            payload={"prompt_excerpt": "real dev-telemetry distinctness test"},
        )
        self.assertTrue(result["remote_persisted"], msg=result)

        conn = el._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT source, activity_class FROM delivery_events WHERE session_id = %s",
                    (session_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        self.assertEqual(row, ("claude_code", "PRODUCT_DEVELOPMENT"))

    def test_spool_only_then_real_sync_lands_in_database(self):
        run_marker = f"sess-spoolonly-sync-{uuid.uuid4().hex[:8]}"
        spool_path = Path(el.SPOOL_PATH).parent / f"claude_hook_test_spool_{uuid.uuid4().hex[:8]}.jsonl"
        with mock.patch.object(el, "SPOOL_PATH", spool_path):
            result = el.spool_only("user_prompt_submitted", session_id=run_marker, source="claude_code",
                                    activity_class=el.ACTIVITY_CLASS_PRODUCT_DEVELOPMENT)
            self.assertFalse(result["remote_persisted"])
            self.assertTrue(result["spooled"])
            # sync_spool() reads the CURRENT el.SPOOL_PATH — still patched here.
            sync_result = el.sync_spool()
        self.assertEqual(sync_result["synced"], 1)
        if spool_path.exists():
            spool_path.unlink()

        conn = el._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT source FROM delivery_events WHERE session_id = %s", (run_marker,))
                row = cur.fetchone()
        finally:
            conn.close()
        self.assertEqual(row, ("claude_code",))


class PermissionConfigTestCase(unittest.TestCase):
    """Structural proof of Section 7: narrow, specific allow rules exist
    for safe read-only commands, and no broad/dangerous rule was added.
    Does not (and cannot, from a unit test) invoke Claude Code's own
    permission engine — that requires a real session. This proves the
    CONFIGURATION itself is narrow, which is the actual safety property."""

    @classmethod
    def setUpClass(cls):
        settings_path = Path(__file__).resolve().parent.parent / ".claude" / "settings.local.json"
        cls.settings = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
        cls.allow = cls.settings.get("permissions", {}).get("allow", [])

    def test_expected_safe_rules_present(self):
        for expected in ("Bash(git status)", "Bash(git diff)", "Bash(git log)", "Bash(git rev-parse *)"):
            self.assertIn(expected, self.allow)

    def test_no_blanket_bash_rule(self):
        self.assertNotIn("Bash(*)", self.allow)
        self.assertNotIn("Bash", self.allow)

    def test_no_blanket_git_rule(self):
        self.assertNotIn("Bash(git *)", self.allow)
        self.assertNotIn("Bash(git:*)", self.allow)

    def test_no_dangerous_command_rules(self):
        dangerous_fragments = ("push", "reset --hard", "clean -f", "rm -rf", "--dangerously-skip-permissions")
        for rule in self.allow:
            for fragment in dangerous_fragments:
                self.assertNotIn(fragment, rule, f"dangerous fragment {fragment!r} found in allow rule {rule!r}")

    def test_bypass_permissions_not_enabled_anywhere_in_settings(self):
        raw = json.dumps(self.settings)
        self.assertNotIn("bypassPermissions", raw)
        self.assertNotIn("dangerously-skip-permissions", raw)


if __name__ == "__main__":
    unittest.main()
