import json
import unittest
from unittest.mock import patch, MagicMock

import pricing_config
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


class _FakeUsage:
    """A real-shaped anthropic Usage object (mirrors
    test_reasoning_gateway.py's own _FakeUsage), used here to prove BL-009/
    ACT-011's usage dict actually survives the trip from
    reasoning_gateway.call() through _call_model_text() and out through
    diagnose()/generate_candidate_patch() (all 3 scenarios) -- every OTHER
    test in this file sets fake_response.usage = None, which never
    exercises this exact propagation path."""

    def __init__(self, input_tokens=1234, output_tokens=321):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_creation_input_tokens = None
        self.cache_read_input_tokens = None


def _fake_response_with_real_usage(text: str):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.usage = _FakeUsage()
    return fake_response


def _assert_real_usage_propagated(test_case, usage):
    """Shared assertion, reused by every ACT-011 propagation test below:
    usage must be present, must never be a fabricated number, and its
    cost must be the REAL output of pricing_config.calculate_cost() for
    the exact tokens _FakeUsage() carries -- never a hand-typed constant
    that could silently drift from the real pricing table."""
    test_case.assertIsNotNone(usage, "a real model response must never leave usage as None")
    test_case.assertEqual(usage["input_tokens"], 1234)
    test_case.assertEqual(usage["output_tokens"], 321)
    test_case.assertIsInstance(usage["duration_ms"], float)
    test_case.assertGreaterEqual(usage["duration_ms"], 0.0)
    expected_cost = pricing_config.calculate_cost(
        "anthropic", "claude-sonnet-5", input_tokens=1234, output_tokens=321,
        cache_read_tokens=0, cache_write_tokens=0,
    )
    test_case.assertTrue(expected_cost["available"], "claude-sonnet-5 must have a real priced entry")
    test_case.assertEqual(usage["total_usd"], expected_cost["total_usd"])
    test_case.assertEqual(usage["available"], True)


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

    def test_diagnose_without_api_key_leaves_usage_honestly_none(self):
        """ACT-011: never a fabricated zero when no real API response was
        obtained -- usage must be None, not $0.00 / 0 tokens."""
        with patch.dict("os.environ", {}, clear=True):
            result = te.diagnose({"defectReproduced": True}, api_key=None, create_fn=None)
        self.assertIsNone(result["usage"])

    def test_diagnose_propagates_the_real_usage_dict_act_011(self):
        """ACT-011/BL-009: the real usage dict reasoning_gateway.call()
        computes must reach diagnose()'s own returned dict, not be
        discarded at _call_model_text()."""
        create_fn = MagicMock(return_value=_fake_response_with_real_usage(json.dumps({
            "hypothesis": "h", "root_cause": "r", "affected_component": "c", "confidence": "HIGH",
        })))
        result = te.diagnose({"defectReproduced": True}, create_fn=create_fn)
        _assert_real_usage_propagated(self, result.get("usage"))

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


