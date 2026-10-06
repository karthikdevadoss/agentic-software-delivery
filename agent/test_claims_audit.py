import unittest

from claims_audit import ClaimStatus, CLAIM_STATUS_DEFINITIONS, classify_claim


class TestClaimStatusDefinitions(unittest.TestCase):
    def test_all_statuses_have_a_definition(self):
        for status in ClaimStatus:
            self.assertIn(status, CLAIM_STATUS_DEFINITIONS)
            self.assertTrue(CLAIM_STATUS_DEFINITIONS[status])

    def test_dishonest_is_distinct_from_wrong_and_unverified(self):
        dishonest = CLAIM_STATUS_DEFINITIONS[ClaimStatus.DISHONEST]
        wrong = CLAIM_STATUS_DEFINITIONS[ClaimStatus.WRONG]
        unverified = CLAIM_STATUS_DEFINITIONS[ClaimStatus.UNVERIFIED]
        self.assertNotEqual(dishonest, wrong)
        self.assertNotEqual(dishonest, unverified)


class TestClassifyClaim(unittest.TestCase):
    def test_honest_mistake_is_wrong_not_dishonest(self):
        # "PASSED locally" claim made after a real local run, which turns
        # out to be false in production -- an honest claim, later proven false.
        status = classify_claim(
            asserted_as_verified=True,
            actually_checked=True,
            contradicting_evidence_known=False,
            claim_is_true=False,
        )
        self.assertEqual(status, ClaimStatus.WRONG)

    def test_honestly_flagged_unverified(self):
        status = classify_claim(
            asserted_as_verified=False,
            actually_checked=False,
            contradicting_evidence_known=False,
            claim_is_true=False,
        )
        self.assertEqual(status, ClaimStatus.UNVERIFIED)

    def test_fixture_claiming_production_evidence_from_a_local_pass_is_dishonest(self):
        # Grounded in sprint-process.md Phase 2b's named real habit this
        # project explicitly warns against: "recording a local result as
        # production evidence is itself one of the habits this ledger
        # exists to catch." A claim worded as "verified in production"
        # that was never actually run against production is DISHONEST
        # regardless of whether the underlying change happens to work --
        # the defect is asserting verification that did not happen.
        status = classify_claim(
            asserted_as_verified=True,
            actually_checked=False,
            contradicting_evidence_known=False,
            claim_is_true=True,
        )
        self.assertEqual(status, ClaimStatus.DISHONEST)

    def test_fixture_claim_made_despite_known_contradicting_evidence_is_dishonest(self):
        status = classify_claim(
            asserted_as_verified=True,
            actually_checked=True,
            contradicting_evidence_known=True,
            claim_is_true=False,
        )
        self.assertEqual(status, ClaimStatus.DISHONEST)

    def test_genuinely_verified_true_claim(self):
        status = classify_claim(
            asserted_as_verified=True,
            actually_checked=True,
            contradicting_evidence_known=False,
            claim_is_true=True,
        )
        self.assertEqual(status, ClaimStatus.VERIFIED_BY_RUN)


if __name__ == "__main__":
    unittest.main()
