"""
Focused automated tests for V4.1 live execution wiring (agent/execution_tools.py).

Does NOT re-prove every write_tools.py/build_tools.py guarantee in depth —
those are already covered by test_write_tools.py/test_build_tools.py. These
tests specifically prove the *live integration*: the model-facing tool
surface, the approval boundary staying outside it, and that dispatch
correctly routes to the already-tested underlying libraries.

Run: python agent/test_execution_tools.py
"""

import shutil
import unittest
from unittest import mock

import tools
import write_tools as wt
import build_tools as bt
import execution_tools as et
import metrics

FIXTURE_DIR = tools.REPO_ROOT / "app" / "src" / "test" / "java" / "com" / "example" / "customer" / "_v41_fixture"
FIXTURE_REL = "app/src/test/java/com/example/customer/_v41_fixture/ExecutionFixture.java"

REAL_CONTROLLER = tools.REPO_ROOT / "app/src/main/java/com/example/customer/controller/CustomerController.java"


def _approve(_edit):
    return True


def _reject(_edit):
    return False


class ExecutionToolsTestCase(unittest.TestCase):
    def setUp(self):
        wt._pending_edits.clear()
        metrics.reset()
        self._orig_prompt = et._approval_prompt_fn
        self._controller_snapshot = REAL_CONTROLLER.read_text(encoding="utf-8")
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        et.set_approval_prompt(self._orig_prompt)
        if FIXTURE_DIR.exists():
            shutil.rmtree(FIXTURE_DIR)
        wt._pending_edits.clear()
        self.assertEqual(REAL_CONTROLLER.read_text(encoding="utf-8"), self._controller_snapshot)

    # --- 1. valid proposal via the live tool surface ---------------------

    def test_propose_via_dispatch_creates_valid_proposal(self):
        et.set_approval_prompt(_approve)
        result, is_error = et.dispatch_execution_tool_call(
            "propose_source_change", {"path": FIXTURE_REL, "new_content": "package x;\n"}
        )
        self.assertFalse(is_error)
        self.assertIn("APPROVED", result)
        self.assertEqual(len(wt._pending_edits), 1)

    # --- 2/3. approval is not model-callable -----------------------------

    def test_approval_not_present_in_tool_schemas_by_exact_name(self):
        # Exact-name set membership, not substring search — a substring
        # check would false-positive on "apply_APPROVEd_source_change".
        names = {schema["name"] for schema in et.EXECUTION_TOOL_SCHEMAS}
        self.assertNotIn("approve_edit", names)
        self.assertNotIn("reject_edit", names)
        self.assertNotIn("grant_approval", names)
        self.assertNotIn("create_approval", names)

    def test_approval_not_reachable_through_dispatch_by_any_name(self):
        self.assertNotIn("approve_edit", et._EXECUTION_DISPATCH)
        self.assertNotIn("reject_edit", et._EXECUTION_DISPATCH)
        # Even an unrecognized/spoofed name falls through to the read-only
        # dispatcher, never to approve_edit/reject_edit.
        result, is_error = et.dispatch_execution_tool_call("approve_edit", {"edit_id": "x"})
        self.assertTrue(is_error)
        self.assertIn("unknown tool", result)

    def test_propose_schema_has_no_field_that_could_carry_an_approval_decision(self):
        schema = next(s for s in et.EXECUTION_TOOL_SCHEMAS if s["name"] == "propose_source_change")
        props = set(schema["input_schema"]["properties"])
        self.assertEqual(props, {"path", "new_content"})

    def test_model_supplied_approval_field_is_ignored_not_honored(self):
        """Even if a model somehow included an 'approved'/'approval' field
        in its tool_use input, propose_source_change's implementation never
        reads it — the human prompt is always what decides."""
        et.set_approval_prompt(_reject)
        result, is_error = et.dispatch_execution_tool_call(
            "propose_source_change",
            {"path": FIXTURE_REL, "new_content": "package x;\n", "approved": True, "approval": "yes"},
        )
        self.assertIn("REJECTED", result)

    # --- 4/6. unapproved / rejected proposals cannot be applied -----------

    def test_rejected_proposal_cannot_be_applied(self):
        et.set_approval_prompt(_reject)
        propose_result, _ = et.dispatch_execution_tool_call(
            "propose_source_change", {"path": FIXTURE_REL, "new_content": "package x;\n"}
        )
        self.assertIn("REJECTED", propose_result)
        self.assertEqual(len(wt._pending_edits), 0)  # reject_edit removes it
        self.assertFalse((tools.REPO_ROOT / FIXTURE_REL).exists())

    # --- 5/7. approved proposal applies exactly once ----------------------

    def test_approved_proposal_applies_once_then_reapply_fails(self):
        et.set_approval_prompt(_approve)
        propose_result, _ = et.dispatch_execution_tool_call(
            "propose_source_change", {"path": FIXTURE_REL, "new_content": "package x; // v1\n"}
        )
        edit_id = list(wt._pending_edits.keys())[0]

        apply_result, apply_error = et.dispatch_execution_tool_call(
            "apply_approved_source_change", {"edit_id": edit_id}
        )
        self.assertFalse(apply_error)
        self.assertEqual(
            (tools.REPO_ROOT / FIXTURE_REL).read_text(encoding="utf-8"), "package x; // v1\n"
        )

        replay_result, replay_error = et.dispatch_execution_tool_call(
            "apply_approved_source_change", {"edit_id": edit_id}
        )
        self.assertTrue(replay_error)
        self.assertIn("already applied", replay_result)

    # --- 8/9. substitution after approval (integration touch; full depth
    # already covered by test_write_tools.py) -----------------------------

    def test_content_substitution_after_approval_rejected_via_dispatch(self):
        et.set_approval_prompt(_approve)
        et.dispatch_execution_tool_call(
            "propose_source_change", {"path": FIXTURE_REL, "new_content": "package x; // orig\n"}
        )
        edit_id = list(wt._pending_edits.keys())[0]
        wt._pending_edits[edit_id].new_content = "package x; // SUBSTITUTED\n"

        result, is_error = et.dispatch_execution_tool_call(
            "apply_approved_source_change", {"edit_id": edit_id}
        )
        self.assertTrue(is_error)
        self.assertIn("changed since approval", result)

    # --- 10-14. write boundary still enforced through the live surface ----

    def test_write_boundary_rejections_reach_the_model_as_errors_via_dispatch(self):
        et.set_approval_prompt(_approve)
        cases = [
            ("../../etc/evil.java", "traversal"),
            ("C:/Windows/evil.java", "absolute"),
            ("docs/DECISIONS.md", "approved source scope"),
            ("app/pom.xml", "approved source scope"),
            (
                "app/src/main/java/com/example/customer/_v41_fixture/testcredentials.java",
                "blocked for safety",
            ),
        ]
        for path, expected_fragment in cases:
            result, is_error = et.dispatch_execution_tool_call(
                "propose_source_change", {"path": path, "new_content": "x"}
            )
            self.assertTrue(is_error, f"expected rejection for {path!r}")
            self.assertIn(expected_fragment, result)
        self.assertEqual(len(wt._pending_edits), 0)

    # --- 15/16/17. compile/test allowlisted, no arbitrary command surface -

    def test_run_controlled_compile_invokes_only_compile_goal(self):
        with mock.patch("build_tools.run_maven") as mocked:
            mocked.return_value = {"goal": "compile", "success": True, "duration_ms": 1.0, "output": "ok"}
            result, is_error = et.dispatch_execution_tool_call("run_controlled_compile", {})
            mocked.assert_called_once_with("compile")
        self.assertFalse(is_error)

    def test_run_controlled_tests_invokes_only_test_goal(self):
        with mock.patch("build_tools.run_maven") as mocked:
            mocked.return_value = {"goal": "test", "success": True, "duration_ms": 1.0, "output": "ok"}
            result, is_error = et.dispatch_execution_tool_call("run_controlled_tests", {})
            mocked.assert_called_once_with("test")
        self.assertFalse(is_error)

    def test_no_tool_accepts_an_arbitrary_command_argument(self):
        for schema in et.EXECUTION_TOOL_SCHEMAS:
            if schema["name"] in ("run_controlled_compile", "run_controlled_tests"):
                self.assertEqual(schema["input_schema"]["properties"], {})

    # --- fail-closed when no real terminal is available -------------------

    def test_default_prompt_fails_closed_on_eof_not_crash(self):
        """Regression test: input() raises EOFError in a non-interactive
        environment (confirmed empirically this session). The default
        prompt must fail closed (reject), never crash and never approve."""
        with mock.patch("builtins.input", side_effect=EOFError):
            edit = wt.propose_edit(FIXTURE_REL, "package x;\n")
            result = et._default_approval_prompt(edit)
        self.assertFalse(result)
        wt.reject_edit(edit.id)

    # --- metrics ----------------------------------------------------------

    def test_metrics_capture_the_full_propose_approve_apply_cycle(self):
        et.set_approval_prompt(_approve)
        et.dispatch_execution_tool_call(
            "propose_source_change", {"path": FIXTURE_REL, "new_content": "package x;\n"}
        )
        edit_id = list(wt._pending_edits.keys())[0]
        et.dispatch_execution_tool_call("apply_approved_source_change", {"edit_id": edit_id})

        tools_called = [e["tool"] for e in metrics.get_tool_call_events()]
        self.assertIn("propose_edit", tools_called)
        self.assertIn("approval_decision", tools_called)
        self.assertIn("apply_edit", tools_called)


if __name__ == "__main__":
    unittest.main()