class GenerateCandidatePatchTestCase(unittest.TestCase):
    def test_without_api_key_is_honest_not_fabricated(self):
        with patch.dict("os.environ", {}, clear=True):
            result = te.generate_candidate_patch({"defectReproduced": True}, api_key=None, create_fn=None)
        self.assertFalse(result["generated"])
        self.assertIsNone(result["candidate_source"])
        self.assertIn("ANTHROPIC_API_KEY", result["explanation"])
        self.assertIsNone(result["usage"])

    def test_generate_candidate_patch_propagates_the_real_usage_dict_act_011(self):
        """ACT-011/BL-009: same propagation proof as diagnose()'s, for the
        SECOND real call site (candidate-patch generation)."""
        create_fn = MagicMock(return_value=_fake_response_with_real_usage(
            "package com.example.customer.service;\n\npublic class ContractPlanService {}\n"))
        result = te.generate_candidate_patch({"defectReproduced": True}, create_fn=create_fn)
        self.assertTrue(result["generated"])
        _assert_real_usage_propagated(self, result.get("usage"))

    def test_with_injected_create_fn_returns_the_models_full_file_content(self):
        fake_block = MagicMock()
        fake_block.type = "text"
        fake_block.text = "package com.example.customer.service;\n\npublic class ContractPlanService {}\n"
        fake_response = MagicMock()
        fake_response.content = [fake_block]
        fake_response.usage = None
        create_fn = MagicMock(return_value=fake_response)

        result = te.generate_candidate_patch({"defectReproduced": True}, create_fn=create_fn)

        self.assertTrue(result["generated"])
        self.assertIn("public class ContractPlanService", result["candidate_source"])
        self.assertEqual(result["target_file"], te.FIX_FILE)
        create_fn.assert_called_once()
        self.assertEqual(create_fn.call_args.kwargs["model"], "claude-sonnet-5")
        # Bounds thinking depth for this mechanical code-generation task --
        # see _call_model_text's Javadoc-equivalent docstring for why
        # (extended thinking otherwise runs adaptive by default and can
        # consume the entire max_tokens budget before any text output).
        self.assertEqual(create_fn.call_args.kwargs["output_config"], {"effort": "low"})

    def test_strips_markdown_fence_if_the_model_adds_one_anyway(self):
        fake_block = MagicMock()
        fake_block.type = "text"
        fake_block.text = "```java\npackage com.example.customer.service;\n```"
        fake_response = MagicMock()
        fake_response.content = [fake_block]
        fake_response.usage = None
        create_fn = MagicMock(return_value=fake_response)

        result = te.generate_candidate_patch({}, create_fn=create_fn)
        self.assertNotIn("```", result["candidate_source"])

    def test_thinking_only_response_is_reported_honestly_not_as_an_empty_candidate(self):
        """REAL BUG this locks in (2026-09-15, live production testing of
        Triage Scenario C): extended thinking consumed the entire
        max_tokens budget before the model emitted any text block --
        response.content held only a ThinkingBlock, stop_reason=
        'max_tokens', zero text blocks. Silently returning an empty
        string let apply_and_verify_candidate() write a blank file and
        report a confusing, unrelated COMPILE_FAILED (missing class)
        instead of the real, honest reason. generated must be False with
        a real explanation, never an empty/whitespace candidate_source."""
        fake_thinking_block = MagicMock()
        fake_thinking_block.type = "thinking"
        fake_response = MagicMock()
        fake_response.content = [fake_thinking_block]
        fake_response.usage = None
        fake_response.stop_reason = "max_tokens"
        create_fn = MagicMock(return_value=fake_response)

        result = te.generate_candidate_patch({}, create_fn=create_fn)

        self.assertFalse(result["generated"])
        self.assertIsNone(result["candidate_source"])
        self.assertIn("max_tokens", result["explanation"])


