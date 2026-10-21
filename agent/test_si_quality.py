"""The Standing Interview answer-quality oracle, tested on synthetic answers.

Sprint 15 built this oracle (si_quality.assess) and proved it against an
archived capture of real production answers. That capture, and the audit it
came from, left the repository on 2026-10-21 by Owner decision: they held
private interview material and statements the Owner has since corrected. The
classes that scored that capture (fixture integrity, recorded baseline,
over-refusal on the capture, post-fix production quality) went with it; they
cannot run without the data, and a skip would read as green.

What stays is everything that proves the oracle itself works, now on short
synthetic answers written for the purpose:
  * it flags a known-bad answer and names the offending sentences,
  * it accepts a clean answer,
  * a refusal and a "have you used X? -> no" answer are not defects,
  * every negative category is reachable,
  * the NRG tense gate catches a seeded past-tense answer.
Production answers are re-scored out of band with si_recapture.py, whose
output path is gitignored.
"""

from __future__ import annotations

import unittest

from si_quality import (
    ABSENCE,
    OWNERSHIP_DISCLAIMER,
    RECALL_LIMIT,
    SCOPE_LIMIT,
    assess,
    split_sentences,
)

# A known-bad answer in the shape the Owner rejected: the work, then three
# volunteered limits nobody asked for.
KNOWN_BAD = (
    "explain your experience with Kafka",
    "I wrote the producer and consumer code for member change events. I didn't "
    "set up the brokers, and I don't remember the retry configuration. Kafka "
    "wasn't part of the stack at my other employers.",
)


class OracleIsTrustworthy(unittest.TestCase):
    """CLAUDE.md: a diagnostic must be proven to detect the known-bad case
    before its clean result is trusted. This class is that proof."""

    def test_oracle_rejects_the_known_bad_answer(self):
        report = assess(KNOWN_BAD[0], KNOWN_BAD[1], "answered")
        self.assertTrue(
            report.unsolicited,
            "the oracle found nothing wrong with an answer that volunteers three "
            "limits. A clean result from a detector that cannot detect the known "
            "defect is meaningless.",
        )

    def test_oracle_names_the_specific_sentences_not_just_a_count(self):
        """A count cannot be acted on. The report must point at the prose."""
        report = assess(KNOWN_BAD[0], KNOWN_BAD[1], "answered")
        sentences = [n.sentence for n in report.unsolicited]
        self.assertTrue(any("set up the brokers" in s for s in sentences),
                        f"expected the scope-limit sentence to be named; got {sentences}")
        self.assertTrue(any("part of the stack" in s for s in sentences),
                        f"expected the absence sentence to be named; got {sentences}")

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
        """Hardening 1. The product's own refusal line on a question that was
        never answered is not a volunteered negative."""
        report = assess("what is your salary expectation",
                        "I don't have a specific example of that to hand. Ask me "
                        "about the backend systems I've worked on.",
                        "private_topic")
        self.assertFalse(
            report.unsolicited,
            "a correct refusal was scored as a quality defect, which would push "
            f"the system toward answering what it should decline:\n{report.describe()}",
        )

    def test_a_capability_probe_may_be_answered_with_a_no(self):
        """'Have you used Terraform?' -> 'No' is the answer, not an unsolicited
        negative."""
        cases = [
            ("have you used Terraform",
             "No, I haven't used Terraform hands-on. The infrastructure I wrote "
             "there was SAM and CloudFormation templates for the Lambda functions."),
            ("have you worked with Kafka at NRG",
             "No, we didn't use Kafka at NRG. The async work there ran on SQS with "
             "dead-letter queues and some scheduled jobs."),
        ]
        for question, answer in cases:
            report = assess(question, answer, "answered")
            self.assertTrue(
                report.solicited or not report.negatives,
                f"{question!r} asks whether a technology was used; saying it was "
                f"not is the answer.\n{report.describe()}",
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
    """NRG is current employment; BCBSA and Marsh are past. A guard nobody has
    seen go red is not a guard, hence the seeded mutation below."""

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


if __name__ == "__main__":
    unittest.main()
