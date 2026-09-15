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

## Mutation testing, property testing — evaluated, deliberately not built this session

Per the directive's own instruction to evaluate before adopting
(Phase 24's Technology Decision Rule) and per the audit's explicit DEFER
recommendation:

- **PIT (mutation testing)**: zero `pit`/`pitest` dependency exists in
  `app/pom.xml` (confirmed via grep, not assumed). Would answer a real
  question this project doesn't currently have an answer to ("would
  existing tests actually catch a seeded defect in `ContractPlanService`
  or the Triage scenario files"), but adds a real new build-time
  dependency and CI runtime cost. Deferred, not rejected — a good
  candidate for a dedicated future session, scoped to the one or two
  highest-value classes (e.g. `ContractPlanService`, given it's already
  the site of one real historical defect).
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

V2 is not "complete." What changed this session: one real, evidenced test-
effectiveness gap closed (Triage candidate verification), one defect
class generalized into a repeatable check (link integrity), and CI gained
a first, safe (non-blocking) integration point for the selective
regression engine V1 already built. Mutation/property testing and a
structurally separate Test Architect subagent remain real, valuable,
deliberately deferred work — see `docs/ACTION_QUEUE.json` for tracking.
