# Audits in this repository

A real audit (full read of claims against code/runtime evidence, like
`SI_AUDIT_2026-09-29.md`) grades every claim with one of the statuses defined
in `agent/claims_audit.py`: `VERIFIED_IN_CODE`, `VERIFIED_BY_RUN`,
`VERIFIED_LIVE`, `UNVERIFIED`, `WRONG`, or `DISHONEST`.

`DISHONEST` (added Sprint 27, BL-123) is distinct from both `WRONG` (an
honest claim later found false) and `UNVERIFIED` (honestly flagged as not
checked): it means the claim asserted verification or certainty that was
never actually performed, or was made despite already-known contradicting
evidence. See `agent/claims_audit.py`'s `CLAIM_STATUS_DEFINITIONS` for the
exact wording and `classify_claim()` for the deterministic rule, and
`agent/test_claims_audit.py` for worked fixture examples of each status.

`SI_AUDIT_2026-09-29.md` predates this status and used a four-label legend
(`VERIFIED_IN_CODE` / `VERIFIED_BY_RUN` / `VERIFIED_LIVE` / `UNVERIFIED`
only) -- it is not retroactively relabelled here. Any audit written from
Sprint 27 onward should use the full six-status vocabulary in
`agent/claims_audit.py` rather than redefining its own legend.
