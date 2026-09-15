"""
Tests for agent/triage_promotion.py -- the Triage Lab candidate-patch
promotion pipeline.

Git workflow steps (clone/commit/push) use a REAL local git repository
as "origin" -- never a mock of subprocess or git's own behavior, the
same discipline test_demo_execution.py already established for exactly
this class of code. Railway-dependent functions (deploy trigger/wait)
are mocked (no real Railway account access from a test suite), and the
admin-login/approve HTTP calls are mocked via triage_execution._request,
matching test_triage_execution.py's own existing pattern.

Run: python agent/test_triage_promotion.py
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import triage_promotion as tp


def _git(args, cwd):
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result.stdout


class RealLocalGitPromotionTestCase(unittest.TestCase):
    """A real, disposable local git repository stands in for the real
    public GitHub repo, exactly like test_demo_execution.py's own
    RealLocalGitWorkflowTestCase."""

    TARGET_REL = "com/example/customer/triage/TriageScenarioBService.java"

    def setUp(self):
        tp._LAST_VERIFIED_CANDIDATE.clear()
        self.addCleanup(tp._LAST_VERIFIED_CANDIDATE.clear)

        self.tmp_root = tempfile.mkdtemp(prefix="test-promotion-origin-")
        self.addCleanup(lambda: shutil.rmtree(self.tmp_root, ignore_errors=True))
        self.origin = Path(self.tmp_root) / "origin"
        self.origin.mkdir()
        _git(["init", "-q", "-b", "master"], self.origin)
        _git(["config", "user.email", "test@example.com"], self.origin)
        _git(["config", "user.name", "Test"], self.origin)
        full_path = self.origin / "app" / "src" / "main" / "java" / self.TARGET_REL
        full_path.parent.mkdir(parents=True)
        self.baseline_source = "public class TriageScenarioBService { /* BUGGY */ }\n"
        full_path.write_text(self.baseline_source, encoding="utf-8")
        _git(["add", "-A"], self.origin)
        _git(["commit", "-q", "-m", "initial"], self.origin)

        self.candidate_source = "public class TriageScenarioBService { /* FIXED */ }\n"

    def _record_valid_candidate(self, scenario="b"):
        tp.record_verified_candidate(scenario, self.TARGET_REL, self.baseline_source, self.candidate_source, "diff...")

    def _admin_login_side_effect(self, *args, **kwargs):
        method, path = args[0], args[1]
        if path == "/auth/login":
            return {"accessToken": "real-admin-jwt", "role": "ADMIN"}
        if path.startswith("/internal/triage/") and path.endswith("/approve"):
            return {"fixApplied": True}
        raise AssertionError(f"unexpected _request call: {method} {path}")

    def test_no_verified_candidate_raises_promotion_error(self):
        with self.assertRaises(tp.PromotionError):
            tp.promote_verified_candidate("b", "admin1", "Demo@123", repo_url=str(self.origin))

    @mock.patch("triage_promotion.te._request")
    def test_wrong_admin_password_raises_promotion_error_before_any_git_operation(self, mock_request):
        import triage_execution as te
        mock_request.side_effect = te.TriageExecutionError("POST /auth/login -> HTTP 401: invalid username or password")
        self._record_valid_candidate()

        with self.assertRaises(tp.PromotionError):
            tp.promote_verified_candidate("b", "admin1", "wrong-password", repo_url=str(self.origin))

        # No branch was ever created on the real origin -- the failure
        # happened before any git operation, not silently after one.
        branches = _git(["branch", "-a"], self.origin)
        self.assertNotIn("demo/triage-b-promotion", branches)

    @mock.patch("triage_promotion.demo_execution.wait_for_new_deployment")
    @mock.patch("triage_promotion.demo_execution.trigger_deploy")
    def test_stale_baseline_raises_approval_invalidated_without_writing_or_committing(self, mock_deploy, mock_wait):
        self._record_valid_candidate()
        # Simulate master having moved since verification: the real file
        # in the origin no longer matches the baseline the candidate was
        # generated against (e.g. because the defect was independently
        # fixed already -- the real Scenario A situation).
        full_path = self.origin / "app" / "src" / "main" / "java" / self.TARGET_REL
        full_path.write_text("public class TriageScenarioBService { /* SOMETHING ELSE ENTIRELY */ }\n", encoding="utf-8")
        _git(["add", "-A"], self.origin)
        _git(["commit", "-q", "-m", "master moved on"], self.origin)

        with mock.patch("triage_promotion.te._request", side_effect=self._admin_login_side_effect):
            with self.assertRaisesRegex(tp.PromotionError, "APPROVAL_INVALIDATED"):
                tp.promote_verified_candidate("b", "admin1", "Demo@123", repo_url=str(self.origin))

        mock_deploy.assert_not_called()
        branches = _git(["branch", "-a"], self.origin)
        self.assertNotIn("demo/triage-b-promotion", branches)

    @mock.patch("triage_promotion.demo_execution.wait_for_new_deployment")
    @mock.patch("triage_promotion.demo_execution.trigger_deploy")
    def test_deploy_trigger_failure_raises_promotion_error_after_a_real_commit(self, mock_deploy, mock_wait):
        mock_deploy.return_value = (False, "railway up: simulated failure")
        self._record_valid_candidate()

        with mock.patch("triage_promotion.te._request", side_effect=self._admin_login_side_effect):
            with self.assertRaises(tp.PromotionError):
                tp.promote_verified_candidate("b", "admin1", "Demo@123", repo_url=str(self.origin))

        mock_wait.assert_not_called()

    @mock.patch("triage_promotion.demo_execution.wait_for_new_deployment")
    @mock.patch("triage_promotion.demo_execution.trigger_deploy")
    def test_full_promotion_genuinely_commits_and_pushes_the_exact_candidate_to_a_dedicated_branch(self, mock_deploy, mock_wait):
        import demo_execution as de

        mock_deploy.return_value = (True, "deploy triggered")
        mock_wait.return_value = ("real-deployment-id-123", "SUCCESS", 42)
        self._record_valid_candidate()

        fake_rerun = {"fixApplied": True, "attemptCount": 1, "expectedAttemptCount": 1,
                      "exceptionType": None, "exceptionMessage": None, "defectReproduced": False}

        # push_change() intentionally hardcodes the real public GitHub
        # URL as its destination (see demo_execution.py's own docstring:
        # "the destination repository/branch is a hardcoded server-side
        # constant, never derived from public input") -- a real test
        # cannot redirect that, by design. Redirect ONLY the destination
        # here, to this test's own local disposable origin, while still
        # exercising demo_execution's REAL push_to_remote() git mechanics
        # for real, not a mock of git itself.
        def _push_to_local_origin(workspace, branch):
            return de.push_to_remote(workspace, str(self.origin), branch)

        with mock.patch("triage_promotion.te._request", side_effect=self._admin_login_side_effect), \
             mock.patch("triage_promotion.te.reproduce_scenario_b", return_value=fake_rerun), \
             mock.patch("triage_promotion.demo_execution.push_change", side_effect=_push_to_local_origin):
            result = tp.promote_verified_candidate("b", "admin1", "Demo@123", repo_url=str(self.origin))

        self.assertTrue(result["promoted"])
        self.assertTrue(result["deployment_identity_confirmed"])
        self.assertTrue(result["resolved"])
        self.assertEqual(result["rerun_result"], fake_rerun)

        # Independent verification: inspect the real ORIGIN repository
        # directly for the real branch and the real committed content --
        # not just trusting the function's own return value.
        self.assertTrue(result["branch"].startswith("demo/triage-b-promotion-"))
        origin_branches = _git(["branch", "--list", result["branch"]], self.origin)
        self.assertIn(result["branch"], origin_branches)
        committed_content = _git(["show", f"{result['branch']}:app/src/main/java/{self.TARGET_REL}"], self.origin)
        self.assertEqual(committed_content, self.candidate_source)

        # A successful promotion invalidates the verified-candidate entry
        # -- the exact same candidate can never be promoted a second time.
        self.assertIsNone(tp.get_verified_candidate_summary("b"))
        with self.assertRaises(tp.PromotionError):
            tp.promote_verified_candidate("b", "admin1", "Demo@123", repo_url=str(self.origin))

    @mock.patch("triage_promotion.demo_execution.wait_for_new_deployment")
    @mock.patch("triage_promotion.demo_execution.trigger_deploy")
    def test_deployment_not_confirmed_never_reruns_reproduction_or_claims_resolved(self, mock_deploy, mock_wait):
        mock_deploy.return_value = (True, "deploy triggered")
        mock_wait.return_value = (None, "TIMEOUT", 900)
        self._record_valid_candidate()

        with mock.patch("triage_promotion.te._request", side_effect=self._admin_login_side_effect), \
             mock.patch("triage_promotion.te.reproduce_scenario_b") as mock_rerun:
            result = tp.promote_verified_candidate("b", "admin1", "Demo@123", repo_url=str(self.origin))

        mock_rerun.assert_not_called()
        self.assertFalse(result["deployment_identity_confirmed"])
        self.assertFalse(result["resolved"])
        self.assertIsNone(result["rerun_result"])


class VerifiedCandidateSummaryTestCase(unittest.TestCase):
    def setUp(self):
        tp._LAST_VERIFIED_CANDIDATE.clear()
        self.addCleanup(tp._LAST_VERIFIED_CANDIDATE.clear)

    def test_no_candidate_returns_none(self):
        self.assertIsNone(tp.get_verified_candidate_summary("a"))

    def test_recorded_candidate_summary_never_exposes_full_source(self):
        tp.record_verified_candidate("a", "some/Path.java", "baseline text", "candidate text", "diff text")
        summary = tp.get_verified_candidate_summary("a")
        self.assertTrue(summary["available"])
        self.assertNotIn("candidate text", str(summary))
        self.assertNotIn("baseline text", str(summary))
        self.assertEqual(len(summary["candidate_hash"]), 16)


if __name__ == "__main__":
    unittest.main()
