"""
Regression tests for agent/verify_claude_hooks_config.py — guards against
exactly the incident this file exists to prevent (see docs/LESSONS.md):
Claude Code's own permission-remember mechanism silently rewrites
.claude/settings.local.json and drops any key (like 'hooks') it doesn't
manage, so a hooks configuration placed there quietly disappears with no
error. "A telemetry capability is VERIFIED only when the real producer
emits an event and the durable remote store contains it" (see
docs/CONSTITUTION.md) — this suite covers the CONFIGURATION layer only;
agent/test_claude_code_hook.py covers the script/spool/ledger layer; real
end-to-end proof requires an actual Claude Code session (see
docs/RECOVERY.md).

Run: python agent/test_verify_claude_hooks_config.py
"""

import json
import unittest
from pathlib import Path
from unittest import mock

import verify_claude_hooks_config as vc


def _good_user_settings():
    return {
        "hooks": {
            event: [{"hooks": [{
                "type": "command",
                "command": 'python "${CLAUDE_PROJECT_DIR}/agent/claude_code_hook.py"',
                "timeout": 5,
            }]}]
            for event in vc.EXPECTED_HOOK_EVENTS
        }
    }


class VerificationLogicTestCase(unittest.TestCase):
    """Mocked-filesystem tests — fast, deterministic, cover every branch
    of the verification logic without touching this machine's real
    config (that's RealMachineConfigTestCase below, deliberately
    separate)."""

    def _run_with(self, project_local_content, user_content):
        texts = {
            vc._project_local_settings_path(): json.dumps(project_local_content),
            vc._user_settings_path(): json.dumps(user_content),
        }

        def fake_exists(self):
            return True

        def fake_read_text(self, encoding="utf-8"):
            return texts[self]

        with mock.patch.object(Path, "exists", fake_exists), \
             mock.patch.object(Path, "read_text", fake_read_text):
            return vc.verify()

    def test_correct_configuration_reports_no_problems(self):
        problems = self._run_with({"permissions": {"allow": []}}, _good_user_settings())
        self.assertEqual(problems, [], msg=problems)

    def test_hooks_in_project_local_settings_is_flagged(self):
        bad_project_local = {"permissions": {"allow": []}, "hooks": {"SessionStart": []}}
        problems = self._run_with(bad_project_local, {"theme": "dark"})
        self.assertTrue(any("known-bad location" in p for p in problems), problems)

    def test_missing_hooks_key_in_user_settings_is_flagged(self):
        problems = self._run_with({"permissions": {"allow": []}}, {"theme": "dark"})
        self.assertTrue(any("no 'hooks' object" in p for p in problems), problems)

    def test_missing_hook_event_is_flagged(self):
        incomplete = _good_user_settings()
        del incomplete["hooks"]["SubagentStop"]
        problems = self._run_with({"permissions": {"allow": []}}, incomplete)
        self.assertTrue(any("SubagentStop" in p for p in problems), problems)

    def test_command_not_referencing_hook_script_is_flagged(self):
        broken = _good_user_settings()
        broken["hooks"]["Stop"][0]["hooks"][0]["command"] = "echo not the real hook"
        problems = self._run_with({"permissions": {"allow": []}}, broken)
        self.assertTrue(any("does not reference" in p for p in problems), problems)

    def test_command_not_using_project_dir_variable_is_flagged(self):
        broken = _good_user_settings()
        broken["hooks"]["Stop"][0]["hooks"][0]["command"] = "python C:/hardcoded/path/claude_code_hook.py"
        problems = self._run_with({"permissions": {"allow": []}}, broken)
        self.assertTrue(any("CLAUDE_PROJECT_DIR" in p for p in problems), problems)

    def test_malformed_user_settings_json_is_flagged_not_crashed(self):
        def fake_exists(self):
            return True

        def fake_read_text(self, encoding="utf-8"):
            if self == vc._project_local_settings_path():
                return json.dumps({"permissions": {"allow": []}})
            return "{not valid json"

        with mock.patch.object(Path, "exists", fake_exists), \
             mock.patch.object(Path, "read_text", fake_read_text):
            problems = vc.verify()  # must not raise
        self.assertTrue(any("not valid JSON" in p for p in problems), problems)

    def test_missing_user_settings_file_entirely_is_flagged(self):
        def fake_exists(self):
            return self == vc._project_local_settings_path()  # only project-local exists

        def fake_read_text(self, encoding="utf-8"):
            return json.dumps({"permissions": {"allow": []}})

        with mock.patch.object(Path, "exists", fake_exists), \
             mock.patch.object(Path, "read_text", fake_read_text):
            problems = vc.verify()
        self.assertTrue(any("does not exist" in p for p in problems), problems)


class RealMachineConfigTestCase(unittest.TestCase):
    """Deliberately NOT mocked: checks THIS machine's actual, real
    ~/.claude/settings.json and .claude/settings.local.json. This is the
    regression guard for the exact incident this file exists to prevent —
    if hooks silently disappear again for any reason, this test fails on
    the very next run instead of the gap going unnoticed for days."""

    def test_real_hooks_config_on_this_machine_is_currently_correct(self):
        problems = vc.verify()
        self.assertEqual(problems, [], msg=(
            "Real Claude Code hooks configuration on this machine has a "
            f"problem: {problems}. If this is because you're running "
            "these tests on a machine that was never set up for "
            "development telemetry, that's expected — see "
            "docs/RECOVERY.md's 'Recovering Claude Code development-"
            "telemetry hooks' section."
        ))


if __name__ == "__main__":
    unittest.main()
