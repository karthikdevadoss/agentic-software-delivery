# Testing & Verification Architecture V2

Phases 10-11 of the Base Architecture V3 directive. Builds on
`docs/TESTING_ARCHITECTURE_V1.md` (not a replacement — V1's sections A-R
remain the authoritative design for risk classification, Test Impact
Analysis, and the selective regression engine). V2's scope, per the
directive: **test effectiveness, not test count**, and an independent
Test Architect responsibility separate from implementation.

The Owner's own stated skepticism ("simple production-visible bugs
escaped") is taken seriously here — this document reports what's real
today honestly, including what's still a genuine gap, rather than
declaring V2 complete because documents exist.

## What V2 actually adds this session

**Nothing new in tooling.** This session's real contribution to test
*effectiveness* (not count) was fixing one concrete, evidenced gap the
Phase 1 audit found: Triage candidate patches were being marked
`COMPILE_VERIFIED` — sufficient for human-promotion eligibility — after
only a successful `mvnw compile`, never proving the actual regression test
passed. That is precisely a "would the test fail if the defect existed"
gap (the directive's own diagnostic question), and it's now fixed
(`agent/triage_execution.py`, commit `72dbe4d`) with a real before/after
proof: the unmodified historical pre-fix file now correctly returns
`TESTS_FAILED` instead of the old, wrongly-reassuring `COMPILE_VERIFIED`.

## Independent Test Architect / Builder / QA separation — where it already exists, where it doesn't

| Role | Exists today? | Evidence |
|---|---|---|
| Builder (implements, no self-certification authority) | Yes | `agent/execution_tools.py`'s dispatch dict structurally excludes `approve_edit`/`reject_edit` |
| QA (independently re-verifies, cannot modify source) | Yes, for Architecture V2 shadow trials | `.claude/agents/qa-evaluator.md` — a structurally separate subagent, proven via 2 real shadow trials (one seeded defect, caught with byte-exact evidence — `docs/ARCHITECTURE_V2_EVALUATION_PLAN.md`) |
| Test Architect (writes the acceptance/test contract BEFORE implementation, independent of the builder) | **Not yet a separate role in the live pipeline.** `.claude/skills/requirement-contract/SKILL.md` and `.claude/skills/test-change/SKILL.md` exist and are used, but as skills the same session invokes, not a structurally separate subagent the way `qa-evaluator` is | Honest gap — tracked here, not fabricated as done |

## Mutation testing — real defect-seeding evidence (Base Architecture V3 continuation)

Answers the directive's actual diagnostic question directly — "if the
defect exists, does the test fail?" — via manual defect seeding against
`ContractPlanService.java` (no PIT dependency added; see below for why).
Both mutations were made directly in the real file, the real focused test
classes were run against them with real `mvnw test`, and the mutation was
reverted immediately after each run (`git checkout --` confirmed clean,
zero diff, before and after).

**Mutant 1 — reintroduce the real historical AEQ-family defect**
(`if (false && currentlyActive.filter(...).isPresent())` disabling the
idempotency no-op check entirely): **KILLED**. `ContractPlanServiceTest
.enroll_whenIdenticalRequestSubmittedTwice_isIdempotentNoOp` failed, and
`TriageScenarioAIntegrationTest` failed 2 of 5 tests (it exercises the
real service end-to-end, so the mutation broke it too) — 3 real failures
across 2 test classes, from one seeded defect. This is the exact defect
this repository actually shipped once (commit `2155a8a`'s fix) — proof
the regression coverage for it is real, not decorative.

**Mutant 2 — a subtler, real `BigDecimal` gotcha** (`isSameTerms()`'s
rate comparison changed from `.compareTo(...) == 0` to `.equals(...)` —
`compareTo` treats `2.5`/`2.50` as equal, `.equals()` does not, a
well-known Java pitfall): **also KILLED**
(`enroll_whenIdenticalRequestSubmittedTwice_isIdempotentNoOp` +
`TriageScenarioAIntegrationTest`'s
`reproduceAfterApproval_withoutReset_correctlyShowsFixed_notStaleHistory`
both failed). The likely reason: these are real Spring Boot integration
tests exercising a genuine DB round-trip (not two freshly-constructed,
identically-scaled `BigDecimal` literals compared in isolation) — a
plan's rate is persisted and reloaded via JPA before the idempotency
check compares it, and Postgres/H2's column scale can differ from the
DTO's raw input scale. **No survivor found in either attempt** — both a
crude and a subtle real mutation were caught by the existing suite.

**Honest conclusion**: this specific subsystem's test coverage is
genuinely effective, not merely present — evidenced by two real, killed
mutants, not by "N tests passed." No `TEST GAP`/`WEAK ORACLE` classification
was needed since nothing survived; per the directive's own instruction
("do not chase 100% mutation score blindly... demonstrate at least one
important behavior mutation that the test suite detects"), this
satisfies the acceptance bar without further speculative mutation hunting
on this class.

**PIT was not adopted.** Manual defect seeding on the one real,
historically-relevant class already answered the concrete question this
session needed answered, at zero new build-time dependency or CI cost.
PIT remains a real, deferred candidate for broader, automated mutation
coverage across more classes than the two experiments above — genuinely
useful future work, not rejected, just not yet justified by evidence of
a gap PIT specifically (versus targeted manual seeding) would close.
- **jqwik (property-based testing)**: no dependency exists. A plausible
  candidate would be `ContractPlanService`'s idempotency invariant itself
  ("N identical enrollment requests always result in exactly 1 active
  plan," for any N) — genuinely more general than the current example-based
  test (which proves it for N=2). Deferred for the same reason: real
  value, no urgency, no evidence yet that the example-based test is
  insufficient in practice.
- **ArchUnit**: not evaluated in depth this session. A plausible fit for
  enforcing `docs/DETERMINISTIC_ENGINEERING_KERNEL.md`'s domain-coupling
  claims mechanically (e.g. "no class outside `triage/` imports
  Customer-App-specific domain types into `reasoning_gateway.py`") if a
  second domain is ever actually built — premature before that.

## CI wiring — informational only, as V1 already planned

`docs/TESTING_ARCHITECTURE_V1.md` §R explicitly deferred CI authoritative-
gate wiring, with its own stated plan: additive annotation first. This
session executed exactly that plan (`.github/workflows/ci.yml`, commit
`5976250`) — `verify_change.py --dry-run` now runs and reports its
classification on every CI run, but cannot fail the build
(`continue-on-error: true`, and `--dry-run` itself always exits 0). The
real, unconditional `mvn test -B` gate is unchanged. Promoting this from
informational to authoritative is real future work requiring its own
evidence (does the classification ever disagree with what a human would
choose?) before being trusted as a gate.

## Golden journeys / link integrity — one gap closed, one class generalized

`docs/TESTING_ARCHITECTURE_V1.md` §I recorded golden journeys as PARTIAL.
This session closed one specific instance of "a production-visible defect
a golden-journey-style check would have caught" — AEQ-022 (a broken
recruiter-facing link) — and generalized the fix beyond the one page that
broke (`e2e/link-integrity.spec.js`, commit `aa133e0`, crawling every
public route's real rendered links). This is real progress on the Owner's
stated skepticism, not a claim that golden-journey coverage is now
complete — Workbench/Triage's own *interactive* flows (not just static
link resolution) still rely on the existing per-page Playwright specs
(`e2e/learn.spec.js`, `e2e/usage.spec.js`, etc.), which remain PARTIAL per
V1's own honest accounting.

## Honest summary

V2 is not "complete." What changed across both continuation sessions: one
real, evidenced test-effectiveness gap closed (Triage candidate
verification), one defect class generalized into a repeatable check (link
integrity), CI gained a first, safe (non-blocking) integration point for
the selective regression engine V1 already built, and two real,
manually-seeded defects against `ContractPlanService` were both caught by
the existing suite (no survivors found — see the mutation testing section
above). Property testing and a structurally separate Test Architect
subagent remain real, valuable, deliberately deferred work — see
`docs/ACTION_QUEUE.json` for tracking.