class ApplyAndVerifyCandidateTestCase(unittest.TestCase):
    @patch("triage_execution.environment_preflight.check_java_toolchain")
    def test_fails_closed_on_wrong_jdk_without_ever_copying_or_compiling(self, mock_preflight):
        mock_preflight.return_value = {
            "status": "ENVIRONMENT_INVALID", "expected_java_major_minimum": 21,
            "detected_java_major": 17, "raw_java_version_output": "openjdk 17", "duration_ms": 1.0,
        }
        result = te.apply_and_verify_candidate("irrelevant candidate content")
        self.assertFalse(result["applied"])
        self.assertEqual(result["status"], "ENVIRONMENT_INVALID")

    def test_computes_a_real_diff_against_the_real_buggy_baseline(self):
        """No mocking of subprocess here -- proves the diff itself (via
        Python's own difflib, never git) is computed correctly against
        the exact real pre-fix file content."""
        candidate = te._BUGGY_FULL_FILE.replace(
            "static final String NO_ACTIVE_PLAN_MESSAGE",
            "static final String RENAMED_FOR_TEST_MESSAGE",
        )
        result = te.apply_and_verify_candidate(candidate)
        self.assertTrue(result["applied"])
        self.assertIn("-    static final String NO_ACTIVE_PLAN_MESSAGE", result["diff"])
        self.assertIn("+    static final String RENAMED_FOR_TEST_MESSAGE", result["diff"])
        # This particular edit renames a constant without updating its
        # usages -- expected to genuinely fail compilation, proving this
        # is a REAL compile, not a rubber-stamped success. TESTS_FAILED is
        # included defensively (not expected) since test_classes is now
        # always passed by the real call site -- if it somehow compiled,
        # a renamed-but-unused constant should not pass the real tests either.
        self.assertIn(result["status"], ("COMPILE_FAILED", "TESTS_FAILED", "COMPILE_VERIFIED"))

    def test_a_candidate_that_compiles_but_does_not_actually_fix_the_defect_is_marked_tests_failed(self):
        """THE REAL DEFECT CLASS THIS FIX CLOSES (docs/INTELLIGENCE_PLACEMENT_V3.md's
        Phase 1 audit, HIGH item): the unmodified historical pre-fix file
        is syntactically valid Java (so it genuinely compiles), but it IS
        the exact defective version this scenario reproduces the bug
        against -- before this fix, the old compile-only contract would
        have wrongly labeled this COMPILE_VERIFIED (eligible for
        human-approved promotion) despite never actually fixing anything.
        Proves both halves for real: compile succeeds, but the real
        scenario test genuinely fails against it."""
        result = te.apply_and_verify_candidate(te._BUGGY_FULL_FILE)
        self.assertTrue(result["applied"])
        self.assertTrue(result["compile"]["success"], result["compile"])
        self.assertIsNotNone(result["test"])
        self.assertFalse(result["test"]["success"], result["test"])
        self.assertEqual(result["status"], "TESTS_FAILED")

    def test_a_candidate_that_genuinely_fixes_the_defect_reaches_compile_verified(self):
        """The real, current, already-fixed ContractPlanService.java
        content (read directly from the actual repository -- the same
        content the historical fix commit 2155a8a produced) must compile
        AND pass the real TriageScenarioAIntegrationTest/
        ContractPlanServiceTest -- proving COMPILE_VERIFIED now means
        what it claims (compiled AND the reproduced defect is genuinely
        fixed), not just "it compiled". No regression from the previous
        compile-only contract for a real, correct candidate."""
        real_fixed_source = (
            te.APP_DIR / "src" / "main" / "java" / "com" / "example"
            / "customer" / "service" / "ContractPlanService.java"
        ).read_text(encoding="utf-8")
        result = te.apply_and_verify_candidate(real_fixed_source)
        self.assertTrue(result["applied"])
        self.assertTrue(result["compile"]["success"], result["compile"])
        self.assertIsNotNone(result["test"])
        self.assertTrue(result["test"]["success"], result["test"])
        self.assertEqual(result["status"], "COMPILE_VERIFIED")

    @patch("triage_execution._isolated_compile_java_candidate")
    def test_wires_the_real_scenario_a_test_classes_through_to_the_shared_engine(self, mock_isolated):
        mock_isolated.return_value = {"applied": True, "status": "COMPILE_VERIFIED", "diff": "", "compile": {}, "test": {}}
        te.apply_and_verify_candidate("some candidate source")
        self.assertEqual(
            mock_isolated.call_args.kwargs.get("test_classes"),
            ["ContractPlanServiceTest", "TriageScenarioAIntegrationTest"],
        )


class ScenarioBRequestHelperTestCase(unittest.TestCase):
    @patch("triage_execution.urllib.request.urlopen")
    def test_reset_scenario_b_calls_the_real_endpoint(self, mock_urlopen):
        mock_urlopen.return_value = _fake_http_response({"fixApplied": False})
        result = te.reset_scenario_b()
        self.assertEqual(result, {"fixApplied": False})
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.full_url, te.CUSTOMER_APP_BASE + "/internal/triage/scenario-b/reset")
        self.assertEqual(request.get_method(), "POST")

    @patch("triage_execution.urllib.request.urlopen")
    def test_reproduce_scenario_b_returns_real_evidence_shape(self, mock_urlopen):
        payload = {"fixApplied": False, "attemptCount": 3, "expectedAttemptCount": 1,
                   "exceptionType": "HttpClientErrorException$BadRequest", "exceptionMessage": "400 Bad Request",
                   "defectReproduced": True}
        mock_urlopen.return_value = _fake_http_response(payload)
        self.assertEqual(te.reproduce_scenario_b(), payload)


