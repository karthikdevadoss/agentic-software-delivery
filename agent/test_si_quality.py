"""The Standing Interview answer-quality suite.

Sprint 15, SI-05/SI-04. Before this file, 0 of 134 test cases looked at answer
quality, which is how a 117/117-green sprint shipped the answers the Owner
rejected.

Sequencing, and why it is not negotiable
----------------------------------------
The audit's Stage 1 says: build the oracle and prove it RED against the six
archived production answers BEFORE any prompt change. Changing the prompt
first would leave no way to tell whether the fix worked or the measurement was
simply absent -- which is the mistake that produced this situation.

So this file contains two different kinds of test, and they are expected to
behave differently at the moment they are written:

  * OracleIsTrustworthy -- must PASS immediately. These prove the oracle
    detects the known-bad answers. Per CLAUDE.md, a diagnostic whose "clean"
    result nobody has seen go dirty is not trusted; these are that proof.

  * RecordedBaseline -- must PASS. It pins the defect as it stood before the
    fix, so the oracle cannot quietly stop detecting it.

  * ProductionAnswerQuality and DoesNotOverRefuse -- FAIL until the fix has
    been deployed and measured. They score a post-fix capture that does not
    exist yet. They fail rather than skip on purpose: a skip reads as green in
    CI, and CLAUDE.md is explicit that SKIPPED is not PASSED. Run
    `python agent/si_recapture.py` after deploying to produce it.

MEASURED BASELINE (this oracle, over the archived capture): 37 unsolicited
negatives across 21 of 57 answered, in four categories -- RECALL_LIMIT 15,
SCOPE_LIMIT 11, ABSENCE 7, OWNERSHIP_DISCLAIMER 4. The audit's own hand-
corrected figure was 38 across 22 of 57; two independent counts landing one
apart is corroboration, not a discrepancy to reconcile.

The baseline fixture is agent/testdata/si_production_answers.json: 63 real answers
captured 2026-09-29 06:45-07:05 UTC from
https://agentic-platform-backend-production.up.railway.app against deploy
marker deploy-20260929T004905Z-8533d67, transcribed verbatim into the audit's
Appendix A and parsed back out. They are real production output, not answers
written to suit the oracle.
"""

from __future__ import annotations

import json
import pathlib
import unittest

from si_quality import (
    ABSENCE,
    OWNERSHIP_DISCLAIMER,
    RECALL_LIMIT,
    SCOPE_LIMIT,
    assess,
    split_sentences,
)

TESTDATA = pathlib.Path(__file__).parent / "testdata"

# The BASELINE: 63 real answers captured BEFORE the Sprint 15 specification
# fix. It is a historical record and never changes. It exists to prove two
# things -- that the oracle detects the defect, and that the defect was really
# there -- so it must keep failing the quality bar forever. An archived answer
# cannot be improved by changing a prompt written after it was generated.
FIXTURE = TESTDATA / "si_production_answers.json"

# The CURRENT capture: the same questions re-run against production AFTER the
# fix is deployed. This is what the quality bar is actually measured on.
# Until it exists, the fix is UNVERIFIED and this suite says so by failing --
# deliberately, because a skip in CI reads as green and CLAUDE.md is explicit
# that SKIPPED is not PASSED.
AFTER_FIXTURE = TESTDATA / "si_production_answers_after.json"

# The six answers the Owner objected to: the three production Kafka draws
# (question a) and the three production Marsh draws (question b). Every shipped
# gate -- leak scan, voice gate, neighbour check, acceptance gate -- returned
# empty for all six.
OWNER_OBJECTED = [("a", 1), ("a", 2), ("a", 3), ("b", 1), ("b", 2), ("b", 3)]


def _load() -> list[dict]:
    if not FIXTURE.exists():
        raise AssertionError(
            f"missing archived production answers at {FIXTURE}; "
            "the quality suite cannot run against invented answers"
        )
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


RECORDS = _load()
ANSWERED = [r for r in RECORDS if r["outcome"] == "answered"]


def _find(qid: str, draw: int) -> dict:
    for r in RECORDS:
        if r["question_id"] == qid and r["draw"] == draw:
            return r
    raise AssertionError(f"archived answer {qid}/draw {draw} not in the fixture")


