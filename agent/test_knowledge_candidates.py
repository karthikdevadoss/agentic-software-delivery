"""
Focused tests for agent/knowledge_candidates.py (Phase E14: smallest real
knowledge-candidate pipeline). Runs against the REAL live event ledger,
consistent with this project's convention (agent/test_event_ledger.py) of
proving actual remote behavior rather than mocking it.

Run: python agent/test_knowledge_candidates.py
"""

import unittest
import uuid

import knowledge_candidates as kc


def _unique(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class CreateCandidateTestCase(unittest.TestCase):
    def test_create_candidate_lands_in_candidate_state_never_verified(self):
        run_id = _unique("test-kc-create")
        result = kc.create_candidate(
            run_id=run_id,
            requirement_text="Test requirement",
            git_commit="abc1234",
            decisions=["chose X over Y"],
            tests=["test_foo passed"],
            failure_root_cause=None,
            actors=[{"role": "implementer", "model": "claude-sonnet-5"}],
            human_intervention=None,
            tokens_cost={"input_tokens": 100, "output_tokens": 20},
            lessons=["a real lesson"],
        )
        self.assertEqual(result["state"], kc.CANDIDATE)
        self.assertTrue(result["remote_persisted"])

    def test_never_stores_a_field_it_was_not_explicitly_given(self):
        """Guards against silently fabricating content -- an unsupplied
        field must come back empty/None, never invented."""
        run_id = _unique("test-kc-minimal")
        kc.create_candidate(run_id=run_id, requirement_text="Minimal case")
        found = [c for c in kc.list_candidates_for_review(limit=200) if c["run_id"] == run_id]
        self.assertEqual(len(found), 1)
        payload = found[0]["candidate"]
        self.assertEqual(payload["decisions"], [])
        self.assertEqual(payload["tests"], [])
        self.assertIsNone(payload["failure_root_cause"])
        self.assertIsNone(payload["human_intervention"])


class StateTransitionTestCase(unittest.TestCase):
    def test_invalid_state_is_rejected(self):
        with self.assertRaises(ValueError):
            kc.set_candidate_state(_unique("test-kc-bad-state"), "PUBLISHED")

    def test_candidate_not_auto_promoted_without_an_explicit_state_change(self):
        """The core non-negotiable rule: creating a candidate must NEVER
        by itself result in VERIFIED -- only an explicit, separately
        recorded reviewer action can do that."""
        run_id = _unique("test-kc-no-auto-promote")
        kc.create_candidate(run_id=run_id, requirement_text="Should stay CANDIDATE")
        found = [c for c in kc.list_candidates_for_review(limit=200) if c["run_id"] == run_id]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["current_state"], kc.CANDIDATE)

    def test_explicit_state_change_is_reflected_and_attributed(self):
        run_id = _unique("test-kc-verify")
        kc.create_candidate(run_id=run_id, requirement_text="Will be verified")
        kc.set_candidate_state(run_id, kc.VERIFIED, reviewer="test_suite", reason="manually reviewed in test")
        found = [c for c in kc.list_candidates_for_review(limit=200) if c["run_id"] == run_id]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["current_state"], kc.VERIFIED)
        self.assertEqual(found[0]["review_note"]["reviewer"], "test_suite")

    def test_state_change_is_append_only_original_candidate_event_untouched(self):
        """The original knowledge_candidate event's own payload state
        field must remain 'CANDIDATE' forever -- current status comes
        from the latest state_change event, never from mutating history."""
        run_id = _unique("test-kc-append-only")
        kc.create_candidate(run_id=run_id, requirement_text="Append-only check")
        kc.set_candidate_state(run_id, kc.STALE, reviewer="test_suite", reason="superseded by later work")
        found = [c for c in kc.list_candidates_for_review(limit=200) if c["run_id"] == run_id]
        self.assertEqual(found[0]["candidate"]["state"], kc.CANDIDATE)  # original event, untouched
        self.assertEqual(found[0]["current_state"], kc.STALE)  # derived from latest state-change event


if __name__ == "__main__":
    unittest.main(verbosity=2)
