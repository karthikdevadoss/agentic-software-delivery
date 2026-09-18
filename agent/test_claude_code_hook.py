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
import shutil
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
        """Real incident (2026-09-18): this and the sibling test below used
        a 'sess-distinct-...'/'sess-spoolonly-sync-...' session_id and
        never cleaned up their real inserted row afterward -- 165+ such
        rows had silently accumulated in the shared production ledger
        across many prior sessions by the time this was found (via the
        Owner's own screenshot showing unrelated test pollution). Session-
        history/dev-cost-summary's allowlist filters now hide these from
        view regardless of prefix, but a test still should not leave a
        permanent, meaningless row in a shared production database just
        because it happens to be invisible -- delete what you insert."""
        session_id = f"sess-distinct-{uuid.uuid4().hex[:8]}"
        result = el.record_event(
            "user_prompt_submitted", session_id=session_id, source="claude_code",
            activity_class=el.ACTIVITY_CLASS_PRODUCT_DEVELOPMENT,
            payload={"prompt_excerpt": "real dev-telemetry distinctness test"},
        )
        self.assertTrue(result["remote_persisted"], msg=result)
        try:
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
        finally:
            el.delete_event_for_test_cleanup(result["event_id"])

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

        fetched = None
        try:
            conn = el._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT event_id, source FROM delivery_events WHERE session_id = %s", (run_marker,))
                    fetched = cur.fetchone()
            finally:
                conn.close()
            self.assertEqual(fetched[1] if fetched else None, "claude_code")
        finally:
            if fetched:
                el.delete_event_for_test_cleanup(fetched[0])


class PermissionConfigTestCase(unittest.TestCase):
    """Structural proof of Section 7: no broad/dangerous rule exists in
    the local permission config. Does not (and cannot, from a unit test)
    invoke Claude Code's own permission engine — that requires a real
    session. This proves the CONFIGURATION itself stays safe, which is
    the actual invariant — not any specific set of rules. This file
    (.claude/settings.local.json) is gitignored and legitimately
    creator-editable at any time (e.g. to add/remove convenience rules),
    so this suite deliberately does NOT assert any particular rule is
    present — only that nothing dangerous is, regardless of how the
    creator has tuned it since."""

    @classmethod
    def setUpClass(cls):
        settings_path = Path(__file__).resolve().parent.parent / ".claude" / "settings.local.json"
        cls.settings = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
        cls.allow = cls.settings.get("permissions", {}).get("allow", [])

    def test_no_blanket_bash_rule(self):
        self.assertNotIn("Bash(*)", self.allow)
        self.assertNotIn("Bash", self.allow)

    def test_no_blanket_git_rule(self):
        self.assertNotIn("Bash(git *)", self.allow)
        self.assertNotIn("Bash(git:*)", self.allow)

    def test_no_dangerous_command_rules(self):
        # Matches the actual original safety instruction verbatim ("force
        # push", "reset --hard", "git clean", ...) — a plain, non-force
        # `git push` is recoverable (revert commit) and was never actually
        # called out as dangerous; an earlier version of this test
        # over-broadened "force push" to bare "push" and flagged a real,
        # legitimate `Bash(git push *)` rule that had since been added —
        # fixed here to match what was actually specified, not a stricter
        # invented standard.
        dangerous_fragments = (
            "push --force", "push -f", "reset --hard", "clean -f", "rm -rf",
            "--dangerously-skip-permissions", "bypassPermissions",
        )
        for rule in self.allow:
            for fragment in dangerous_fragments:
                self.assertNotIn(fragment, rule, f"dangerous fragment {fragment!r} found in allow rule {rule!r}")

    def test_bypass_permissions_not_enabled_anywhere_in_settings(self):
        raw = json.dumps(self.settings)
        self.assertNotIn("bypassPermissions", raw)
        self.assertNotIn("dangerously-skip-permissions", raw)


class _NoContentAccessDict(dict):
    """A dict that raises if 'content' is ever looked up — used to prove
    _extract_usage_from_transcript genuinely never reads a message's
    content/text, not merely that the returned shape happens to omit it."""

    def __getitem__(self, key):
        if key == "content":
            raise AssertionError("_extract_usage_from_transcript accessed 'content' -- it must never read message text")
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key == "content":
            raise AssertionError("_extract_usage_from_transcript accessed 'content' -- it must never read message text")
        return super().get(key, default)


