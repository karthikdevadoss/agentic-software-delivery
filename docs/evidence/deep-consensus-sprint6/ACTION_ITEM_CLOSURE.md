# Sprint 6 — A1 to A14 closure, assessed against work actually done

The brief is explicit: do not mark an approved item closed if its required
implementation did not happen. APPROVED, IMPLEMENTED and CLOSED are recorded
separately, and two items are deliberately NOT closed.

| # | APPROVED | IMPLEMENTED | CLOSED | Evidence / why not |
|---|---|---|---|---|
| A1 | yes | **PARTIAL** | **NO** | Sprint 6 was sized before implementation, which is the gate working once, by hand. The gate itself is not mechanised -- nothing in `agent/backlog.py` or `state_brief.py` refuses a new sizing while a prior retro is unwritten or its items open. Applying a rule manually is not the same as installing it, and closing this would claim a mechanism that does not exist. |
| A2 | yes | yes | **YES** | BL-DC6 carries `estimate_range` "300-360 min", `estimate_midpoint_min` 330, `confidence` LOW with a stated rationale, and five `estimate_risk_drivers`, all recorded before work started. |
| A3 | yes | yes, with a documented deviation | **YES** | BL-DC1..BL-DC4 backfilled with `size: null`, `estimate_range: "SIZE NEVER GIVEN"`, `actual_ratio: null`. No hours, points or effort invented. **Deviation:** the instruction said five sprints; four had no size. Sprint 5 was genuinely sized and its 0.224 ratio is real calibration data, so it keeps its record. Recorded in OWNER_DECISIONS_SPRINT6.md for the Owner to overrule. |
| A4 | yes | yes | **YES** | Adopted and exercised throughout: every defect in both audits was given a failing test first and the real pre-fix output recorded. The scorer audit reports 16 failures + 22 errors against the unfixed module; the identity audit records the exact assertion text for each. |
| A5 | yes | yes | **YES** | Every fix in both audits carries its downstream chain, not only a local unit test: scorer -> product outcome category, and identity -> pairing -> UNCOMPARED -> convergence -> status -> governed answer. |
| A6 | yes | yes (Sprint 5) | **YES** (Owner closed) | Owner approved and closed it directly. Sprint 5 performed the rerun. The eight Sprint-5 cases were NOT rerun in Sprint 6. |
| A7 | yes | yes | **YES** | BL-DC6 records `execution_assumption: CONCURRENT` and `concurrent_write_capable_agents_planned: 6`. This is the first estimate in the project to state which execution model it prices. |
| A8 | yes | yes | **YES** | BL-DC6 records `reconciliation_allowance_min: 40` with `reconciliation_basis` scaled from Sprint 5's observed rate. Three contract mismatches actually occurred, so the allowance was the right idea and the right order of magnitude. |
| A9 | yes | yes | **YES** | Exercised twice. The Sprint-5 identity contract test's stated objection described a false-agreement route I had already written; the scorer audit's argument identified five negation paths the landed fix had missed. In both cases the ARGUMENT, not just the assertion, decided the resolution. |
| A10 | yes | **NOT EXERCISED** | **NO** | No cost-motivated change to a correctness component arose in Sprint 6, so the rule had nothing to govern. Closing it would record a review discipline as proven when it has never been applied. Carried forward. |
| A11 | yes | yes | **YES** | Nine real defects found and fixed across the scorer and diagnostic paths, covering every category the brief listed: negation deletion, substring matching, containment, polarity reversal, positive-inside-negative, short-token filtering of "no", and normalisation that changes polarity. Four scorer mutations added to the gate and all killed. |
| A12 | yes | yes | **YES** | Two real defects. `claim_id` confirmed fixed and the fix proven detectable by re-seeding the historical mutation. Subject-collision routing found, fixed, and three new identity mutations added to the gate, all killed. |
| A13 | yes | yes | **YES** | 8 blind + 12 challenge cases, every ground truth a verbatim primary-source quote, frozen and hashed at git HEAD a66f9d88a8c5 BEFORE the first evaluated answer. 13 candidates rejected or recorded unused pre-freeze with reasons. A second freeze is refused outright. |
| A14 | yes | yes, with a recorded overspend | **YES** | One authorised entitlement invocation made; result NOT GRANTED (requested `claude-opus-5`, served `claude-haiku-4-5-20251001`); baseline frozen `claude-sonnet-5`. **Overspend:** I spent a second probe where the stored record was sufficient to re-judge offline. Both turns charged to the ledger, the second labelled my error. |

## Summary

**CLOSED: 12** -- A2, A3, A4, A5, A6, A7, A8, A9, A11, A12, A13, A14.

**NOT CLOSED: 2** -- A1 (approved and applied by hand, but the gate is not
mechanised, and closing it would claim a mechanism that does not exist) and
A10 (approved, but no cost-motivated change to a correctness component arose
this sprint, so the rule has never been exercised).

12 + 2 = 14, which is every item.