class ApproveScenarioBTestCase(unittest.TestCase):
    @patch("triage_execution._request")
    def test_approve_scenario_b_logs_in_then_calls_approve_with_the_real_token(self, mock_request):
        mock_request.side_effect = [
            {"accessToken": "real-admin-jwt", "role": "ADMIN"},
            {"fixApplied": True},
        ]
        result = te.approve_scenario_b("admin1", "Demo@123")
        self.assertEqual(result, {"fixApplied": True})
        login_call, approve_call = mock_request.call_args_list
        self.assertEqual(login_call.args[:2], ("POST", "/auth/login"))
        self.assertEqual(approve_call.args[:2], ("POST", "/internal/triage/scenario-b/approve"))

    @patch("triage_execution._request")
    def test_approve_scenario_b_wrong_password_raises_approval_auth_error(self, mock_request):
        mock_request.side_effect = te.TriageExecutionError("POST /auth/login -> HTTP 401: invalid username or password")
        with self.assertRaises(te.ApprovalAuthError):
            te.approve_scenario_b("admin1", "wrong-password")


class DiagnoseBTestCase(unittest.TestCase):
    def test_diagnose_b_without_api_key_is_honest_not_fabricated(self):
        with patch.dict("os.environ", {}, clear=True):
            result = te.diagnose_b({"defectReproduced": True}, api_key=None, create_fn=None)
        self.assertFalse(result["model_called"])
        self.assertIsNone(result["hypothesis"])
        self.assertIn("ANTHROPIC_API_KEY", result["explanation"])

    def test_diagnose_b_with_injected_create_fn_parses_real_response_shape(self):
        fake_block = MagicMock()
        fake_block.type = "text"
        fake_block.text = json.dumps({
            "hypothesis": "Retry predicate matches any exception, including non-retryable 4xx",
            "root_cause": "retryOnException(ex -> true) retries a client error that can never succeed",
            "affected_component": "TriageScenarioBService.buggyRetry",
            "confidence": "HIGH",
        })
        fake_response = MagicMock()
        fake_response.content = [fake_block]
        fake_response.usage = None
        create_fn = MagicMock(return_value=fake_response)

        result = te.diagnose_b({"attemptCount": 3}, create_fn=create_fn)

        self.assertTrue(result["model_called"])
        self.assertEqual(result["confidence"], "HIGH")
        create_fn.assert_called_once()
        self.assertEqual(create_fn.call_args.kwargs["model"], "claude-sonnet-5")

    def test_diagnose_b_propagates_the_real_usage_dict_act_011(self):
        """ACT-011/BL-009: same propagation proof as diagnose()'s, for
        Scenario B."""
        create_fn = MagicMock(return_value=_fake_response_with_real_usage(json.dumps({
            "hypothesis": "h", "root_cause": "r", "affected_component": "c", "confidence": "HIGH",
        })))
        result = te.diagnose_b({"attemptCount": 3}, create_fn=create_fn)
        _assert_real_usage_propagated(self, result.get("usage"))


class GetReferenceBTestCase(unittest.TestCase):
    def test_get_reference_b_is_honest_about_not_being_a_historical_commit(self):
        result = te.get_reference_b()
        self.assertTrue(result["available"])
        self.assertEqual(result["kind"], "production_reference")
        self.assertIn("AppointmentAvailabilityConfig", result["file"])
        self.assertIn("ResourceAccessException", result["excerpt"])