class ExtractUsageFromTranscriptTestCase(unittest.TestCase):
    """agent/claude_code_hook.py's _extract_usage_from_transcript -- reads
    a real Claude Code session transcript JSONL and sums real, provider-
    returned token usage. The one invariant this whole feature depends on:
    it must NEVER read a message's content/text, only its usage object."""

    def setUp(self):
        self.tmp_dir = Path(el.SPOOL_PATH).parent / f"claude_hook_transcript_test_{uuid.uuid4().hex[:8]}"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        for f in self.tmp_dir.glob("*"):
            f.unlink()
        self.tmp_dir.rmdir()

    def _write_transcript(self, lines):
        path = self.tmp_dir / "transcript.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for line in lines:
                f.write(json.dumps(line) + "\n")
        return path

    def test_returns_none_for_missing_path(self):
        self.assertIsNone(claude_code_hook._extract_usage_from_transcript(None))
        self.assertIsNone(claude_code_hook._extract_usage_from_transcript(""))

    def test_returns_none_for_nonexistent_file(self):
        missing = self.tmp_dir / "does-not-exist.jsonl"
        self.assertIsNone(claude_code_hook._extract_usage_from_transcript(str(missing)))

    def test_returns_none_when_no_assistant_messages_have_usage(self):
        path = self._write_transcript([
            {"type": "user", "message": {"role": "user", "content": "hi"}},
            {"type": "system", "message": {}},
        ])
        self.assertIsNone(claude_code_hook._extract_usage_from_transcript(str(path)))

    def test_sums_real_usage_across_multiple_assistant_messages(self):
        path = self._write_transcript([
            {"type": "assistant", "message": {"role": "assistant", "model": "claude-sonnet-5",
             "usage": {"input_tokens": 10, "output_tokens": 20,
                        "cache_creation_input_tokens": 5, "cache_read_input_tokens": 100}}},
            {"type": "user", "message": {"role": "user", "content": "irrelevant"}},
            {"type": "assistant", "message": {"role": "assistant", "model": "claude-sonnet-5",
             "usage": {"input_tokens": 2, "output_tokens": 483,
                        "cache_creation_input_tokens": 0, "cache_read_input_tokens": 43564}}},
        ])
        result = claude_code_hook._extract_usage_from_transcript(str(path))
        self.assertIsNotNone(result)
        self.assertEqual(result["input_tokens"], 12)
        self.assertEqual(result["output_tokens"], 503)
        self.assertEqual(result["cache_creation_input_tokens"], 5)
        self.assertEqual(result["cache_read_input_tokens"], 43664)
        self.assertEqual(result["message_count"], 2)
        self.assertEqual(result["model"], "claude-sonnet-5")

    def test_malformed_lines_are_skipped_not_fatal(self):
        path = self.tmp_dir / "transcript.jsonl"
        with path.open("w", encoding="utf-8") as f:
            f.write("not json at all\n")
            f.write(json.dumps({"type": "assistant", "message": {
                "role": "assistant", "model": "claude-sonnet-5",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }}) + "\n")
            f.write("\n")  # blank line
        result = claude_code_hook._extract_usage_from_transcript(str(path))
        self.assertIsNotNone(result)
        self.assertEqual(result["message_count"], 1)

    def test_never_accesses_message_content_even_when_present(self):
        """The real, structural guarantee: a message dict that raises on
        any 'content' lookup must still be processed correctly -- proving
        the function's code path genuinely never touches that key, not
        merely that its return value happens to omit it."""
        real_transcript_line = {
            "type": "assistant",
            "message": _NoContentAccessDict({
                "role": "assistant",
                "model": "claude-sonnet-5",
                "usage": {"input_tokens": 7, "output_tokens": 9},
                "content": "SHOULD NEVER BE READ",
            }),
        }
        # json.dumps would need to serialize the dict, which doesn't
        # trigger __getitem__/get -- write real JSON, then monkeypatch
        # json.loads for this one test to return the guarded dict instead,
        # so the guard is active on the object the function actually
        # receives from parsing, not just on an object we never pass in.
        path = self._write_transcript([{
            "type": "assistant",
            "message": {"role": "assistant", "model": "claude-sonnet-5",
                        "usage": {"input_tokens": 7, "output_tokens": 9},
                        "content": "SHOULD NEVER BE READ"},
        }])

        real_loads = json.loads

        def guarded_loads(s):
            parsed = real_loads(s)
            if isinstance(parsed, dict) and parsed.get("type") == "assistant":
                parsed["message"] = _NoContentAccessDict(parsed["message"])
            return parsed

        with mock.patch.object(claude_code_hook.json, "loads", side_effect=guarded_loads):
            result = claude_code_hook._extract_usage_from_transcript(str(path))

        self.assertIsNotNone(result)
        self.assertEqual(result["input_tokens"], 7)
        self.assertEqual(result["output_tokens"], 9)


