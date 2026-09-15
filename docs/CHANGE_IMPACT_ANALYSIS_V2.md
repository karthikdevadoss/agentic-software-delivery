# Change Impact Analysis V2

Base Architecture V3 Section 8. Real evidence, not a theoretical
redesign: compared the current path-rule-based Test Impact Analysis
(`agent/test_impact_analysis.py`) selection for a real change against
what Section 7's real symbol/caller analysis (`docs/
CODE_INTELLIGENCE_EVALUATION.md`) independently found — and it disagreed.

## The real comparison

**Real change**: `app/src/main/java/com/example/customer/service/
ContractPlanService.java` + its unit test.

**TIA's selection before this session**: `["ContractPlanServiceTest",
"ContractPlanControllerIntegrationTest"]` — confirmed via a real run of
`verify_change.build_plan()` against this exact diff.

**What Section 7's real grep-based caller analysis independently found**:
`TriageScenarioAService`'s "fixed" enrollment path calls
`ContractPlanService.enroll()` directly — a real, verified caller TIA's
hand-maintained table did not include.

**Was this a real gap, or just a theoretical one?** Real: Section 4's
mutation testing already proved `TriageScenarioAIntegrationTest`
independently detects defects in `ContractPlanService` (both seeded
mutants caused real failures there, not just in the two tests TIA was
already selecting). A change to this file that somehow passed
`ContractPlanServiceTest` but broke the Triage-specific path would have
received a *narrower* real-world test selection than the file's actual
blast radius warranted, in the selective (non-fail-closed) regression
path `verify_change.py` uses locally and in CI.

## The fix

Added `TriageScenarioAIntegrationTest` to `agent/test_impact_analysis.py`'s
`ContractPlan.java`/`ContractPlanService.java`/`ContractPlanStatus.java`
entries. Re-ran the exact same real diff through `verify_change.
build_plan()`: selection is now `["ContractPlanControllerIntegrationTest",
"ContractPlanServiceTest", "TriageScenarioAIntegrationTest"]`. Full
`agent/test_test_impact_analysis.py` suite (15/15) and the newly added
`agent/test_capability_boundaries.py`/`test_reasoning_gateway*`/`test_main`
suites (37/37 combined) re-run clean.

## Honest conclusion for Section 8's actual question

**"Does deterministic symbol/dependency intelligence improve TIA?" —
yes, demonstrated on one real change, not hypothetically.** The
improvement did not require adopting a new tool (Section 7 already
concluded grep suffices at this codebase's scale) — it required actually
*using* grep-based caller analysis to audit TIA's hand-maintained table
against reality, which found and fixed a real, if narrow, coverage gap.
This is the same lesson as Section 7's evaluation, applied: the
deterministic *capability* (accurate caller analysis) already exists in
this codebase's tooling; what was missing was applying it to validate
TIA's own table, not a more sophisticated analysis engine. **Fail-closed
behavior is unchanged** (a fail-closed diff still runs the full suite
regardless of this table) — this only improves the selective-path case.

**Not done, and why**: a systematic audit of every one of `agent/
test_impact_analysis.py`'s ~40 file→test mappings against real grep-based
caller analysis, which would be the thorough version of this exercise.
Scoped to the one file this session's other work already had deep,
verified context on, rather than a broad sweep with less individual
scrutiny per entry — a good candidate for a dedicated future session.
