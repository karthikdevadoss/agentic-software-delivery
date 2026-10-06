"""Shared claim-status vocabulary for audits in this repository.

Grounded in docs/audits/SI_AUDIT_2026-09-29.md's evidence-label legend
(VERIFIED_IN_CODE / VERIFIED_BY_RUN / VERIFIED_LIVE / UNVERIFIED). This module
adds DISHONEST (BL-123, SI audit BK-25) as a status distinct from an honest
WRONG claim or an honestly-flagged UNVERIFIED one, and gives a deterministic
way to tell them apart instead of leaving the distinction to judgment call.
"""

from enum import Enum


class ClaimStatus(Enum):
    VERIFIED_IN_CODE = "VERIFIED_IN_CODE"
    VERIFIED_BY_RUN = "VERIFIED_BY_RUN"
    VERIFIED_LIVE = "VERIFIED_LIVE"
    UNVERIFIED = "UNVERIFIED"
    WRONG = "WRONG"
    DISHONEST = "DISHONEST"


CLAIM_STATUS_DEFINITIONS = {
    ClaimStatus.VERIFIED_IN_CODE: (
        "Read in the real source at a cited commit, file and line."
    ),
    ClaimStatus.VERIFIED_BY_RUN: (
        "A real command was run in this session and its real output is quoted."
    ),
    ClaimStatus.VERIFIED_LIVE: (
        "Observed directly in a real response from the running system."
    ),
    ClaimStatus.UNVERIFIED: (
        "Stated together with the reason it could not be checked. Stays "
        "unverified; never upgraded by plausibility alone."
    ),
    ClaimStatus.WRONG: (
        "Checked and found false, but made in good faith at the time -- the "
        "author believed it, usually because the source they relied on "
        "(a doc, an earlier audit, a stale state file) had already drifted "
        "from reality without anyone yet noticing."
    ),
    ClaimStatus.DISHONEST: (
        "Checked and found false, where the author either (a) asserted "
        "verification or certainty that was never actually performed, or "
        "(b) had access to evidence contradicting the claim at the time it "
        "was made and did not disclose it. The defect is in how the claim "
        "was made, not only in whether it happens to be true -- this is what "
        "separates it from WRONG, and from UNVERIFIED, which is the honest "
        "version of 'this was not checked.'"
    ),
}


def classify_claim(asserted_as_verified, actually_checked, contradicting_evidence_known, claim_is_true):
    """Deterministically classify a claim given four real facts about it.

    asserted_as_verified: the claim's own wording claims it was checked
        (e.g. "PASSED", "verified in production"), not merely stated.
    actually_checked: a check genuinely happened (a run, a code read, a
        live observation) before the claim was made.
    contradicting_evidence_known: the author already had evidence against
        the claim at the time it was made.
    claim_is_true: the claim is actually correct.

    This is a classification helper, not a truth oracle -- the four inputs
    must themselves come from real evidence, never from a guess.
    """
    if contradicting_evidence_known:
        return ClaimStatus.DISHONEST
    if asserted_as_verified and not actually_checked:
        return ClaimStatus.DISHONEST
    if claim_is_true:
        return ClaimStatus.VERIFIED_BY_RUN if actually_checked else ClaimStatus.UNVERIFIED
    if not asserted_as_verified and not actually_checked:
        return ClaimStatus.UNVERIFIED
    return ClaimStatus.WRONG
