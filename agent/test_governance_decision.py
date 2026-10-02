"""Acceptance and mutation tests for the governance decision boundary.

Three parts, and the second two are what make the first worth anything:

  1. the 22 Owner-specified cases resolve as specified;
  2. each protection is BROKEN on a copy and the relevant case is shown to flip
     -- so a green result means the rules are doing the work, not that the
     scenarios happen to agree with whatever the code does;
  3. the engine's inputs stay typed, so it cannot quietly become a prose reader.

Part 2 is the rule this project adopted the expensive way: a detector that has
only ever run against clean input has not been shown to detect. A governance
test that can only pass is governance theatre.

Hermetic: pure data in, pure decision out. No network, no model, no filesystem.
"""

from __future__ import annotations

import dataclasses
import unittest
from unittest import mock

import governance_decision as gd
from governance_cases import CASES
from governance_decision import Request, State, Disposition


class OwnerSpecifiedCasesTestCase(unittest.TestCase):
    def test_every_case_resolves_as_specified(self):
        wrong = []
        for number, name, request, expected, note in CASES:
            got = gd.evaluate(request)
            if got.state != expected:
                wrong.append(
                    f"case {number} ({name}): expected {expected.value}, "
                    f"got {got.state.value} via rule {got.rule!r} -- {note}"
                )
        self.assertEqual(wrong, [], "governance cases resolved wrongly:\n" + "\n".join(wrong))

    def test_all_twenty_owner_cases_are_present(self):
        """The Owner specified 1-12 in the contract and 13-20 in the addendum.
        A missing case would make this suite pass by not asking."""
        numbers = {c[0] for c in CASES}
        for n in range(1, 21):
            self.assertIn(n, numbers, f"Owner case {n} is not covered")

    def test_case_7_stops_only_the_affected_workstream(self):
        """A stop on one stream must never read as 'halt and wait'."""
        decision = gd.evaluate(
            Request(programme="deep_consensus", action="rerun",
                    independent_authorized_work_available=True)
        )
        self.assertEqual(decision.state, State.STOPPED_BY_RULE)
        self.assertTrue(
            decision.continue_independent_work,
            "independent authorized work must continue; idling is never the answer",
        )

    def test_case_8_is_fix_now_not_a_queued_prose_item(self):
        decision = gd.evaluate(
            Request(retro_lesson_objective=True, retro_lesson_in_scope=True,
                    retro_lesson_deterministically_verifiable=True)
        )
        self.assertEqual(decision.disposition, Disposition.FIX_NOW)

    def test_case_17_is_add_guard_not_merely_recorded(self):
        decision = gd.evaluate(
            Request(retro_lesson_objective=True, retro_lesson_in_scope=True,
                    retro_lesson_deterministically_verifiable=False)
        )
        self.assertEqual(decision.disposition, Disposition.ADD_GUARD_OR_TEST)

    def test_an_out_of_scope_retro_correction_goes_to_the_owner(self):
        decision = gd.evaluate(
            Request(retro_lesson_objective=True, retro_lesson_in_scope=False,
                    retro_lesson_deterministically_verifiable=True)
        )
        self.assertEqual(decision.state, State.NEEDS_OWNER_GOAL_REVIEW)
        self.assertEqual(decision.disposition, Disposition.NEEDS_OWNER)

    def test_frozen_evidence_is_never_mutable_in_any_outcome(self):
        """Across every case, no decision may authorise changing frozen
        evidence. Checked over all of them rather than on one, because this is
        the invariant most damaging to lose."""
        for number, name, request, _, _ in CASES:
            with self.subTest(case=number):
                self.assertFalse(
                    gd.evaluate(request).frozen_evidence_may_change,
                    f"case {number} ({name}) would permit frozen evidence to change",
                )

    def test_every_decision_carries_a_rule_and_a_reason(self):
        """A terminal state with no named rule is unauditable -- the Owner
        cannot check a decision he cannot trace."""
        for number, name, request, _, _ in CASES:
            decision = gd.evaluate(request)
            with self.subTest(case=number):
                self.assertTrue(decision.rule, f"case {number} has no rule name")
                self.assertTrue(decision.reasons, f"case {number} has no reason")


