"""Tests for the governance clause gate.

The first test is the ordinary one: the real repository passes.

The second test is the one that makes the first one worth anything. A
"clean" result from a detector proves nothing until the detector has been
observed rejecting the known-bad case -- the rule this project wrote down after
Sprint 4's BL-032, where a careful root-cause read reached a wrong conclusion
because the evidence field it trusted had already been truncated upstream. So
this file seeds a real mutation (a required clause deleted from a real copy of
the real file) and asserts the gate FAILS on it, naming the right clause.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

import governance_clauses as gc


class TestRealRepositoryPasses(unittest.TestCase):
    def test_every_required_clause_is_present(self):
        missing = gc.missing_clauses()
        self.assertEqual(
            missing,
            [],
            "required governing clause(s) absent from the canonical files: "
            + ", ".join(f"{cid} ({path})" for cid, path, _ in missing),
        )

    def test_the_clause_list_is_not_empty(self):
        # A gate over an empty requirement list passes vacuously and would be
        # worse than no gate, because it reports PASS.
        self.assertGreater(len(gc.REQUIRED_CLAUSES), 10)


class TestGateDetectsTheKnownBadCase(unittest.TestCase):
    """Seeded-mutation proof: the gate must reject text with a clause removed."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for rel in sorted({rel for rel, _, _ in gc.REQUIRED_CLAUSES.values()}):
            src = gc.REPO_ROOT / rel
            dst = self.tmp / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_unmutated_copy_passes(self):
        # Control. If the copy itself failed, a later failure would prove nothing.
        self.assertEqual(gc.missing_clauses(self.tmp), [])

    def test_deleting_the_sunk_cost_clause_is_detected(self):
        rel, needle, _ = gc.REQUIRED_CLAUSES["sunk_cost_rejected"]
        target = self.tmp / rel
        text = target.read_text(encoding="utf-8")
        self.assertIn(needle, text)
        target.write_text(text.replace(needle, "", 1), encoding="utf-8")

        missing = gc.missing_clauses(self.tmp)
        ids = [cid for cid, _, _ in missing]
        self.assertIn("sunk_cost_rejected", ids)

    def test_deleting_the_deep_consensus_guard_is_detected(self):
        rel, needle, _ = gc.REQUIRED_CLAUSES["dc_guard_returns_stopped_by_rule"]
        target = self.tmp / rel
        text = target.read_text(encoding="utf-8")
        target.write_text(text.replace(needle, "may be reconsidered", 1), encoding="utf-8")

        ids = [cid for cid, _, _ in gc.missing_clauses(self.tmp)]
        self.assertIn("dc_guard_returns_stopped_by_rule", ids)

    def test_a_missing_file_is_detected_not_skipped(self):
        (self.tmp / "docs" / "CONSTITUTION.md").unlink()
        missing = gc.missing_clauses(self.tmp)
        ids = [cid for cid, _, _ in missing]
        self.assertIn("constitution_stop_checks", ids)
        self.assertTrue(any("FILE MISSING" in answers for _, _, answers in missing))

    def test_crlf_checkout_does_not_read_as_a_missing_clause(self):
        # A multi-line clause must not fail merely because git checked the file
        # out with CRLF endings on Windows.
        rel, _, _ = gc.REQUIRED_CLAUSES["no_default_continue"]
        target = self.tmp / rel
        text = target.read_text(encoding="utf-8")
        target.write_text(text.replace("\n", "\r\n"), encoding="utf-8", newline="")
        ids = [cid for cid, _, _ in gc.missing_clauses(self.tmp)]
        self.assertNotIn("no_default_continue", ids)


if __name__ == "__main__":
    unittest.main()