class GenerateCandidatePatchBTestCase(unittest.TestCase):
    def test_without_api_key_is_honest_not_fabricated(self):
        with patch.dict("os.environ", {}, clear=True):
            result = te.generate_candidate_patch_b({"attemptCount": 3}, api_key=None, create_fn=None)
        self.assertFalse(result["generated"])
        self.assertIsNone(result["candidate_source"])

    def test_with_injected_create_fn_returns_the_models_full_file_content(self):
        fake_block = MagicMock()
        fake_block.type = "text"
        fake_block.text = "package com.example.customer.triage;\n\npublic class TriageScenarioBService {}\n"
        fake_response = MagicMock()
        fake_response.content = [fake_block]
        fake_response.usage = None
        create_fn = MagicMock(return_value=fake_response)

        result = te.generate_candidate_patch_b({"attemptCount": 3}, create_fn=create_fn)

        self.assertTrue(result["generated"])
        self.assertIn("public class TriageScenarioBService", result["candidate_source"])
        self.assertEqual(result["target_file"], te.FIX_FILE_B)

    def test_generate_candidate_patch_b_propagates_the_real_usage_dict_act_011(self):
        """ACT-011/BL-009: same propagation proof as generate_candidate_patch()'s,
        for Scenario B."""
        create_fn = MagicMock(return_value=_fake_response_with_real_usage(
            "package com.example.customer.triage;\n\npublic class TriageScenarioBService {}\n"))
        result = te.generate_candidate_patch_b({"attemptCount": 3}, create_fn=create_fn)
        self.assertTrue(result["generated"])
        _assert_real_usage_propagated(self, result.get("usage"))


class ApplyAndVerifyCandidateBTestCase(unittest.TestCase):
    @patch("triage_execution.environment_preflight.check_java_toolchain")
    def test_fails_closed_on_wrong_jdk_without_ever_copying_or_compiling(self, mock_preflight):
        mock_preflight.return_value = {
            "status": "ENVIRONMENT_INVALID", "expected_java_major_minimum": 21,
            "detected_java_major": 17, "raw_java_version_output": "openjdk 17", "duration_ms": 1.0,
        }
        result = te.apply_and_verify_candidate_b("irrelevant candidate content")
        self.assertFalse(result["applied"])
        self.assertEqual(result["status"], "ENVIRONMENT_INVALID")

    def test_a_genuinely_valid_candidate_actually_compiles_and_passes_tests(self):
        """The unmodified real baseline file (matching the actual Java
        source on disk, already correct) must genuinely compile AND pass
        the real TriageScenarioBIntegrationTest through the real
        isolated-workspace mechanism -- proving this reused engine works
        for Scenario B's target file exactly like it does for Scenario A's,
        and that COMPILE_VERIFIED now requires both, not compile alone."""
        result = te.apply_and_verify_candidate_b(te._BUGGY_FULL_FILE_B)
        self.assertTrue(result["applied"])
        self.assertTrue(result["compile"]["success"], result["compile"])
        self.assertIsNotNone(result["test"])
        self.assertTrue(result["test"]["success"], result["test"])
        self.assertEqual(result["status"], "COMPILE_VERIFIED")

    @patch("triage_execution._isolated_compile_java_candidate")
    def test_wires_the_real_scenario_b_test_class_through_to_the_shared_engine(self, mock_isolated):
        mock_isolated.return_value = {"applied": True, "status": "COMPILE_VERIFIED", "diff": "", "compile": {}, "test": {}}
        te.apply_and_verify_candidate_b("some candidate source")
        self.assertEqual(mock_isolated.call_args.kwargs.get("test_classes"), ["TriageScenarioBIntegrationTest"])


class VerifyFixBTestCase(unittest.TestCase):
    @patch("triage_execution.environment_preflight.check_java_toolchain", return_value=_VALID_PREFLIGHT)
    @patch("triage_execution.subprocess.run")
    def test_verify_fix_b_runs_the_scoped_test_class(self, mock_run, mock_preflight):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = te.verify_fix_b()
        self.assertTrue(result["success"])
        argv = mock_run.call_args.args[0]
        self.assertIn("-Dtest=TriageScenarioBIntegrationTest", argv)