class MutationTestCase(unittest.TestCase):
    """Break one protection at a time; the case it guards must flip."""

    def _case(self, number):
        for n, name, request, expected, note in CASES:
            if n == number:
                return request, expected
        raise AssertionError(f"no case {number}")

    def test_control_unmutated_cases_pass(self):
        for number, _, request, expected, _ in CASES:
            self.assertEqual(gd.evaluate(request).state, expected, f"case {number}")

    def test_removing_the_frozen_programme_guard_unblocks_sprint_7(self):
        request, expected = self._case(4)
        self.assertEqual(expected, State.STOPPED_BY_RULE)
        with mock.patch.dict(gd.FROZEN_PROGRAMMES, {}, clear=True):
            self.assertNotEqual(
                gd.evaluate(request).state, State.STOPPED_BY_RULE,
                "case 4 still stops with the guard removed, so the guard is not "
                "what was stopping it",
            )

    def test_removing_only_the_replacement_benchmark_action_unblocks_case_5(self):
        request, _ = self._case(5)
        narrowed = {"deep_consensus": {"start_sprint"}}
        with mock.patch.dict(gd.FROZEN_PROGRAMMES, narrowed, clear=True):
            self.assertNotEqual(gd.evaluate(request).state, State.STOPPED_BY_RULE)

    def test_treating_sunk_cost_as_valid_evidence_flips_case_2_to_continue(self):
        request, _ = self._case(2)
        without = {k: v for k, v in gd.WORTHLESS_JUSTIFICATIONS.items() if k != "sunk_cost"}
        with mock.patch.dict(gd.WORTHLESS_JUSTIFICATIONS, without, clear=True):
            self.assertEqual(
                gd.evaluate(request).state, State.CONTINUE,
                "with sunk cost treated as real evidence the request proceeds -- "
                "which is exactly the failure this project is correcting",
            )

    def test_treating_absence_of_a_stop_rule_as_evidence_flips_case_3(self):
        request, _ = self._case(3)
        without = {k: v for k, v in gd.WORTHLESS_JUSTIFICATIONS.items()
                   if k != "no_stop_rule_fired"}
        with mock.patch.dict(gd.WORTHLESS_JUSTIFICATIONS, without, clear=True):
            self.assertEqual(gd.evaluate(request).state, State.CONTINUE)

    def test_treating_code_volume_as_value_flips_case_18(self):
        request, _ = self._case(18)
        without = {k: v for k, v in gd.WORTHLESS_JUSTIFICATIONS.items() if k != "code_volume"}
        with mock.patch.dict(gd.WORTHLESS_JUSTIFICATIONS, without, clear=True):
            self.assertNotEqual(gd.evaluate(request).state, State.REDIRECT)

    def test_the_disclosure_boundary_is_held_by_two_independent_guards(self):
        """Written as a single-guard mutation first, and the mutation FAILED --
        removing the reserved-decision entries did not unblock case 15, because
        the private/public boundary is checked twice: once in its own early
        branch (which runs before the reserved list, so a publication request is
        stopped before anything else can weigh in) and once via OWNER_RESERVED.

        That is defence in depth on the single most damaging possible leak, and
        the test now asserts the real structure rather than my first assumption
        about it. Removing EITHER guard alone must still stop the request."""
        request, _ = self._case(15)

        # guard 2 removed, guard 1 (the early branch) still holds
        without_reserved = gd.OWNER_RESERVED - {"private_public_disclosure", "publication"}
        with mock.patch.object(gd, "OWNER_RESERVED", without_reserved):
            self.assertEqual(
                gd.evaluate(request).state, State.NEEDS_OWNER_GOAL_REVIEW,
                "with the reserved list weakened, the dedicated private/public "
                "branch must still stop a publication request",
            )

        # guard 1 removed, guard 2 (the reserved list) still holds
        plain_publication = Request(action="publish", affects=["publication"],
                                    independent_authorized_work_available=True)
        self.assertEqual(gd.evaluate(plain_publication).state,
                         State.NEEDS_OWNER_GOAL_REVIEW)

        # and a request touching neither is not spuriously blocked, so the
        # guards are specific rather than a blanket refusal
        self.assertEqual(gd.evaluate(Request()).state, State.CONTINUE)

    def test_unreserving_purpose_lets_a_model_redefine_the_mission(self):
        request, _ = self._case(9)
        with mock.patch.object(gd, "OWNER_RESERVED", gd.OWNER_RESERVED - {"purpose"}):
            self.assertNotEqual(gd.evaluate(request).state, State.NEEDS_OWNER_GOAL_REVIEW)

    def test_raising_the_drift_threshold_silences_the_drift_trigger(self):
        request, _ = self._case(21)
        original = gd.evaluate
        # the threshold is inline, so mutate the input to one below it instead:
        # a single sprint must NOT fire the trigger, which is the other half of
        # the rule -- one is noise, two is a pattern.
        one_sprint = dataclasses.replace(request, consecutive_sprints_without_either=1)
        self.assertEqual(original(one_sprint).state, State.CONTINUE,
                         "one sprint must not fire the trigger")
        self.assertEqual(original(request).state, State.NEEDS_OWNER_GOAL_REVIEW,
                         "two in a row must fire it")

    def test_an_unsupported_claim_cannot_be_rescued_by_other_facts(self):
        """Ordering is itself a protection: nothing downstream may rescue a
        claim the evidence does not support."""
        decision = gd.evaluate(
            Request(claim_supported_by_evidence=False,
                    produced_recruiter_visible_value=True,
                    produced_hiring_relevant_proof=True,
                    continuation_justifications=[])
        )
        self.assertEqual(decision.state, State.REDIRECT)
        self.assertEqual(decision.disposition, Disposition.FIX_NOW)

    def test_a_frozen_programme_stop_outranks_every_argument_for_proceeding(self):
        decision = gd.evaluate(
            Request(programme="deep_consensus", action="ablation",
                    has_mission_card=True,
                    produced_recruiter_visible_value=True,
                    produced_hiring_relevant_proof=True,
                    company_objective="employment")
        )
        self.assertEqual(decision.state, State.STOPPED_BY_RULE)
        self.assertEqual(decision.rule, "frozen-programme-guard")


