"""
Focused automated tests for the V4 write/execution boundary
(agent/write_tools.py). Uses a distinctly-named, self-cleaning fixture
path under app/src/test/java/ so no real Customer source is ever at risk,
and verifies real Customer files are untouched after every test.

Run: python agent/test_write_tools.py
"""

import shutil
import unittest

import tools
import write_tools as wt
import metrics

FIXTURE_DIR = tools.REPO_ROOT / "app" / "src" / "test" / "java" / "com" / "example" / "customer" / "_v4_fixture"
FIXTURE_REL = "app/src/test/java/com/example/customer/_v4_fixture/WriteBoundaryFixtureTest.java"

REAL_CONTROLLER = tools.REPO_ROOT / "app/src/main/java/com/example/customer/controller/CustomerController.java"


class WriteToolsTestCase(unittest.TestCase):
    def setUp(self):
        wt._pending_edits.clear()
        metrics.reset()
        self._controller_snapshot = REAL_CONTROLLER.read_text(encoding="utf-8")
        self.addCleanup(self._cleanup_fixture)

    def _cleanup_fixture(self):
        if FIXTURE_DIR.exists():
            shutil.rmtree(FIXTURE_DIR)
        wt._pending_edits.clear()
        # Prove no real Customer source was touched by this test.
        self.assertEqual(REAL_CONTROLLER.read_text(encoding="utf-8"), self._controller_snapshot)

    # --- allowed target: full propose -> approve -> apply lifecycle -------

    def test_allowed_target_full_lifecycle_writes_exact_content(self):
        content = "package com.example.customer._v4_fixture;\npublic class WriteBoundaryFixtureTest {}\n"
        edit = wt.propose_edit(FIXTURE_REL, content)
        self.assertTrue(edit.is_new_file)
        self.assertIn("+public class WriteBoundaryFixtureTest", edit.diff)

        wt.approve_edit(edit.id)
        result = wt.apply_edit(edit.id)
        self.assertIn(edit.id, result)

        written = (tools.REPO_ROOT / FIXTURE_REL).read_text(encoding="utf-8")
        self.assertEqual(written, content)

    def test_unapproved_write_cannot_execute(self):
        edit = wt.propose_edit(FIXTURE_REL, "package x;\n")
        with self.assertRaises(wt.WriteToolError) as ctx:
            wt.apply_edit(edit.id)
        self.assertIn("not been approved", str(ctx.exception))
        self.assertFalse((tools.REPO_ROOT / FIXTURE_REL).exists())

    def test_approved_edit_cannot_be_applied_twice(self):
        edit = wt.propose_edit(FIXTURE_REL, "package x;\n")
        wt.approve_edit(edit.id)
        wt.apply_edit(edit.id)
        with self.assertRaises(wt.WriteToolError):
            wt.apply_edit(edit.id)

    def test_content_substitution_after_approval_is_rejected(self):
        """The approval-integrity gap found and fixed this session: approval
        must be bound to the exact content approved, not just 'this ID was
        approved at some point'."""
        edit = wt.propose_edit(FIXTURE_REL, "package x; // original\n")
        wt.approve_edit(edit.id)
        edit.new_content = "package x; // SUBSTITUTED AFTER APPROVAL\n"
        with self.assertRaises(wt.WriteToolError) as ctx:
            wt.apply_edit(edit.id)
        self.assertIn("changed since approval", str(ctx.exception))
        self.assertFalse((tools.REPO_ROOT / FIXTURE_REL).exists())

    def test_target_substitution_after_approval_is_rejected(self):
        other_fixture_rel = (
            "app/src/test/java/com/example/customer/_v4_fixture/OtherTarget.java"
        )
        edit = wt.propose_edit(FIXTURE_REL, "package x;\n")
        wt.approve_edit(edit.id)
        edit.path = other_fixture_rel
        with self.assertRaises(wt.WriteToolError) as ctx:
            wt.apply_edit(edit.id)
        self.assertIn("changed since approval", str(ctx.exception))
        self.assertFalse((tools.REPO_ROOT / FIXTURE_REL).exists())
        self.assertFalse((tools.REPO_ROOT / other_fixture_rel).exists())

    def test_rejected_edit_cannot_be_applied(self):
        edit = wt.propose_edit(FIXTURE_REL, "package x;\n")
        wt.reject_edit(edit.id)
        with self.assertRaises(wt.WriteToolError):
            wt.apply_edit(edit.id)

    # --- rejection paths ------------------------------------------------

    def test_traversal_rejected(self):
        with self.assertRaises(wt.WriteToolError) as ctx:
            wt.propose_edit("../../etc/evil.java", "x")
        self.assertIn("traversal", str(ctx.exception))

    def test_absolute_path_rejected(self):
        with self.assertRaises(wt.WriteToolError) as ctx:
            wt.propose_edit("C:/Windows/evil.java", "x")
        self.assertIn("absolute", str(ctx.exception))

    def test_out_of_scope_path_rejected(self):
        with self.assertRaises(wt.WriteToolError) as ctx:
            wt.propose_edit("docs/DECISIONS.md", "x")
        self.assertIn("approved source scope", str(ctx.exception))

    def test_pom_xml_rejected_despite_being_a_project_file(self):
        with self.assertRaises(wt.WriteToolError):
            wt.propose_edit("app/pom.xml", "x")

    def test_wrong_extension_in_scope_rejected(self):
        with self.assertRaises(wt.WriteToolError) as ctx:
            wt.propose_edit(
                "app/src/main/java/com/example/customer/_v4_fixture/notes.txt", "x"
            )
        self.assertIn("file type", str(ctx.exception))

    def test_secret_named_new_file_in_scope_rejected(self):
        """Regression test for a real bug found this session: tools.py's
        blocked-name check only ran for files that already existed, so a
        brand-new file named e.g. 'testcredentials.java' slipped through."""
        with self.assertRaises(wt.WriteToolError) as ctx:
            wt.propose_edit(
                "app/src/main/java/com/example/customer/_v4_fixture/testcredentials.java", "x"
            )
        self.assertIn("blocked for safety", str(ctx.exception))

    def test_symlink_escape_rejected_if_creatable_on_this_platform(self):
        target_outside = tools.REPO_ROOT.parent / "outside_target.java"
        link_path = FIXTURE_DIR / "escape.java"
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        target_outside.write_text("outside content", encoding="utf-8")
        self.addCleanup(lambda: target_outside.unlink(missing_ok=True))
        try:
            link_path.symlink_to(target_outside)
        except OSError:
            self.skipTest("symlink creation not permitted on this platform/account")
        rel = str(link_path.relative_to(tools.REPO_ROOT)).replace("\\", "/")
        with self.assertRaises(wt.WriteToolError) as ctx:
            wt.propose_edit(rel, "x")
        self.assertIn("symlink", str(ctx.exception))

    # --- delegation, not reimplementation --------------------------------

    def test_write_scope_check_delegates_to_shared_tools_path_validation(self):
        from unittest import mock
        with mock.patch("tools._resolve_safe_path", side_effect=tools.RepoToolError("boom")) as mocked:
            with self.assertRaises(wt.WriteToolError):
                wt.propose_edit(FIXTURE_REL, "x")
            mocked.assert_called_once_with(FIXTURE_REL)

    # --- unrelated file isolation -----------------------------------------

    def test_unrelated_customer_file_is_never_touched(self):
        edit = wt.propose_edit(FIXTURE_REL, "package x;\n")
        wt.approve_edit(edit.id)
        wt.apply_edit(edit.id)
        # tearDown's _cleanup_fixture already asserts this, but assert
        # explicitly here too so the intent is visible in this test.
        self.assertEqual(REAL_CONTROLLER.read_text(encoding="utf-8"), self._controller_snapshot)

    # --- metrics -----------------------------------------------------

    def test_metrics_recorded_for_blocked_and_successful_calls(self):
        with self.assertRaises(wt.WriteToolError):
            wt.propose_edit("../../etc/evil.java", "x")
        edit = wt.propose_edit(FIXTURE_REL, "package x;\n")
        wt.approve_edit(edit.id)
        wt.apply_edit(edit.id)

        events = metrics.get_tool_call_events()
        tools_called = {e["tool"] for e in events}
        self.assertIn("propose_edit", tools_called)
        self.assertIn("apply_edit", tools_called)

        blocked = [e for e in events if e["tool"] == "propose_edit" and not e["success"]]
        self.assertTrue(any(e["blocked_unsafe"] for e in blocked))


if __name__ == "__main__":
    unittest.main()