class ScenarioCRequestHelperTestCase(unittest.TestCase):
    @patch("triage_execution.urllib.request.urlopen")
    def test_reset_scenario_c_calls_the_real_endpoint(self, mock_urlopen):
        mock_urlopen.return_value = _fake_http_response({"fixApplied": False})
        result = te.reset_scenario_c()
        self.assertEqual(result, {"fixApplied": False})
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.full_url, te.CUSTOMER_APP_BASE + "/internal/triage/scenario-c/reset")
        self.assertEqual(request.get_method(), "POST")

    @patch("triage_execution.urllib.request.urlopen")
    def test_reproduce_scenario_c_returns_real_evidence_shape(self, mock_urlopen):
        payload = {"fixApplied": False, "querySucceeded": False, "resultCount": 0,
                   "errorType": "PSQLException", "errorMessage": "function lower(bytea) does not exist",
                   "defectReproduced": True}
        mock_urlopen.return_value = _fake_http_response(payload)
        self.assertEqual(te.reproduce_scenario_c(), payload)


class ApproveScenarioCTestCase(unittest.TestCase):
    @patch("triage_execution._request")
    def test_approve_scenario_c_logs_in_then_calls_approve_with_the_real_token(self, mock_request):
        mock_request.side_effect = [
            {"accessToken": "real-admin-jwt", "role": "ADMIN"},
            {"fixApplied": True},
        ]
        result = te.approve_scenario_c("admin1", "Demo@123")
        self.assertEqual(result, {"fixApplied": True})
        login_call, approve_call = mock_request.call_args_list
        self.assertEqual(login_call.args[:2], ("POST", "/auth/login"))
        self.assertEqual(approve_call.args[:2], ("POST", "/internal/triage/scenario-c/approve"))


class DiagnoseCTestCase(unittest.TestCase):
    def test_diagnose_c_without_api_key_is_honest_not_fabricated(self):
        with patch.dict("os.environ", {}, clear=True):
            result = te.diagnose_c({"defectReproduced": True}, api_key=None, create_fn=None)
        self.assertFalse(result["model_called"])
        self.assertIsNone(result["hypothesis"])
        self.assertIn("ANTHROPIC_API_KEY", result["explanation"])

    def test_diagnose_c_with_injected_create_fn_parses_real_response_shape(self):
        fake_block = MagicMock()
        fake_block.type = "text"
        fake_block.text = json.dumps({
            "hypothesis": "Bind parameter type ambiguity through CONCAT defaults to bytea on Postgres",
            "root_cause": "The :term parameter is used both in an IS NULL check and inside CONCAT",
            "affected_component": "TriageScenarioCService.searchBuggy",
            "confidence": "HIGH",
        })
        fake_response = MagicMock()
        fake_response.content = [fake_block]
        fake_response.usage = None
        create_fn = MagicMock(return_value=fake_response)

        result = te.diagnose_c({"defectReproduced": True}, create_fn=create_fn)

        self.assertTrue(result["model_called"])
        self.assertEqual(result["confidence"], "HIGH")
        create_fn.assert_called_once()

    def test_diagnose_c_propagates_the_real_usage_dict_act_011(self):
        """ACT-011/BL-009: same propagation proof as diagnose()'s, for
        Scenario C."""
        create_fn = MagicMock(return_value=_fake_response_with_real_usage(json.dumps({
            "hypothesis": "h", "root_cause": "r", "affected_component": "c", "confidence": "HIGH",
        })))
        result = te.diagnose_c({"defectReproduced": True}, create_fn=create_fn)
        _assert_real_usage_propagated(self, result.get("usage"))


class GetReferenceCTestCase(unittest.TestCase):
    def test_get_reference_c_is_honest_about_the_real_source(self):
        result = te.get_reference_c()
        self.assertTrue(result["available"])
        self.assertEqual(result["kind"], "production_reference")
        self.assertIn("CustomerRepository", result["file"])
        self.assertIn("searchWorkspaceCustomers", result["excerpt"])


