"""
Focused tests for aggregate_evidence.py (BL-029, 2026-09-20).

Real incident this closes: agent/.verify_change_evidence/*.json has been
real, structured data since BL-017/BL-020, but nothing ever aggregated it
into cross-run metrics -- docs/TESTING_ARCHITECTURE_V1.md's own "Open
items" section flagged this explicitly as gap 5.

Isolated from the real (shared) EVIDENCE_DIR throughout, same pattern as
test_verify_change.py::AggregateEvidenceTestCase, to avoid picking up
stale/real data from an unrelated run on this machine.

Run: python agent/test_aggregate_evidence.py
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import aggregate_evidence as ae
import verify_change as vc


class IsolatedEvidenceDirTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._real_evidence_dir = vc.EVIDENCE_DIR
        vc.EVIDENCE_DIR = Path(self.tmpdir)
        self.addCleanup(self._restore)

    def _restore(self):
        vc.EVIDENCE_DIR = self._real_evidence_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write(self, name, **fields):
        base = {
            "timestamp_utc": "2026-09-20T00:00:00+00:00",
            "changed_paths": [],
            "verdict": "PASSED",
            "escaped_defects": None,
            "independent_evaluation": {"invoked": False, "verdict": None, "findings_count": None},
            "commands": [],
        }
        base.update(fields)
        (vc.EVIDENCE_DIR / name).write_text(json.dumps(base), encoding="utf-8")


class NoEvidenceTestCase(IsolatedEvidenceDirTestCase):
    """A genuinely empty EVIDENCE_DIR (or one that doesn't exist yet) must
    produce real zeros/None, never a crash and never a fabricated number."""

    def test_missing_directory_is_handled(self):
        shutil.rmtree(vc.EVIDENCE_DIR, ignore_errors=True)
        result = ae.aggregate()
        self.assertEqual(result["total_runs"], 0)
        self.assertIsNone(result["first_pass_yield"])
        self.assertFalse(result["time_rollup"]["available"])
        self.assertFalse(result["cost_rollup"]["available"])
        self.assertFalse(result["rework"]["authoritative_rework_ratio"]["available"])

    def test_empty_directory_is_handled(self):
        result = ae.aggregate()
        self.assertEqual(result["total_runs"], 0)
        self.assertIsNone(result["first_pass_yield"])


class FirstPassYieldTestCase(IsolatedEvidenceDirTestCase):
    def test_all_clean_passed_runs_yield_100_percent(self):
        self._write("a.json", verdict="PASSED")
        self._write("b.json", verdict="PASSED")
        result = ae.aggregate()
        self.assertEqual(result["first_pass_yield"], 1.0)
        self.assertEqual(result["total_runs"], 2)

    def test_failed_run_lowers_yield(self):
        self._write("a.json", verdict="PASSED")
        self._write("b.json", verdict="FAILED")
        result = ae.aggregate()
        self.assertEqual(result["first_pass_yield"], 0.5)

    def test_passed_run_with_escaped_defect_is_not_clean(self):
        self._write("a.json", verdict="PASSED", escaped_defects=1)
        result = ae.aggregate()
        self.assertEqual(result["first_pass_yield"], 0.0)

    def test_passed_run_with_none_escaped_defects_is_still_clean(self):
        # None means "never revisited", not "has a defect" -- must NOT be
        # penalized the same way a real escaped_defects=1 is.
        self._write("a.json", verdict="PASSED", escaped_defects=None)
        result = ae.aggregate()
        self.assertEqual(result["first_pass_yield"], 1.0)

    def test_passed_run_with_independent_evaluation_findings_is_not_clean(self):
        self._write("a.json", verdict="PASSED", independent_evaluation={
            "invoked": True, "verdict": "FAIL", "findings_count": 2,
        })
        result = ae.aggregate()
        self.assertEqual(result["first_pass_yield"], 0.0)

    def test_passed_run_with_independent_evaluation_zero_findings_is_clean(self):
        self._write("a.json", verdict="PASSED", independent_evaluation={
            "invoked": True, "verdict": "PASS", "findings_count": 0,
        })
        result = ae.aggregate()
        self.assertEqual(result["first_pass_yield"], 1.0)

    def test_dry_run_is_excluded_from_yield_denominator(self):
        self._write("a.json", verdict="PASSED")
        self._write("b.json", verdict="DRY_RUN")
        result = ae.aggregate()
        # Only the one real (non-dry-run) run counts -- 1/1, not 1/2.
        self.assertEqual(result["first_pass_yield"], 1.0)
        self.assertEqual(result["total_runs"], 2)
        self.assertEqual(result["dry_runs_excluded_from_yield"], 1)

    def test_only_dry_runs_gives_none_not_a_fabricated_ratio(self):
        self._write("a.json", verdict="DRY_RUN")
        result = ae.aggregate()
        self.assertIsNone(result["first_pass_yield"])


class TimeRollupTestCase(IsolatedEvidenceDirTestCase):
    def test_no_duration_fields_reports_insufficient_data(self):
        self._write("a.json", commands=[{"name": "x", "exit_code": 0}])  # no duration_seconds key
        result = ae.aggregate()
        self.assertFalse(result["time_rollup"]["available"])

    def test_real_durations_are_summed_correctly(self):
        self._write("a.json", commands=[
            {"name": "x", "exit_code": 0, "duration_seconds": 10.0},
            {"name": "y", "exit_code": 0, "duration_seconds": 5.0},
        ])
        self._write("b.json", commands=[
            {"name": "x", "exit_code": 0, "duration_seconds": 3.0},
        ])
        result = ae.aggregate()
        t = result["time_rollup"]
        self.assertTrue(t["available"])
        self.assertEqual(t["runs_with_timing"], 2)
        self.assertEqual(t["total_command_seconds"], 18.0)
        self.assertEqual(t["total_wall_seconds_by_run"], 18.0)
        self.assertEqual(t["avg_run_seconds"], 9.0)
        self.assertEqual(t["min_run_seconds"], 3.0)
        self.assertEqual(t["max_run_seconds"], 15.0)


class CostRollupTestCase(IsolatedEvidenceDirTestCase):
    def test_cost_is_always_insufficient_data_for_the_real_schema(self):
        self._write("a.json", verdict="PASSED")
        result = ae.aggregate()
        self.assertFalse(result["cost_rollup"]["available"])
        self.assertEqual(result["cost_rollup"]["cost_like_keys_actually_found_in_evidence"], [])

    def test_a_cost_like_key_if_ever_present_is_surfaced_not_silently_dropped(self):
        # Proves the detector itself works, in case the schema ever gains
        # a cost field later -- this test should start failing loudly
        # (cost_rollup still reporting unavailable) the day that happens,
        # which is the intended signal to build real cost aggregation.
        self._write("a.json", verdict="PASSED", cost_usd=0.05)
        result = ae.aggregate()
        self.assertIn("cost_usd", result["cost_rollup"]["cost_like_keys_actually_found_in_evidence"])


class ReworkIndicatorTestCase(IsolatedEvidenceDirTestCase):
    def test_authoritative_rework_ratio_is_always_insufficient_data(self):
        self._write("a.json")
        result = ae.aggregate()
        self.assertFalse(result["rework"]["authoritative_rework_ratio"]["available"])

    def test_no_flagged_runs_gives_zero_heuristic_candidates(self):
        self._write("a.json", changed_paths=["agent/foo.py"], verdict="PASSED")
        self._write("b.json", changed_paths=["agent/foo.py"], verdict="PASSED")
        result = ae.aggregate()
        self.assertEqual(result["rework"]["heuristic_path_overlap_rework_candidates"]["count"], 0)

    def test_later_run_touching_same_path_as_a_flagged_run_is_a_heuristic_candidate(self):
        self._write("a.json", timestamp_utc="2026-09-20T00:00:00+00:00",
                     changed_paths=["agent/foo.py"], verdict="PASSED", escaped_defects=1)
        self._write("b.json", timestamp_utc="2026-09-20T01:00:00+00:00",
                     changed_paths=["agent/foo.py"], verdict="PASSED")
        result = ae.aggregate()
        rw = result["rework"]["heuristic_path_overlap_rework_candidates"]
        self.assertEqual(rw["count"], 1)
        self.assertEqual(rw["flagged_runs_used_as_basis"], 1)

    def test_earlier_run_is_never_counted_as_rework_for_a_later_flag(self):
        # Order matters: a run BEFORE the flagged run must not count.
        self._write("a.json", timestamp_utc="2026-09-20T00:00:00+00:00",
                     changed_paths=["agent/foo.py"], verdict="PASSED")
        self._write("b.json", timestamp_utc="2026-09-20T01:00:00+00:00",
                     changed_paths=["agent/foo.py"], verdict="PASSED", escaped_defects=1)
        result = ae.aggregate()
        self.assertEqual(result["rework"]["heuristic_path_overlap_rework_candidates"]["count"], 0)


class RealEvidenceShapeTestCase(unittest.TestCase):
    """Proves this module's assumptions actually match verify_change.py's
    real evidence-writing code, not a remembered/guessed schema -- runs
    execute() with dry_run=True (no subprocess calls) and feeds the real
    resulting dict straight into aggregate_evidence's own functions."""

    def test_a_real_dry_run_evidence_dict_is_handled_without_crashing(self):
        class FakeClassification:
            risk = "LOW"
            blast_radius = "LOCAL"
            unrecognized_paths = []

        class FakeSelection:
            classification = FakeClassification()
            fail_closed = False
            fail_closed_reason = None
            java_tests = []
            reasons = []
            skipped = []
            playwright_specs = []

        real_evidence = vc.execute(["agent/foo.py"], FakeSelection(), dry_run=True)
        self.assertEqual(real_evidence["verdict"], "DRY_RUN")
        self.assertTrue(ae._is_clean_first_pass(real_evidence) is False)  # DRY_RUN never counts as a clean PASS


if __name__ == "__main__":
    unittest.main()