class FixtureIntegrity(unittest.TestCase):
    """The suite is only as good as the answers it is measured against."""

    def test_fixture_is_the_real_production_capture(self):
        self.assertEqual(len(RECORDS), 63, "the audit captured 63 requests")
        self.assertEqual(len(ANSWERED), 57, "the audit recorded 57 answered")
        self.assertEqual(len({r["question_id"] for r in RECORDS}), 23)
        for r in RECORDS:
            self.assertTrue(
                r["answer"].strip(),
                f"{r['question_id']}/{r['draw']} has no answer text",
            )


class OracleIsTrustworthy(unittest.TestCase):
    """CLAUDE.md: a diagnostic must be proven to detect the known-bad case
    before its clean result is trusted. This class is that proof."""

    def test_oracle_rejects_every_answer_the_owner_objected_to(self):
        missed = []
        for qid, draw in OWNER_OBJECTED:
            rec = _find(qid, draw)
            report = assess(rec["question"], rec["answer"], rec["outcome"])
            if not report.unsolicited:
                missed.append(f"{qid}/draw {draw}")
        self.assertFalse(
            missed,
            f"the oracle found nothing wrong with {missed}, which the Owner "
            f"rejected. A clean result from a detector that cannot detect the "
            f"known defect is meaningless.",
        )

    def test_oracle_names_the_specific_sentences_not_just_a_count(self):
        """A count cannot be acted on. The report must point at the prose."""
        rec = _find("a", 1)
        report = assess(rec["question"], rec["answer"], rec["outcome"])
        sentences = [n.sentence for n in report.unsolicited]
        self.assertTrue(
            any("set up the brokers" in s or "administer" in s for s in sentences),
            f"expected the scope-limit sentence to be named; got {sentences}",
        )
        self.assertTrue(
            any("part of the stack" in s or "didn't use Kafka" in s for s in sentences),
            f"expected the absence sentence to be named; got {sentences}",
        )

    def test_oracle_accepts_a_clean_answer(self):
        """The other direction: a good answer must not be flagged."""
        clean = (
            "At BCBSA I wrote the application-side Kafka producer and consumer "
            "code for member, coverage and claims changes. A backend service "
            "processes a change, publishes an event, and a downstream consumer "
            "applies the update on its side. That kept the receiving service "
            "current without the source service having to coordinate "
            "synchronously with every consumer."
        )
        report = assess("explain your experience with Kafka", clean, "answered")
        self.assertTrue(report.ok, f"a clean answer was rejected:\n{report.describe()}")

    def test_a_refusal_is_not_counted_as_a_quality_defect(self):
        """Hardening 1. Six of the audit detector's 45 raw hits were the
        product's own refusal line on rows that were never answered."""
        rec = next(r for r in RECORDS if r["outcome"] == "private_topic")
        report = assess(rec["question"], rec["answer"], rec["outcome"])
        self.assertFalse(
            report.unsolicited,
            "a correct refusal was scored as a quality defect, which would push "
            f"the system toward answering what it should decline:\n{report.describe()}",
        )

    def test_a_capability_probe_may_be_answered_with_a_no(self):
        """'Have you used Terraform?' -> 'No' is the answer, not an unsolicited
        negative. The audit hard-coded questions n/o/v; this is computed."""
        for qid in ("n", "o", "v"):
            rec = _find(qid, 1)
            report = assess(rec["question"], rec["answer"], rec["outcome"])
            self.assertTrue(
                report.solicited or not report.negatives,
                f"question {qid} ({rec['question']!r}) asks whether a technology "
                f"was used; saying it was not is the answer.\n{report.describe()}",
            )

    def test_sentence_splitter_does_not_swallow_decimals_or_abbreviations(self):
        text = "Cost was 0.39 per run. We used e.g. Redis. That is all."
        self.assertEqual(len(split_sentences(text)), 3)

    def test_every_negative_category_is_reachable(self):
        """A category no pattern can produce is dead code pretending to be a
        check."""
        samples = {
            ABSENCE: "Kafka wasn't part of the stack at my other employers.",
            SCOPE_LIMIT: "I didn't administer the cluster myself.",
            RECALL_LIMIT: "I don't remember the exact retry configuration.",
            OWNERSHIP_DISCLAIMER: (
                "That came from the technical architect, rather than owning it."
            ),
        }
        for category, sentence in samples.items():
            report = assess("describe the system", sentence, "answered")
            self.assertTrue(
                any(n.category == category for n in report.negatives),
                f"no pattern matches the {category} sample: {sentence!r}",
            )