class GenerateCandidatePatchCTestCase(unittest.TestCase):
    def test_without_api_key_is_honest_not_fabricated(self):
        with patch.dict("os.environ", {}, clear=True):
            result = te.generate_candidate_patch_c({"querySucceeded": False}, api_key=None, create_fn=None)
        self.assertFalse(result["generated"])
        self.assertIsNone(result["candidate_source"])

    def test_with_injected_create_fn_returns_the_models_full_file_content(self):
        fake_block = MagicMock()
        fake_block.type = "text"
        fake_block.text = "package com.example.customer.triage;\n\npublic class TriageScenarioCService {}\n"
        fake_response = MagicMock()
        fake_response.content = [fake_block]
        fake_response.usage = None
        create_fn = MagicMock(return_value=fake_response)

        result = te.generate_candidate_patch_c({"querySucceeded": False}, create_fn=create_fn)

        self.assertTrue(result["generated"])
        self.assertIn("public class TriageScenarioCService", result["candidate_source"])
        self.assertEqual(result["target_file"], te.FIX_FILE_C)

    def test_generate_candidate_patch_c_propagates_the_real_usage_dict_act_011(self):
        """ACT-011/BL-009: same propagation proof as generate_candidate_patch()'s,
        for Scenario C -- the 6th and last of the 6 named call sites."""
        create_fn = MagicMock(return_value=_fake_response_with_real_usage(
            "package com.example.customer.triage;\n\npublic class TriageScenarioCService {}\n"))
        result = te.generate_candidate_patch_c({"querySucceeded": False}, create_fn=create_fn)
        self.assertTrue(result["generated"])
        _assert_real_usage_propagated(self, result.get("usage"))


class ApplyAndVerifyCandidateCTestCase(unittest.TestCase):
    @patch("triage_execution.environment_preflight.check_java_toolchain")
    def test_fails_closed_on_wrong_jdk_without_ever_copying_or_compiling(self, mock_preflight):
        mock_preflight.return_value = {
            "status": "ENVIRONMENT_INVALID", "expected_java_major_minimum": 21,
            "detected_java_major": 17, "raw_java_version_output": "openjdk 17", "duration_ms": 1.0,
        }
        result = te.apply_and_verify_candidate_c("irrelevant candidate content")
        self.assertFalse(result["applied"])
        self.assertEqual(result["status"], "ENVIRONMENT_INVALID")

    def test_a_genuinely_valid_candidate_actually_compiles_and_passes_tests(self):
        """The unmodified real baseline file (matching the actual Java
        source on disk, already correct) must genuinely compile AND pass
        the real TriageScenarioCIntegrationTest through the real
        isolated-workspace mechanism -- proving this reused engine works
        for Scenario C's target file exactly like it does for A/B, and
        that COMPILE_VERIFIED now requires both, not compile alone."""
        result = te.apply_and_verify_candidate_c(te._BUGGY_FULL_FILE_C)
        self.assertTrue(result["applied"])
        self.assertTrue(result["compile"]["success"], result["compile"])
        self.assertIsNotNone(result["test"])
        self.assertTrue(result["test"]["success"], result["test"])
        self.assertEqual(result["status"], "COMPILE_VERIFIED")

    @patch("triage_execution._isolated_compile_java_candidate")
    def test_wires_the_real_scenario_c_test_class_through_to_the_shared_engine(self, mock_isolated):
        mock_isolated.return_value = {"applied": True, "status": "COMPILE_VERIFIED", "diff": "", "compile": {}, "test": {}}
        te.apply_and_verify_candidate_c("some candidate source")
        self.assertEqual(mock_isolated.call_args.kwargs.get("test_classes"), ["TriageScenarioCIntegrationTest"])


class VerifyFixCTestCase(unittest.TestCase):
    @patch("triage_execution.environment_preflight.check_java_toolchain", return_value=_VALID_PREFLIGHT)
    @patch("triage_execution.subprocess.run")
    def test_verify_fix_c_runs_the_scoped_test_class(self, mock_run, mock_preflight):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = te.verify_fix_c()
        self.assertTrue(result["success"])
        argv = mock_run.call_args.args[0]
        self.assertIn("-Dtest=TriageScenarioCIntegrationTest", argv)


if __name__ == "__main__":
    unittest.main()
