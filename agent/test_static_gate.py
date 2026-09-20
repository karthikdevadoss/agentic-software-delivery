"""
Tests for static_gate.py (BL-018, 2026-09-20). Real defect this closes:
a real, live violation (scripts/deploy_customer_app.sh, mode 100644
despite a real #!/usr/bin/env bash shebang) was found and fixed by this
gate's own first real run -- see git history / docs/RETRO_LOG.md.

Run: python agent/test_static_gate.py
"""

import unittest

import static_gate


class CandidateDetectionTestCase(unittest.TestCase):
    def test_mvnw_is_a_candidate(self):
        self.assertTrue(static_gate._is_candidate("app/mvnw"))
        self.assertTrue(static_gate._is_candidate("services/billing-service/mvnw"))

    def test_sh_file_is_a_candidate(self):
        self.assertTrue(static_gate._is_candidate("scripts/deploy_customer_app.sh"))

    def test_anything_under_scripts_is_a_candidate(self):
        self.assertTrue(static_gate._is_candidate("scripts/some_new_tool.py"))

    def test_unrelated_java_file_is_not_a_candidate(self):
        self.assertFalse(static_gate._is_candidate("app/src/main/java/com/example/customer/Foo.java"))


class RealRepoCheckTestCase(unittest.TestCase):
    """Runs the real check against the real, current repo state -- proves
    the gate actually works end-to-end, not just its helper functions."""

    def test_real_repo_currently_has_no_violations(self):
        # This IS the regression test for the real bug this gate found and
        # fixed on its first real run (scripts/deploy_customer_app.sh was
        # mode 100644 with a real shebang). If this ever fails again, a
        # real file lost its executable bit -- exactly the class of bug
        # this gate exists to catch.
        violations = static_gate.check()
        self.assertEqual(violations, [], f"real STATIC violations found: {violations}")

    def test_all_mvnw_scripts_are_executable(self):
        pairs = static_gate._list_tracked_with_mode()
        mvnw_files = [(mode, path) for mode, path in pairs if path.rsplit("/", 1)[-1] == "mvnw"]
        self.assertGreater(len(mvnw_files), 0, "expected to find at least one real mvnw file in this repo")
        for mode, path in mvnw_files:
            self.assertEqual(mode, "100755", f"{path} lost its executable bit")


if __name__ == "__main__":
    unittest.main()
