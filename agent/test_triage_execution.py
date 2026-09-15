import json
import unittest
from unittest.mock import patch, MagicMock

import triage_execution as te

_VALID_PREFLIGHT = {
    "status": "ENVIRONMENT_VALID", "expected_java_major_minimum": 21,
    "detected_java_major": 24, "raw_java_version_output": "openjdk 24", "duration_ms": 1.0,
}


def _fake_http_response(payload: dict):
    body = json.dumps(payload).encode("utf-8")
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = body
    cm.__exit__.return_value = False
    return cm


class RequestHelperTestCase(unittest.TestCase):
    @patch("triage_execution.urllib.request.urlopen")
    def test_reset_scenario_calls_the_real_endpoint_and_parses_json(self, mock_urlopen):
        mock_urlopen.return_value = _fake_http_response({"triageCustomerId": 41, "fixApplied": False})
        result = te.reset_scenario()
        self.assertEqual(result, {"triageCustomerId": 41, "fixApplied": False})
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.full_url, te.CUSTOMER_APP_BASE + "/internal/triage/scenario-a/reset")
        self.assertEqual(request.get_method(), "POST")

    @patch("triage_execution.urllib.request.urlopen")
    def test_reproduce_scenario_returns_real_evidence_shape(self, mock_urlopen):
        payload = {"triageCustomerId": 1, "fixApplied": False, "plans": [{"id": 1}, {"id": 2}],
                   "defectReproduced": True, "activePlanCount": 1}
        mock_urlopen.return_value = _fake_http_response(payload)
        self.assertEqual(te.reproduce_scenario(), payload)

    @patch("triage_execution.urllib.request.urlopen")
    def test_get_state_uses_get_method(self, mock_urlopen):
        mock_urlopen.return_value = _fake_http_response({"triageCustomerId": None, "fixApplied": False})
        te.get_state()
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.get_method(), "GET")

    @patch("triage_execution.urllib.request.urlopen")
    def test_http_error_raises_triage_execution_error_not_a_raw_traceback(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="x", code=500, msg="boom", hdrs=None, fp=MagicMock(read=lambda: b"server error"))
        with self.assertRaises(te.TriageExecutionError):
            te.reset_scenario()


class ApproveScenarioTestCase(unittest.TestCase):
    @patch("triage_execution._request")
    def test_approve_scenario_logs_in_then_calls_approve_with_the_real_token(self, mock_request):
        mock_request.side_effect = [
            {"accessToken": "real-admin-jwt", "role": "ADMIN"},
            {"triageCustomerId": 1, "fixApplied": True},
        ]
        result = te.approve_scenario("admin1", "Demo@123")
        self.assertEqual(result, {"triageCustomerId": 1, "fixApplied": True})
        login_call, approve_call = mock_request.call_args_list
        self.assertEqual(login_call.args[:2], ("POST", "/auth/login"))
        self.assertEqual(approve_call.args[:2], ("POST", "/internal/triage/scenario-a/approve"))
        self.assertEqual(approve_call.kwargs.get("token") or approve_call.args[2:], "real-admin-jwt")

    @patch("triage_execution._request")
    def test_approve_scenario_wrong_password_raises_approval_auth_error_not_a_generic_one(self, mock_request):
        mock_request.side_effect = te.TriageExecutionError("POST /auth/login -> HTTP 401: invalid username or password")
        with self.assertRaises(te.ApprovalAuthError):
            te.approve_scenario("admin1", "wrong-password")

    @patch("triage_execution._request")
    def test_approve_scenario_non_admin_login_is_rejected_at_the_approve_step(self, mock_request):
        # A real login can succeed (e.g. a USER persona token) but the
        # approve call itself must still be rejected server-side -- the
        # security boundary lives in SecurityConfig, not client trust.
        mock_request.side_effect = [
            {"accessToken": "real-user-jwt", "role": "USER"},
            te.TriageExecutionError("POST /internal/triage/scenario-a/approve -> HTTP 403: insufficient scope"),
        ]
        with self.assertRaises(te.ApprovalAuthError):
            te.approve_scenario("user1", "Demo@123")