class TenseIsCorrect(unittest.TestCase):
    """NRG is current employment; BCBSA and Marsh are past. Live answers are
    already correct, so this is a regression guard -- and a guard nobody has
    seen go red is not a guard, hence the seeded mutation below."""

    def test_no_archived_answer_puts_nrg_in_the_past(self):
        bad = []
        for r in ANSWERED:
            report = assess(r["question"], r["answer"], r["outcome"])
            if report.tense_errors:
                bad.append(f"{r['question_id']}/{r['draw']}: {report.tense_errors}")
        self.assertFalse(bad, "NRG is current employment:\n" + "\n".join(bad))

    def test_tense_gate_catches_a_seeded_past_tense_nrg_answer(self):
        seeded = "I worked at NRG on the payments retry handler and the batch jobs."
        report = assess(
            "what are you working on at NRG right now", seeded, "answered"
        )
        self.assertTrue(
            report.tense_errors, "the tense gate did not catch past-tense NRG"
        )

    def test_tense_gate_allows_past_tense_for_a_finished_task_at_nrg(self):
        """'At NRG I built X' is correct past tense for completed work and must
        not be flagged -- otherwise the gate forbids describing work."""
        fine = "At NRG I built the retry handler and moved the batch jobs onto SQS."
        report = assess("what have you built at NRG", fine, "answered")
        self.assertFalse(report.tense_errors, f"false positive: {report.tense_errors}")


class DoesNotOverRefuse(unittest.TestCase):
    """Every existing refusal test asserts that a refusal HAPPENS; none asserts
    that a fair question is answered. Question m was refused on all three
    production draws while passing every shipped test."""

    def test_the_baseline_recorded_the_over_refusal(self):
        """History, pinned. Question m was declined on all three pre-fix draws
        while passing every shipped test."""
        refused = {
            r["question_id"]
            for r in RECORDS
            if assess(r["question"], r["answer"], r["outcome"]).over_refusal
        }
        self.assertIn(
            "m", refused,
            "the over-refusal gate no longer sees the case it was built for",
        )

    def test_a_legitimate_interview_question_is_not_refused(self):
        """Measured on the post-fix capture, not on history.

        KNOWN CAUSE if this stays red on question m: the decline is a CORPUS
        gap, not a gate defect. "Describe a technical disagreement" is a
        behavioural question, and the private books are technical -- retrieval
        genuinely finds nothing, so the model correctly declines rather than
        inventing a story. Fixing it means adding behavioural material to the
        corpus, which is the Owner's call on his own career content (the audit
        parked it as SI-19), not something to patch in the gate. Loosening the
        decline gate instead would make the system invent an anecdote about a
        disagreement that may never have happened -- far worse than a refusal.
        """
        current = ProductionAnswerQuality._current()
        refused = []
        for r in current:
            report = assess(r["question"], r["answer"], r["outcome"])
            if report.over_refusal:
                refused.append(f"{r['question_id']}/{r['draw']}: {report.over_refusal}")
        self.assertFalse(
            refused,
            "legitimate interview questions were declined:\n" + "\n".join(refused),
        )


class RecordedBaseline(unittest.TestCase):
    """The defect, as it stood before the fix, pinned down.

    These PASS, and they must keep passing: if the oracle ever stops seeing
    the defect in the archived answers, it has been broken or quietly
    loosened, and every clean result it gives afterwards would be worthless.
    """

    def test_the_archived_answers_still_show_the_defect(self):
        offenders = [
            r for r in ANSWERED
            if assess(r["question"], r["answer"], r["outcome"]).unsolicited
        ]
        self.assertGreaterEqual(
            len(offenders), 20,
            "the oracle no longer detects the defect in the archived "
            "pre-fix answers, so it can no longer be trusted on new ones",
        )

    def test_marsh_was_the_worst_question_in_the_baseline(self):
        """The audit's headline finding: 3-5 volunteered negatives per draw."""
        marsh = [
            len(assess(r["question"], r["answer"], r["outcome"]).unsolicited)
            for r in ANSWERED if r["question_id"] == "b"
        ]
        self.assertTrue(marsh, "question b missing from the baseline")
        self.assertGreaterEqual(max(marsh), 3)