class IterSubagentTranscriptsTestCase(unittest.TestCase):
    """agent/claude_code_hook.py's _iter_subagent_transcripts -- real gap
    found 2026-09-18 (the 40 EUR overnight-session incident): explaining
    per-task cost required manually locating <session>/subagents/*.jsonl
    by hand. This is the automated version of that exact manual process,
    following the same on-disk convention discovered during that
    investigation."""

    def setUp(self):
        self.tmp_dir = Path(el.SPOOL_PATH).parent / f"claude_hook_subagent_test_{uuid.uuid4().hex[:8]}"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.main_transcript = self.tmp_dir / "main-session.jsonl"
        self.main_transcript.write_text("", encoding="utf-8")
        self.subagents_dir = self.tmp_dir / "main-session" / "subagents"
        self.subagents_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _write_subagent(self, agent_id, meta, usage_lines):
        (self.subagents_dir / f"{agent_id}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
        with (self.subagents_dir / f"{agent_id}.jsonl").open("w", encoding="utf-8") as f:
            for line in usage_lines:
                f.write(json.dumps(line) + "\n")

    def test_no_subagents_dir_yields_nothing(self):
        lone = self.tmp_dir / "lonely.jsonl"
        lone.write_text("", encoding="utf-8")
        self.assertEqual(list(claude_code_hook._iter_subagent_transcripts(str(lone))), [])

    def test_missing_main_transcript_yields_nothing(self):
        self.assertEqual(list(claude_code_hook._iter_subagent_transcripts(None)), [])
        self.assertEqual(list(claude_code_hook._iter_subagent_transcripts(str(self.tmp_dir / "missing.jsonl"))), [])

    def test_reads_real_meta_and_usage_for_each_subagent(self):
        self._write_subagent(
            "agent-abc123",
            {"agentType": "fork", "isFork": True, "description": "Implement Phase 1: cost accounting fix", "worktreeBranch": "worktree-agent-abc123"},
            [{"type": "assistant", "message": {"role": "assistant", "model": "claude-sonnet-5",
              "usage": {"input_tokens": 5, "output_tokens": 100, "cache_creation_input_tokens": 2, "cache_read_input_tokens": 50}}}],
        )
        self._write_subagent(
            "agent-def456",
            {"agentType": "Explore", "description": "Trace usage/cost data path"},
            [{"type": "assistant", "message": {"role": "assistant", "model": "claude-sonnet-5",
              "usage": {"input_tokens": 1, "output_tokens": 10, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 5}}}],
        )
        results = list(claude_code_hook._iter_subagent_transcripts(str(self.main_transcript)))
        self.assertEqual(len(results), 2)
        by_id = {meta["agent_id"]: (meta, usage) for meta, usage in results}
        fork_meta, fork_usage = by_id["agent-abc123"]
        self.assertEqual(fork_meta["agentType"], "fork")
        self.assertEqual(fork_meta["worktreeBranch"], "worktree-agent-abc123")
        self.assertEqual(fork_usage["output_tokens"], 100)
        explore_meta, explore_usage = by_id["agent-def456"]
        self.assertEqual(explore_meta["agentType"], "Explore")
        self.assertEqual(explore_usage["output_tokens"], 10)

    def test_subagent_with_no_usage_data_is_skipped_not_fabricated(self):
        self._write_subagent("agent-empty", {"agentType": "Explore", "description": "no-op"}, [])
        self.assertEqual(list(claude_code_hook._iter_subagent_transcripts(str(self.main_transcript))), [])

    def test_malformed_meta_json_does_not_crash_the_whole_scan(self):
        (self.subagents_dir / "agent-badmeta.meta.json").write_text("not json", encoding="utf-8")
        with (self.subagents_dir / "agent-badmeta.jsonl").open("w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "model": "claude-sonnet-5",
                                 "usage": {"input_tokens": 1, "output_tokens": 1}}}) + "\n")
        results = list(claude_code_hook._iter_subagent_transcripts(str(self.main_transcript)))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0]["agent_id"], "agent-badmeta")


if __name__ == "__main__":
    unittest.main()
