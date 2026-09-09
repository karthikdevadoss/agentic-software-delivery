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


class BuildToolsTestCase(unittest.TestCase):
    def setUp(self):
        metrics.reset()

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

    def test_output_is_size_bounded(self):
        huge = "x" * 100_000
        with mock.patch("subprocess.run") as mocked_run:
            mocked_run.return_value = mock.Mock(returncode=0, stdout=huge, stderr="")
            result = bt.run_maven("compile")
        self.assertLessEqual(len(result["output"]), bt.MAX_OUTPUT_CHARS + 20)
        self.assertIn("truncated", result["output"])


if __name__ == "__main__":
    unittest.main()
