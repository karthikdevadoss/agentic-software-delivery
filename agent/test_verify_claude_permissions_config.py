"""
Regression tests for agent/verify_claude_permissions_config.py — the
permanent guard against AEQ-023's exact defect class (see
docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml): a blanket, no-confirmation
"Bash(railway up *)" auto-allow rule in .claude/settings.local.json let a
background fork subagent deploy to production despite an explicit
prompt-level instruction not to. Mirrors
agent/test_verify_claude_hooks_config.py's established pattern: mocked
tests cover the verification logic, a separate, deliberately unmocked
test proves THIS machine's real, current configuration is actually safe.

Run: python agent/test_verify_claude_permissions_config.py
"""

import json
import unittest
from pathlib import Path
from unittest import mock

import verify_claude_permissions_config as vp


class VerificationLogicTestCase(unittest.TestCase):
    def _run_with(self, project_local_allow=None, project_allow=None, user_allow=None):
        contents = {
            vp._project_local_settings_path(): {"permissions": {"allow": project_local_allow or []}},
            vp._project_settings_path(): {"permissions": {"allow": project_allow or []}},
            vp._user_settings_path(): {"permissions": {"allow": user_allow or []}},
        }

        def fake_exists(self):
            return True

        def fake_read_text(self, encoding="utf-8"):
            return json.dumps(contents[self])

        with mock.patch.object(Path, "exists", fake_exists), \
             mock.patch.object(Path, "read_text", fake_read_text):
            return vp.verify()

    def test_empty_allow_lists_report_no_problems(self):
        self.assertEqual(self._run_with(), [])

    def test_safe_allow_rules_report_no_problems(self):
        problems = self._run_with(project_local_allow=[
            "Bash(railway status *)", "Bash(git push *)", "Bash(curl *)", "WebSearch",
        ])
        self.assertEqual(problems, [], msg=problems)

    def test_the_exact_real_incident_rule_is_flagged(self):
        # The literal rule that was actually present on this machine
        # before this fix (docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml AEQ-023).
        problems = self._run_with(project_local_allow=["Bash(railway up *)"])
        self.assertTrue(any("railway up" in p and "production deployment" in p for p in problems), problems)

    def test_railway_domain_mutation_is_flagged(self):
        problems = self._run_with(project_local_allow=["Bash(railway domain *)"])
        self.assertTrue(any("DNS/routing" in p for p in problems), problems)

    def test_force_push_is_flagged(self):
        problems = self._run_with(project_local_allow=["Bash(git push --force *)"])
        self.assertTrue(any("destructive history rewrite" in p for p in problems), problems)

    def test_rm_rf_is_flagged(self):
        problems = self._run_with(project_local_allow=["Bash(rm -rf *)"])
        self.assertTrue(any("recursive destructive delete" in p for p in problems), problems)

    def test_a_dangerous_rule_in_user_level_settings_is_also_caught(self):
        # The incident could just as easily have been in the user-level
        # file instead of the project-local one -- this must not only
        # check one location.
        problems = self._run_with(user_allow=["Bash(railway up *)"])
        self.assertTrue(any("railway up" in p for p in problems), problems)

    def test_ordinary_non_bash_rules_are_never_flagged(self):
        problems = self._run_with(project_local_allow=["Skill(claude-api)", "WebFetch(domain:claude.com)"])
        self.assertEqual(problems, [], msg=problems)

    def test_malformed_json_is_reported_not_crashed(self):
        def fake_exists(self):
            return self == vp._project_local_settings_path()

        def fake_read_text(self, encoding="utf-8"):
            return "{not valid json"

        with mock.patch.object(Path, "exists", fake_exists), \
             mock.patch.object(Path, "read_text", fake_read_text):
            problems = vp.verify()  # must not raise
        self.assertTrue(any("not valid JSON" in p for p in problems), problems)

    def test_missing_files_entirely_report_no_problems_not_a_crash(self):
        def fake_exists(self):
            return False

        with mock.patch.object(Path, "exists", fake_exists):
            problems = vp.verify()
        self.assertEqual(problems, [])


class RealMachineConfigTestCase(unittest.TestCase):
    """Deliberately NOT mocked: checks THIS machine's actual, real
    permission configuration. This is the regression guard for AEQ-023 --
    if a dangerous blanket auto-allow rule is ever reintroduced (by a
    human or a future session), this test fails on the very next run
    instead of the gap going unnoticed until another incident."""

    def test_real_permissions_config_on_this_machine_has_no_dangerous_auto_allow_rule(self):
        problems = vp.verify()
        self.assertEqual(problems, [], msg=(
            f"Real Claude Code permission configuration on this machine has a "
            f"problem: {problems}. See docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml "
            f"AEQ-023 for the real incident this guards against."
        ))


if __name__ == "__main__":
    unittest.main()
