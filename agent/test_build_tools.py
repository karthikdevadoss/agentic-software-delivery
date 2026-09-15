"""
Focused automated tests for the V4 controlled compile/test tool
(agent/build_tools.py). Fast tests here only check the allowlist/rejection
logic with subprocess mocked out. A real Maven invocation is slow (tens of
seconds) and is verified separately, manually, as part of this session's
V4 sign-off — see docs/PROJECT_STATE.json verification_state.

Run: python agent/test_build_tools.py
"""

import unittest
from unittest import mock

import build_tools as bt
import metrics

_VALID_PREFLIGHT = {
    "status": "ENVIRONMENT_VALID", "expected_java_major_minimum": 21,
    "detected_java_major": 24, "raw_java_version_output": "openjdk 24", "duration_ms": 1.0,
}


class BuildToolsTestCase(unittest.TestCase):
    def setUp(self):
        metrics.reset()
        # These tests mock subprocess.run globally to simulate mvnw's own
        # output -- environment_preflight.check_java_toolchain() also
        # calls subprocess.run internally (for `java -version`), so it
        # must be mocked separately here to a passing result, or every
        # test below would see the mvnw-shaped mock output where it
        # expects a real Java version string and fail closed instead of
        # reaching the actual behavior under test.
        patcher = mock.patch("build_tools.environment_preflight.check_java_toolchain", return_value=_VALID_PREFLIGHT)
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_unknown_goal_rejected_without_touching_subprocess(self):
        with mock.patch("subprocess.run") as mocked_run:
            with self.assertRaises(bt.BuildToolError) as ctx:
                bt.run_maven("deploy")
            mocked_run.assert_not_called()
        self.assertIn("not allowed", str(ctx.exception))

    def test_shell_injection_attempt_rejected_as_unknown_goal(self):
        with mock.patch("subprocess.run") as mocked_run:
            with self.assertRaises(bt.BuildToolError):
                bt.run_maven("test; rm -rf /")
            mocked_run.assert_not_called()

    def test_subprocess_never_uses_shell_true(self):
        with mock.patch("subprocess.run") as mocked_run:
            mocked_run.return_value = mock.Mock(returncode=0, stdout="ok", stderr="")
            bt.run_maven("compile")
            _, kwargs = mocked_run.call_args
            self.assertFalse(kwargs.get("shell", False))
            # argv form (a list), never a single interpolated string
            args = mocked_run.call_args[0][0]
            self.assertIsInstance(args, list)

    def test_success_recorded_in_metrics(self):
        with mock.patch("subprocess.run") as mocked_run:
            mocked_run.return_value = mock.Mock(returncode=0, stdout="BUILD SUCCESS", stderr="")
            result = bt.run_maven("compile")
        self.assertTrue(result["success"])
        events = metrics.get_tool_call_events()
        self.assertTrue(any(e["tool"] == "maven_compile" and e["success"] for e in events))

    def test_failure_recorded_in_metrics_not_a_crash(self):
        with mock.patch("subprocess.run") as mocked_run:
            mocked_run.return_value = mock.Mock(returncode=1, stdout="", stderr="COMPILATION ERROR")
            result = bt.run_maven("test")
        self.assertFalse(result["success"])
        events = metrics.get_tool_call_events()
        self.assertTrue(any(e["tool"] == "maven_test" and not e["success"] for e in events))

    def test_fails_closed_on_wrong_jdk_without_ever_running_mvnw(self):
        """The exact real AEQ-021 class of bug: run_maven() must refuse
        to even attempt mvnw when the JDK is too old, and report
        ENVIRONMENT_INVALID rather than a generic failure indistinguishable
        from a real compile/test defect."""
        with mock.patch("build_tools.environment_preflight.check_java_toolchain", return_value={
            "status": "ENVIRONMENT_INVALID", "expected_java_major_minimum": 21,
            "detected_java_major": 17, "raw_java_version_output": "openjdk 17", "duration_ms": 1.0,
        }):
            with mock.patch("subprocess.run") as mocked_run:
                result = bt.run_maven("compile")
                mocked_run.assert_not_called()
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "ENVIRONMENT_INVALID")

    def test_output_is_size_bounded(self):
        huge = "x" * 100_000
        with mock.patch("subprocess.run") as mocked_run:
            mocked_run.return_value = mock.Mock(returncode=0, stdout=huge, stderr="")
            result = bt.run_maven("compile")
        self.assertLessEqual(len(result["output"]), bt.MAX_OUTPUT_CHARS + 20)
        self.assertIn("truncated", result["output"])


if __name__ == "__main__":
    unittest.main()