class ProductionAnswerQuality(unittest.TestCase):
    """The actual bar, measured on answers generated by the FIXED prompt.

    RED until agent/testdata/si_production_answers_after.json exists. That
    file is produced by re-running the archived questions against production
    once the fix is deployed -- which is the only evidence that can settle
    whether the specification change worked. A prompt diff is not evidence.
    """

    @classmethod
    def _current(cls):
        if not AFTER_FIXTURE.exists():
            raise AssertionError(
                "UNVERIFIED: the Sprint 15 specification fix has not been "
                "measured on production.\n"
                f"  missing: {AFTER_FIXTURE}\n"
                "  produce it with: python agent/si_recapture.py\n"
                "  (deploy first -- it queries the live service)\n"
                "This test fails rather than skips on purpose: a skip reads "
                "as green in CI, and SKIPPED is not PASSED."
            )
        return json.loads(AFTER_FIXTURE.read_text(encoding="utf-8"))

    @classmethod
    def _current_answered(cls):
        return [r for r in cls._current() if r["outcome"] == "answered"]

    def test_production_answers_volunteer_no_unsolicited_negatives(self):
        """The Owner's complaint, measured. Budget: zero.

        KNOWN TENSION, raised by an independent review and recorded here
        rather than quietly resolved in whichever direction was convenient.
        This test asserts ZERO. The runtime does NOT hard-enforce zero: a
        volunteered limitation triggers one retry, and if the retry still
        carries one but is otherwise clean, standing_interview.answer() SHIPS
        it rather than refusing (see SOFT_VIOLATION and only_soft_violations).
        So the runtime can emit an answer this test rejects, and the test may
        be unsatisfiable on a draw where the model is stubborn.

        That is deliberate, and the direction matters: the test is STRICTER
        than the runtime, never looser. The alternative -- refusing whenever a
        retry still volunteers a caveat -- replaces a real, grounded, honest
        answer with "I don't have that recorded", and over-refusal is its own
        registered defect (question m, declined on all three baseline draws).
        Availability at the edge was chosen over a clean number.

        If the post-fix capture shows residual negatives, the legitimate fixes
        are a second retry or a better prompt. Loosening THIS number is not
        one of them -- it is the Owner's complaint, and it is the one thing in
        this file that must not move.

        RED when written -- 37 volunteered negatives across 21 of 57 answered
        production answers, measured by this oracle (the audit's independent
        hand count was 38 across 22). Goes green only when a post-fix capture
        exists and shows none.
        """
        offenders = []
        total = 0
        current = self._current_answered()
        for r in current:
            report = assess(r["question"], r["answer"], r["outcome"])
            if report.unsolicited:
                total += len(report.unsolicited)
                offenders.append(
                    f"  {r['question_id']}/draw {r['draw']} "
                    f"({len(report.unsolicited)}): {r['question']}\n{report.describe()}"
                )
        self.assertFalse(
            offenders,
            f"{total} unsolicited negatives across {len(offenders)} of "
            f"{len(current)} answered production answers. Nobody asked for any "
            f"of them:\n" + "\n".join(offenders),
        )

    def test_no_single_answer_carries_more_than_one_unsolicited_negative(self):
        """A softer bar reported separately, so progress stays visible while
        the zero-budget test above is still red. Marsh ran 3-5 per draw."""
        worst = []
        for r in self._current_answered():
            report = assess(r["question"], r["answer"], r["outcome"])
            if len(report.unsolicited) > 1:
                worst.append(
                    f"  {r['question_id']}/draw {r['draw']}: "
                    f"{len(report.unsolicited)} unsolicited negatives"
                )
        self.assertFalse(
            worst,
            "answers stacking multiple volunteered negatives:\n" + "\n".join(worst),
        )


if __name__ == "__main__":
    unittest.main()