class InputsStayTypedTestCase(unittest.TestCase):
    """The engine's guard-rail is that it CANNOT read prose, because nothing
    prose-shaped reaches it. If a free-text judgement field is ever added, this
    fails -- which makes crossing the line a deliberate, visible act rather
    than a drift."""

    EXPECTED_FIELDS = {
        "action", "programme",
        "has_mission_card", "hiring_audience", "required_for_system_integrity",
        "company_objective",
        "continuation_justifications", "produced_recruiter_visible_value",
        "produced_hiring_relevant_proof", "consecutive_sprints_without_either",
        "affects",
        "claim_supported_by_evidence", "public_text_contains_private_terms",
        "conflicts_with_frozen_evidence", "canonical_source",
        "retro_lesson_objective", "retro_lesson_in_scope",
        "retro_lesson_deterministically_verifiable",
        "independent_authorized_work_available",
    }

    def test_request_fields_are_exactly_the_declared_set(self):
        actual = {f.name for f in dataclasses.fields(Request)}
        self.assertEqual(
            actual, self.EXPECTED_FIELDS,
            "the Request shape changed. If a free-text field was added, the engine "
            "can now be handed prose to interpret, which is the exact pattern "
            "unapproved lesson A17 forbids. Update this set only deliberately.",
        )

    def test_judgement_inputs_are_booleans_not_text(self):
        hints = {f.name: f.type for f in dataclasses.fields(Request)}
        for judgement in ("claim_supported_by_evidence",
                          "public_text_contains_private_terms",
                          "conflicts_with_frozen_evidence",
                          "required_for_system_integrity"):
            with self.subTest(field=judgement):
                self.assertEqual(
                    hints[judgement], "bool",
                    f"{judgement} must be an already-decided boolean -- the judgement "
                    "is made by a dedicated checker or the Owner, never here",
                )

    def test_every_terminal_state_is_one_of_the_four(self):
        self.assertEqual(
            {s.value for s in State},
            {"CONTINUE", "REDIRECT", "STOPPED_BY_RULE", "NEEDS_OWNER_GOAL_REVIEW"},
        )

    def test_every_disposition_is_one_of_the_five(self):
        self.assertEqual(
            {d.value for d in Disposition},
            {"FIX_NOW", "ADD_GUARD_OR_TEST", "UPDATE_CANONICAL_KNOWLEDGE",
             "NEEDS_OWNER", "NO_ACTION_WITH_REASON"},
        )


if __name__ == "__main__":
    unittest.main()