class DiagnoseTestCase(unittest.TestCase):
    def test_diagnose_without_api_key_is_honest_not_fabricated(self):
        with patch.dict("os.environ", {}, clear=True):
            result = te.diagnose({"defectReproduced": True}, api_key=None, create_fn=None)
        self.assertFalse(result["model_called"])
        self.assertIsNone(result["hypothesis"])
        self.assertIn("ANTHROPIC_API_KEY", result["explanation"])

    def test_diagnose_with_injected_create_fn_parses_real_response_shape(self):
        fake_block = MagicMock()
        fake_block.type = "text"
        fake_block.text = json.dumps({
            "hypothesis": "No idempotency check on repeated identical enrollment",
            "root_cause": "enroll() unconditionally cancels and recreates on every call",
            "affected_component": "ContractPlanService.enroll",
            "confidence": "HIGH",
        })
        fake_response = MagicMock()
        fake_response.content = [fake_block]
        fake_response.usage = None
        create_fn = MagicMock(return_value=fake_response)

        result = te.diagnose({"defectReproduced": True}, create_fn=create_fn)

        self.assertTrue(result["model_called"])
        self.assertEqual(result["confidence"], "HIGH")
        self.assertIn("idempotency", result["hypothesis"].lower())
        create_fn.assert_called_once()
        self.assertEqual(create_fn.call_args.kwargs["model"], "claude-sonnet-5")

    def test_diagnose_handles_a_markdown_fenced_response(self):
        fake_block = MagicMock()
        fake_block.type = "text"
        fake_block.text = "```json\n" + json.dumps({"hypothesis": "h", "root_cause": "r", "affected_component": "c", "confidence": "MEDIUM"}) + "\n```"
        fake_response = MagicMock()
        fake_response.content = [fake_block]
        fake_response.usage = None
        create_fn = MagicMock(return_value=fake_response)

        result = te.diagnose({}, create_fn=create_fn)
        self.assertEqual(result["confidence"], "MEDIUM")

    def test_diagnose_handles_non_json_response_honestly(self):
        fake_block = MagicMock()
        fake_block.type = "text"
        fake_block.text = "I'm not sure, let me think about this differently."
        fake_response = MagicMock()
        fake_response.content = [fake_block]
        fake_response.usage = None
        create_fn = MagicMock(return_value=fake_response)

        result = te.diagnose({}, create_fn=create_fn)
        self.assertTrue(result["model_called"])
        self.assertIsNone(result["hypothesis"])
        self.assertIn("did not return valid JSON", result["explanation"])


class PatchDiffTestCase(unittest.TestCase):
    def test_get_patch_diff_returns_the_real_historical_commit_diff(self):
        result = te.get_patch_diff()
        self.assertTrue(result["available"], result)
        self.assertEqual(result["commit"], te.FIX_COMMIT)
        self.assertIn("isSameTerms", result["diff"])

    @patch("triage_execution.subprocess.run")
    def test_get_patch_diff_falls_back_to_the_embedded_diff_when_git_history_is_unavailable(self, mock_run):
        # Reproduces the real deployed-container condition found live this
        # session: `railway up` doesn't upload .git, so the container's
        # own freshly-initialized git repo genuinely has no such commit.
        mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="fatal: bad revision '2155a8a'\n")
        result = te.get_patch_diff()
        self.assertTrue(result["available"])
        self.assertEqual(result["source"], "embedded_fallback")
        self.assertIn("isSameTerms", result["diff"])

    @patch("triage_execution.subprocess.run")
    def test_get_patch_diff_prefers_real_git_when_available(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="real git diff content", stderr="")
        result = te.get_patch_diff()
        self.assertEqual(result["source"], "git")
        self.assertEqual(result["diff"], "real git diff content")


class VerifyFixTestCase(unittest.TestCase):
    @patch("triage_execution.environment_preflight.check_java_toolchain", return_value=_VALID_PREFLIGHT)
    @patch("triage_execution.subprocess.run")
    def test_verify_fix_runs_the_exact_two_scoped_test_classes(self, mock_run, mock_preflight):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = te.verify_fix()
        self.assertTrue(result["success"])
        argv = mock_run.call_args.args[0]
        self.assertIn("-Dtest=ContractPlanServiceTest,TriageScenarioAIntegrationTest", argv)
        self.assertFalse(mock_run.call_args.kwargs.get("shell", False))

    @patch("triage_execution.environment_preflight.check_java_toolchain", return_value=_VALID_PREFLIGHT)
    @patch("triage_execution.subprocess.run")
    def test_verify_fix_reports_failure_honestly_on_nonzero_exit(self, mock_run, mock_preflight):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="1 test failed")
        result = te.verify_fix()
        self.assertFalse(result["success"])
        self.assertIn("failed", result["output_tail"])

    @patch("triage_execution.environment_preflight.check_java_toolchain")
    @patch("triage_execution.subprocess.run")
    def test_verify_fix_fails_closed_on_wrong_jdk_without_ever_running_maven(self, mock_run, mock_preflight):
        """The exact real AEQ-021 class of bug -- verify_fix() must
        refuse to even attempt mvnw test when the JDK is too old, and
        must report ENVIRONMENT_INVALID rather than a generic FAILED
        that would look like a real test defect."""
        mock_preflight.return_value = {
            "status": "ENVIRONMENT_INVALID", "expected_java_major_minimum": 21,
            "detected_java_major": 17, "raw_java_version_output": "openjdk 17", "duration_ms": 1.0,
        }
        result = te.verify_fix()
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "ENVIRONMENT_INVALID")
        mock_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
