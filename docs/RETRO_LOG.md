# Retro Log

The permanent, structured store for every sprint retro under this
project's estimation-calibration loop (see `docs/BACKLOG.json`'s
`_calibration_process` block for the mechanism this file records the
history of; see `CLAUDE.md`'s "Backlog and sizing discipline" section for
how this fits the wider Scrum-for-AI adaptation). Distinct from
`docs/LESSONS.md`: LESSONS.md holds general, reusable technical gotchas;
this file holds the sizing/estimation retro history specifically —
comparison tables, verdicts, real evidence, the discussion that produced
them, and the resulting action items — for every sprint, so the pattern
across many retros is retrievable, not just each one's isolated outcome.

A "sprint" here is one sized backlog item (task or epic), start to
finish — never a fixed calendar timebox.

---

## Standing Scrum-process research (once per sprint, BL-023)

### 2026-09-20 — first pass: real external validation of this project's own findings

Real web research (not opinion) on how the wider industry is currently
adapting Scrum/estimation for AI coding agents, done as the standing
once-per-sprint commitment.

**The headline finding independently confirms tonight's own calibration
work, from an outside source**: traditional story points/velocity are
now widely recognized as broken for AI-agent work — "in 2024, a 3-point
story represented X amount of human effort, but in 2026 an AI agent can
generate the code for that same story in 4 seconds"; "when AI reduces
drafting effort to near-zero while leaving verification complexity high,
velocity becomes a vanity metric" ([dev.to — The Death of Story
Points](https://dev.to/dmitryame/the-death-of-story-points-engineering-metrics-in-the-agentic-era-2kho)).
This project independently arrived at the same conclusion tonight from
its own real data (every completed sprint-3 item ran 0.09–0.68× its
estimate) and had already moved to numeric hour-estimates + confidence
rather than story points before this research ran — real, external
confirmation the direction is right, not a new correction needed.

**Proposed replacement metrics match what this project just built,
independently, hours earlier**: "objective completion rates and cycle
time," "defect escape rate," "rework ratio"
([Scrum.org — From Velocity to Agent
Efficiency](https://www.scrum.org/resources/blog/velocity-agent-efficiency-evidence-based-management-ai-era)).
`BL-020` (this same sprint) added an `escaped_defects` field to
`verify_change.py`'s evidence JSON for exactly this reason, before this
research was run — good alignment, not a gap.

**One real idea not yet built here, worth a future sprint's
consideration**: "rework ratio" (how much of a "done" item later needed
real correction) isn't explicitly tracked yet — `BL-014`'s honest partial
and the earlier BL-007 premature-closure incident are real historical
examples that a rework-ratio metric would have captured directly. Not
built this pass (out of scope for a 15-25 min research task) — flagged
as a real candidate for a future `_calibration_process` addition.

**Process-framing finding, informational**: AWS's own prescriptive
guidance suggests "Sprint Planning" should evolve into "Intent Design"
for agent-driven work — defining roles/guardrails/fallback mechanisms
rather than scripting every decision path
([Agile Insider — Agentic AI Is Rewriting the Sprint
Lifecycle](https://medium.com/agileinsider/agentic-ai-is-rewriting-the-sprint-lifecycle-2ecd15bee4c4)).
This project's CLAUDE.md governance file already reads this way (durable
rules and guardrails, not a literal task script) — noted as validation,
not a required change.

---

## Section 1 — Learnings from wrong ESTIMATION

Root-caused, dated entries where the size/estimate itself was miscalled
(reason was NOT an execution mistake).

### 2026-09-20 — BL-007 epic-level estimate (XLARGE, 12–20h) — actual 1h22m54s

**Task:** BL-007, Microservices decomposition (whole epic).
**Estimated:** XLARGE, 12–20h, LOW confidence.
**Actual:** 1h22m54s — roughly 8–15x under the low end of the range.
**Root cause:** Two compounding gaps, found via this retro, not before:
1. The estimate conflated architectural/structural novelty (first
   Eureka+Gateway+multi-module decomposition in this codebase — genuinely
   XLARGE-shaped) with per-service business-logic novelty. Most of
   customer-service, billing-service, and notification-service's core
   logic was *ported and adapted* from already-working `app/` code, not
   designed from scratch — a categorically faster kind of work than the
   estimate implicitly assumed.
2. The estimate never modeled that 4 of the epic's 8 sub-tasks would run
   in parallel via independent subagents, collapsing what would have
   taken meaningfully longer sequentially into a 23m35s concurrent batch.
3. Underlying structural cause: `docs/BACKLOG.json`'s `_sizing_rubric`
   had (at estimate time) no hour-range guidance at all — SMALL through
   XLARGE were purely qualitative (file count, novelty, ambiguity). The
   "12–20h" figure was a freehand number with zero empirical anchor —
   BL-007 was the first XLARGE item ever completed and retro'd with real
   hours in this project, so there was no historical data to calibrate
   against in the first place.

**Fix (this retro, `_sizing_rubric` updated):** split architecture/
integration-risk sizing (drives confidence band) from per-component
effort (drives the hour range) as two separate calls, not one blended
number; require a real numeric hour estimate on every sized task, not
just epics; when a task is known to be splittable across parallel
subagents, give both a sequential-effort figure and a parallelized
wall-clock figure.

### 2026-09-20 — BL-007 item 7 (E2E integration test)

**Task:** End-to-end integration test (Eureka + Gateway + all 4 services
routed together, real smoke test).
**Estimated:** MEDIUM (original guess, "wire it up and verify").
**Actual:** LARGE (self-realized mid-epic, once the real work was done).
**Root cause:** This was the first real multi-instance Eureka+Gateway
integration test ever run in this codebase. Distributed-systems discovery
and networking failure modes (a `@LoadBalanced` bean silently hijacking
Eureka's own client; `.before(uri(...))` not actually load-balancing
without an explicit `lb()` filter; `prefer-ip-address` breaking
same-machine self-connections; a missing JWT-propagation gap) are
structurally unknown-unknowns the first time a pattern like this runs —
not something "wire it up and verify" should have assumed away.
**Process note:** per the calibration loop's rule on self-discovered
mid-sprint corrections, this was correctly NOT paused-and-re-estimated
mid-epic — work continued straight into item 8, and the gap was surfaced
only in this end-of-epic retro, exactly as the loop specifies.
**Fix (this retro, `_sizing_rubric` updated):** a task that is the FIRST
real multi-service/multi-instance integration test of its kind in this
codebase defaults to LARGE, not MEDIUM, regardless of how simple it
sounds going in.

### 2026-09-20 — BL-007 item 8 (CI wiring), partial

**Task:** Wire CI coverage for the 4 new microservices.
**Estimated:** MEDIUM. **Actual:** MEDIUM (size matched).
One of the two real bugs found here (`SecurityConfig` needing
`@ConditionalOnWebApplication` for a `WebEnvironment.NONE` test context)
was a genuine CI-only design interaction invisible on this Docker-less
dev machine — an estimation blind spot, not a mistake in how CI was
wired. (The other bug found in this same item, the lost `mvnw`
executable bit, is a separate IMPLEMENTATION finding — see Section 2.)
No rubric change from this half of the finding — the MEDIUM label still
held overall; recorded here as a documented instance of "real bugs found
does not automatically mean the size was wrong."

---

## Section 2 — Learnings from IMPLEMENTATION issues

Root-caused, dated entries where the estimate was right, but a real
execution mistake cost extra time.

### 2026-09-20 — BL-007 item 4 (billing-service build)

**Task:** Build out billing-service (ContractPlan, enrollment, Redis
lock, real REST call to customer-service).
**Estimated:** LARGE. **Actual:** LARGE (size matched — no sizing gap).
**Root cause:** A bare `src/test/resources/application.properties` was
created for the new service's tests, but this filename SHADOWS (does not
layer with) the main `application.properties` via Maven's test-classpath
ordering — silently breaking every `@SpringBootTest`'s JWT secret
resolution. A real mistake in how the test resource was laid out, not a
sizing miss: the LARGE budget already anticipated meaningful real work,
and this was found and fixed inside that same budget, not evidence the
task deserved a bigger size.
**Fix applied same night:** a profile-specific `application-test.properties`
+ `@ActiveProfiles("test")`, and the gotcha was proactively checked for
(and avoided) on the other 3 services being built in parallel — see
`docs/LESSONS.md`'s shadowed-test-properties-file entry for the full
technical writeup.

### 2026-09-20 — BL-007 item 8 (CI wiring), partial

**Task:** Wire CI coverage for the 4 new microservices.
The lost `mvnw` executable bit (git showed `100644` vs. `app/mvnw`'s
`100755` after copying the file to all 6 new services on Windows) was a
real mechanical mistake in how the files were copied, not a sizing miss
or a design gap — a plain implementation error, fixed via
`git update-index --chmod=+x` on all 6 services, verified before
committing. (The other bug in this same item, `SecurityConfig`'s missing
`@ConditionalOnWebApplication`, is the separate ESTIMATION finding above
— both are real, and are listed as two findings against the same item on
purpose, not merged into one.)

---

## Action item history

Action items produced by each retro, their approval status, and what
actually happened once approved. Action items are never sized (see
`_calibration_process` in `docs/BACKLOG.json`).

### From the 2026-09-20 BL-007 retro

1. **Fold the novelty-conflation split (architecture/integration risk vs.
   per-component effort) into `docs/BACKLOG.json`'s `_sizing_rubric`
   itself**, not just prose in LESSONS.md. — Proposed 2026-09-20,
   approved 2026-09-20, **done same day** (`_sizing_rubric` + new
   `_calibration_process` block).
2. **Add a rubric heuristic: first-of-its-kind multi-service/multi-instance
   integration defaults to LARGE, not MEDIUM.** — Proposed 2026-09-20,
   approved 2026-09-20, **done same day**.
3. **Add a rubric note: tasks splittable across parallel subagents get
   two figures (sequential + parallelized wall-clock).** — Proposed
   2026-09-20, approved 2026-09-20, **done same day**.
4. **Create this document** (BL-008) as the permanent store for all
   future retro data. — Proposed 2026-09-20, approved 2026-09-20,
   **done same day** (this file).

Additional process decisions settled in the same discussion, recorded
here since they shape every future retro (full detail: this session's
own conversation history, and the Claude-memory file
`feedback_estimation_calibration_loop.md`):
- Retro table columns: Task | Size given | Actual size | Verdict
  (Estimation wrong / Implementation issues / Matched — no gap) | Real
  evidence.
- Tolerance for "matched": actual/estimate-midpoint within ±30% to
  start, tightened over time as real variance narrows — each tightening
  gets its own dated entry in this file once there's enough data to
  justify one.
- Mid-sprint re-estimation is triggered ONLY by the Owner changing scope
  himself — never by Claude's own mid-sprint realization, which is
  simply finished as planned and surfaces in the normal end-of-sprint
  retro as an ESTIMATION WRONG finding.
- Action items themselves are never sized.
- No retroactive re-sizing of already-completed old backlog items, ever
  — only new tasks get sized with updated knowledge.

---

## Sprint retro: BL-009 through BL-015 (complete)

Sprint approved 2026-09-20 (Owner: "go ahead... lets see how this sprint
estimation and actuals come up... prepare the retro analysis and keep it
ready"). Pre-sprint estimates (given to the Owner before work started):

| Item | Size | Estimate | Confidence |
|---|---|---|---|
| BL-009: Triage Lab cost/token/time propagation | MEDIUM | 15–25 min | HIGH |
| BL-010: ACT-001+ACT-002 bundle | SMALL | 15–20 min | HIGH |
| BL-011: MCP streamable-http real test | SMALL | 10–15 min | MEDIUM |
| BL-012: Playwright spec, Customer App frontend | MEDIUM | 20–30 min | MEDIUM |
| BL-013: Update Email backend feature | LARGE | 45–75 min | MEDIUM |
| BL-014: Microservices distributed tracing | LARGE | 30–50 min | LOW |
| BL-015: Metering-to-billing integration | MEDIUM | 20–35 min | MEDIUM |

*Total estimated: ~2h35m–3h55m.*

### Final actuals — all 7 items done or honestly concluded

**CORRECTION, 2026-09-20 (found during the Scrum-process review, same day):** the verdicts below were
originally called by soft/qualitative judgment ("did anything go wrong"), not by actually computing each
item's ratio against the stated ±30% tolerance band. Recomputed precisely: **every item that actually
finished this sprint fell OUTSIDE the tolerance band, on the fast side** — including 3 previously marked
"Matched." This is corrected below rather than left standing. See the synthesized finding after the table.

| Item | Size given | Actual size | Ratio (actual ÷ estimate-midpoint) | Verdict | Real evidence |
|---|---|---|---|---|---|
| BL-009 | MEDIUM, 15–25 min | MEDIUM | 0.68 (combined w/ BL-010, see below) | **Estimation wrong** (corrected) — see synthesized finding | Committed together with BL-010 (`7a29928`, 06:19:33 UTC, 25m22s combined from sprint start 05:54:11 — no clean split between the two since worked sequentially before one commit); existing usage-rendering pattern reused throughout |
| BL-010 | SMALL, 15–20 min | SMALL | 0.68 (combined, see above) | **Estimation wrong** (corrected) — see synthesized finding | Same commit as BL-009; 12/12 new tests passing first run except one wrong test assumption (POSIX vs Windows `is_absolute()` behavior) caught and fixed immediately |
| BL-011 | SMALL, 10–15 min, MEDIUM confidence | SMALL | **0.40** | **Estimation wrong** (corrected from "Matched") — see synthesized finding | `1a4f35c`, 06:24:36 UTC — 5m03s isolated delta from BL-009/010's commit. Real friction that justified the MEDIUM (not HIGH) confidence: 2 real SDK API mismatches hit and fixed — but the task was still 2.5x faster than the range's own midpoint despite that friction |
| BL-012 | MEDIUM, 20–30 min | SMALL | **0.09** | **Estimation wrong** — cross-task synergy the estimate couldn't see: BL-013 (running in parallel) built the actual Playwright spec as a side effect of proving its own feature | `87a2ef6`, 06:26:45 UTC — 2m09s isolated delta from BL-011's commit |
| BL-013 | LARGE, 45–75 min, MEDIUM confidence | MEDIUM | **0.37** | **Estimation wrong** — the estimate assumed a green-field build, but the feature skeleton already existed from an earlier session with only the uniqueness check missing | Fork's own report: ~22 min wall-clock, corroborated by commit `f3ecbc6`. 152/152 real `app/` tests, 0 failures (baseline 148); first-ever Playwright spec for the Customer App frontend, run for real |
| BL-014 | LARGE, 30–50 min, LOW confidence | **Not completed — honest partial** | n/a — no finish to ratio against | **Estimation wrong** — LOW confidence correctly flagged real risk, but the range still implicitly assumed a finished result was achievable in that window. Root cause found (Boot 4.1.1 + micrometer-tracing 1.7.1 + Spring Cloud 2025.1.2 never auto-configures a real Brave `Tracer`), full correlation not achieved; deliberately stopped rather than improvising unverified wiring | `b496e3f`, 06:43:41 UTC. 1.18M tokens/440 tool uses across two runs (hit its 200-turn agent limit once, resumed) — real evidence of genuine unknown-unknown depth |
| BL-015 | MEDIUM, 20–35 min, MEDIUM confidence | MEDIUM | **0.39** | **Estimation wrong** (corrected from "Matched") — see synthesized finding | `57d3b5f`, 06:54:23 UTC — 10m42s isolated delta from BL-014's commit. 12 new tests, full billing-service suite 28/28 passing, 0 failures. **Real live proof through the gateway**: real customer, real plan, real meter readings → `totalKwhConsumed: 80.0, estimatedCost: 16.00`, exactly correct |

**Synthesized finding (the actual headline result of this sprint's tolerance check):** this is not five
independent surprises — it's the same root cause repeating. **Every single item that finished this sprint
ran at 0.09–0.68 of its estimate's midpoint; none landed in [0.7, 1.3].** BL-012/013/014 each have their own
additional specific reason (cross-item synergy, pre-existing skeleton, genuine unknown-unknown depth) layered
on top, but BL-009/010/011/015 have no such special-case reason — they simply ran faster than a supposedly
generous ±30% band allows, on ordinary, correctly-scoped, no-surprises work. The honest conclusion: the sizing
rubric's numeric hour ranges are still calibrated for a slower execution pace than this specific context (AI
execution + heavy reuse of already-proven patterns in a codebase Claude already knows well + real
parallelization) actually delivers, on top of BL-007's own already-identical finding. Two sprints in a row now
show the same directional bias. See the new rubric lesson below.

**Sprint totals (corrected):** 6 of 7 items done and proven; 1 (BL-014) honestly concluded as a real, valuable partial rather than forced to a false "done." **0 of 7 matched their estimate under the stated ±30% tolerance** — all 7 were "estimation wrong," 6 favorably (finished faster than estimated) and 1 unfavorably in depth-of-effort though not in elapsed time (BL-014). Zero "implementation issues" findings traced to any single item this sprint (one real sprint-level implementation mistake did happen — see action items below).

**Overall sprint estimate vs. actual (2026-09-20, corrected — the first total given in chat had a small arithmetic slip, re-added here):**
- Summed estimate: 155–250 min = **2h35m–4h10m**.
- Real actual: sprint start (05:54:11 UTC) → BL-015's commit, the last real implementation work (06:54:23 UTC) = **~1h00m**; including merge + retro write-up (07:00:25 UTC) = **~1h06m**.
- Actual came in under even the low end of the estimate, despite BL-014 not finishing. Caveat: summed-individual-duration (≈1h40m, adding each item's own real time) vs. wall-clock (≈1h00m) shows roughly 40 minutes were saved by real parallelism (2 forks running concurrently with direct work) — both numbers are real, they answer different questions (see action item 1.4 below).

**Token/cost accounting:** real, harness-reported usage exists for the 3 forked items — BL-013: 337,441 tokens / 81 tool uses / 1,258,450ms. BL-014+BL-015 combined (one fork, two runs): 1,176,970 tokens / 440 tool uses / 3,574,240ms. The parent session's own direct work has no LIVE token/time figure queryable mid-session — but this is not a real gap: `agent/claude_code_hook.py`'s `SessionEnd` hook already captures this session's own real token usage automatically from its transcript at session end, into the same event ledger (`get_dev_session_cost_summary()`, the Usage page's "Claude Code Dev Session" card) — the number exists, just not live, and not until this actual session ends. No new work needed (see action item 3.2 below).

### Action items — resolved 2026-09-20, same day, per Owner instruction ("act on all before next sprint")

**1. Estimation mistakes**
1. BL-014 lesson (LOW-confidence work may validly conclude "real partial") — folded into `docs/BACKLOG.json`'s `_calibration_process` loop. **DONE.**
2. BL-012 lesson (concurrent items' later estimate is provisional) — folded into `_calibration_process`. **DONE.**
3. BL-013 lesson (verify repo state before sizing a "build X" task) — folded into `_calibration_process`. **DONE.**
4. Sprint-level lesson (flag parallelizable items before work starts; give both summed-sequential and wall-clock figures for the WHOLE sprint, not just single epics) — folded into `_calibration_process`; CLAUDE.md's Phase 2 section updated to require the overall sprint estimate be reported every retro. **DONE.**

**2. Implementation mistakes**
1. Sprint-level: dispatched the BL-013 fork without worktree isolation while continuing direct edits in the same checkout — its `git stash` swept up concurrent BL-009/010 work too (recovered cleanly, nothing lost). Fixed going forward: used `isolation:"worktree"` for the very next fork (BL-014/015) in the same sprint, and saved as a standing rule (Claude memory `feedback_fork_git_isolation.md`). **DONE — already applied within this same sprint, no further action.**

**3. Neither, but still needed**
1. BL-014 (Brave tracing not fully wired) stays `active` in `docs/BACKLOG.json` as real, genuine follow-up work — a next-sprint candidate, not silently dropped. **DONE — already correctly left active by the fork itself; confirmed, no change needed.**
2. Investigate whether the parent session's own token usage can be captured — **investigated and resolved, no code change needed**: `agent/claude_code_hook.py`'s `SessionEnd` hook already captures this automatically into the event ledger once a session ends (see Token/cost accounting note above). The retro just needs to say so honestly instead of calling it an open gap.

Retro discussion + all action items closed 2026-09-20. Next sprint scoping begins after a full review of the Scrum process (requested separately by the Owner) — see CLAUDE.md/`docs/BACKLOG.json`'s `_calibration_process` for the current, now-updated process this next sprint will follow.

---

## Sprint retro: BL-016 through BL-023, ACT-013, AEQ-025B (complete)

Sprint approved 2026-09-20 (Owner: "We can have that prompt thing from
next sprint. so for now, start the sprint and do not expect me for next
few hours. if you are ready, go ahead."), scoped by systematically
re-deriving everything discussed since the BL-009–015 retro (the mandatory
pre-sprint-proposal checklist, `docs/BACKLOG.json`'s `_calibration_process`)
rather than from memory, per the Owner's own instruction. Also completed
in the same window: `BL-014` (real Brave tracing), a **carryover item
from the previous sprint** — its first attempt there was an honest,
deliberately-stopped partial; this sprint's work is its real completion,
not a new sprint item, so it is reported separately below and excluded
from this sprint's own estimate/actual totals.

Pre-sprint estimates (given before work started, `5c770e8`, 2026-09-20 15:02:13 CEST):

| Item | Size | Estimate | Confidence |
|---|---|---|---|
| BL-016: Apply AI-native testing governance (CLAUDE.md + qa-evaluator.md) | SMALL | 10–15 min | HIGH |
| BL-017: verify_change.py skip-accounting + fail-closed-on-execution | SMALL | 15–25 min | MEDIUM_HIGH |
| BL-018: STATIC verification tier (file-mode/shebang gate) | SMALL | 10–15 min | HIGH |
| BL-019: Outbound-request-assertion convention + real example | SMALL | 15–20 min | MEDIUM |
| BL-020: Evidence-JSON instrumentation (independent_evaluation/escaped_defects) | SMALL | 15–20 min | MEDIUM |
| BL-021: Real-topology multi-instance test tier | LARGE | 40–70 min | LOW_MEDIUM |
| BL-022: Retroactive qa-evaluator pass on BL-007/BL-013 | MEDIUM | 20–35 min | MEDIUM |
| BL-023: Standing Scrum-process research | SMALL | 15–25 min | MEDIUM |
| ACT-013: Rework billing-service into a legacy-billing facade | LARGE | 40–70 min | MEDIUM |
| AEQ-025B: App-name single source of truth | SMALL | 10–15 min | HIGH |

*Total estimated (naive serial sum of midpoints): ~250 min = 4h10m.*

### Final actuals — all 10 items done, real evidence for each

Durations verified against real `git log` commit timestamps (not
self-reported), same discipline as the BL-009–015 retro's correction.
Sequentially-executed items are measured commit-to-commit; the two items
run as isolated `worktree` forks (BL-021, ACT-013) are measured by their
own dispatch-to-own-commit wall clock, since they ran concurrently with
the sequential work, not in series with it.

| Item | Size given | Ratio (actual ÷ midpoint) | Verdict | Real evidence |
|---|---|---|---|---|
| BL-016 | SMALL, 10–15 min | **0.21** | Estimation wrong (fast) | CLAUDE.md's new "AI-characteristic defect discipline" + "every activity carries a category" sections, `.claude/agents/qa-evaluator.md` amendments — both already fully drafted by the pre-sprint research, this item only wired them in |
| BL-017 | SMALL, 15–25 min | **0.20** | Estimation wrong (fast) | `agent/verify_change.py`: `_parse_surefire_skips`, `verdict`/`verdict_reason` fields; `agent/test_verify_change.py` — 10 new tests, one caught a real self-inflicted test-isolation bug (stale surefire reports) before it shipped |
| BL-018 | SMALL, 10–15 min | **0.36** | Estimation wrong (fast) | `agent/static_gate.py` + `agent/test_static_gate.py` (6 tests) — found and fixed one real, live violation on first run (`scripts/deploy_customer_app.sh`, mode 100644 despite a real shebang) |
| BL-019 | SMALL, 15–20 min | **0.20** | Estimation wrong (fast) | 2 new tests in `BillingCustomerClientIntegrationTest` (8/8 passing) proving real per-call bearer-token propagation, not just response-code assertions; new §S convention in `docs/TESTING_ARCHITECTURE_V1.md` |
| BL-020 | SMALL, 15–20 min | **0.12** | Estimation wrong (fast) | `verify_change.py`'s `independent_evaluation`/`escaped_defects` fields + `record_independent_evaluation()`/`record_escaped_defects()`/`aggregate_evidence()`, covered by new tests |
| BL-021 | LARGE, 40–70 min, LOW_MEDIUM confidence | **0.73** | **Matched, inside ±30% tolerance — the only item this sprint that did** | `services/real-topology-tests/`: 7 real runs against real service instances, 4 real defects found and fixed in the harness itself (Eureka server/client-cache readiness race — twice, at two different points in the call graph; an unsafe port-based process-kill fallback; real port contention with a concurrently active sibling worktree), 3 consecutive clean passes at `--port-offset 10000`. Merged 2026-09-20 15:47 CEST after resolving a real `docs/TESTING_ARCHITECTURE_V1.md` §S/§S section-letter collision with BL-019 (BL-021's section relettered to §T) |
| BL-022 | MEDIUM, 20–35 min | **0.42** | Estimation wrong (fast) | Real, independent qa-evaluator pass, re-ran every suite itself rather than trusting either implementer's self-report: BL-007 PASS but surfaced ONE real, previously-unrecorded escaped defect (eureka-server + api-gateway have zero automated tests and are excluded from the CI matrix — logged as `ACT-014`); BL-013 PASS, independently reproduced 152/152 tests |
| BL-023 | SMALL, 15–25 min | **0.06*** | Estimation wrong (fast) — *caveat: real research time likely happened partly during a gap while forks ran; the commit-to-commit delta measured here is a floor, not a clean isolated duration (same caveat as BL-009/010's combined figure in the prior retro) | New "Standing Scrum-process research" section in this file — 3 real, cited external sources, all independently confirming this project's own already-made calibration decisions, plus one genuinely new idea (a "rework ratio" metric) flagged for a future sprint |
| ACT-013 | LARGE, 40–70 min | **0.41** | Estimation wrong (fast) | New `LegacyBillingSystemClient`/`Config`/`LegacyPlanPricingOutcome` (sealed)/`LegacyPlanRateResponse`; `ContractPlanService` now calls the legacy pricing client before persisting a plan; 40 total billing-service tests passing (0 failures, 0 errors, 5 skipped) |
| AEQ-025B | SMALL, 10–15 min | **0.40** | Estimation wrong (fast) | `app/.../index.html`'s `APP_NAME` constant + `applyAppName()`, 3 hardcoded text occurrences replaced with element-id targets; `AEQ-025` resolved in `docs/ACTION_QUEUE.json` |

**Carryover item completed the same window (excluded from sprint totals above):**

| Item | Size given | Ratio (actual ÷ midpoint) | Verdict | Real evidence |
|---|---|---|---|---|
| BL-014 (carryover, 2nd attempt) | LARGE, 30–50 min, LOW confidence | **0.82** | Matched, inside ±30% tolerance | Real live proof, not just compile-verified: the same `traceId` (`4144a1f7404e29cd`) appears in all 3 services' real structured logs for one real request through the gateway, correct parent/child span tree. 5 new `BraveTracingConfig.java` files (all non-eureka services). Merged 2026-09-20 15:36 CEST |

**Synthesized finding (headline result, 3rd sprint in a row showing the
same pattern):** every one of this sprint's 10 items finished faster than
its estimate's midpoint (0.06×–0.42×) — continuing the exact directional
bias the BL-007 and BL-009–015 retros both already found, now confirmed a
third time. **The one genuine exception is real signal, not noise:**
BL-021 (0.73) is the *first item in three sprints to land inside the
±30% tolerance band at all* — and it is exactly the item whose own
`size_rationale` explicitly named it "first-of-its-kind... defaults to
LARGE regardless of apparent simplicity." The carryover BL-014 (0.82,
also inside tolerance) is the same class of item for the same reason.
Read together: this project's LOW/LOW_MEDIUM-confidence sizing band for
genuinely first-of-its-kind, real-multi-process integration risk is
calibrated about right — the systematic over-estimation this project
keeps finding is concentrated in the SMALL/MEDIUM, already-scoped,
apply-a-known-pattern items, not in the LOW-confidence, genuinely novel
ones. That is a real, actionable, non-obvious distinction the rubric
should encode explicitly (see action item 1.1 below), not evidence the
whole rubric runs too high across the board.

**Sprint totals:** 10 of 10 new items done and proven, plus 1 carryover
item (BL-014) genuinely completed on its second attempt. 0 implementation
do-overs on any item (no attempt was abandoned or had to be redone from
scratch this sprint) — the one real "implementation mistake" this sprint
(BL-021's own cleanup-logic safety bug) was found and fixed by the same
task that introduced it, before merge, not discovered later as an
escaped defect.

**Overall sprint estimate vs. actual (verified via `git log` timestamps,
not self-reported):**
- Summed estimate (naive serial sum of the 10 new items' midpoints): **~250 min = 4h10m.**
- Summed-individual actual (adding each item's own real duration —
  sequential items by commit-to-commit delta, BL-021/ACT-013 by their own
  fork wall-clock): **~1h37m** (10 items; BL-014's own 32m36s carryover
  work is additional and excluded, as above).
- Real wall-clock (sprint-start commit `5c770e8`, 15:02:13 CEST, through
  this retro's own write-up and the completed BL-021 merge, `ad34eae`,
  15:49:23 CEST — including all 3 worktree merges, one real merge-conflict
  resolution, and durably recording the process-kill incident): **47m10s.**
- Real parallelism (3 concurrent worktree forks — BL-021, ACT-013, and
  BL-014's carryover work — running alongside sequential direct work)
  saved roughly **50 minutes** of wall-clock time versus the
  summed-individual total, on top of the summed-individual total already
  running at 0.39× the naive serial estimate. Both effects are real and
  independent, same as the BL-009–015 retro's own finding.

**Token/cost accounting:** real, harness-reported figures exist for the
`ACT-013` and `BL-021` forks (each fork's own transcript under
`<session>/subagents/*.jsonl`) but were not pulled into this retro's
figures above — flagged as a real, minor gap for next retro to close by
reading those transcripts directly, rather than presented as a false
zero here. The parent session's own direct-work token usage is captured
automatically at session end by `agent/claude_code_hook.py`'s
`SessionEnd` hook (same mechanism confirmed in the BL-009–015 retro) —
no new gap.

### Action items

**1. Estimation mistakes**
1. **Sprint-level.** For the 3rd consecutive sprint, nearly every item
   finished well under its estimate — but this sprint's data draws a
   sharper, more actionable line than the last two retros could: items
   whose `size_rationale` cites genuine first-of-its-kind/real-multi-
   process integration risk (BL-021, BL-014) landed inside tolerance
   (0.73, 0.82); every item whose real work was "wire in/apply an
   already-decided pattern" (the other 8) landed at 0.06–0.42. **Action:**
   `docs/BACKLOG.json`'s `_sizing_rubric`/`_calibration_process` should
   distinguish these two cases explicitly going forward — a LOW/
   LOW_MEDIUM-confidence item earns its current wide band on its own
   merits, but a HIGH/MEDIUM-confidence SMALL item whose description is
   "apply already-fully-specified content" (as BL-016/BL-020 were,
   both pre-drafted by the same session's own earlier research) should be
   sized toward the rubric's own floor, not its normal SMALL default.
   **DONE** — folded into `_calibration_process` at the same time as this
   retro (see `docs/BACKLOG.json`).
2. BL-023's real research time was not cleanly isolable from a
   concurrent fork-waiting gap, so its 0.06 ratio is a floor, not a
   clean measurement — same caveat class as BL-009/010's combined figure
   last sprint. **Action:** when a sequential item's work plausibly
   overlaps with waiting on a concurrent fork, note that explicitly in
   the item's own `actual_note` at completion time, not only reconstructed
   after the fact during the retro. **DONE** — noted here; applied
   going forward via this retro's own documented pattern, no code change
   needed.

**2. Implementation mistakes**
1. **Sprint-level, the significant one.** BL-021's first cleanup design
   had a real safety bug: a port-based "kill whatever is listening on my
   target port" fallback force-killed a concurrently-running sibling
   worktree's (BL-014's) live, unrelated service processes, because
   `git worktree` isolates git state but not the shared machine's process
   table or default ports — confirmed as the root cause of BL-014's own,
   separately-reported "eureka-server/api-gateway repeatedly died
   mid-test" gotcha, only connected causally during this retro. Found and
   fixed by BL-021's own task before merge (proven-descendant-only
   process killing via a PowerShell CIM tree walk, plus a `--port-offset`
   option so concurrent worktrees never need to contend for the same
   ports at all) — no data was lost, no test result was corrupted, but it
   could have been worse with a longer-running concurrent task. **DONE**
   — durably recorded in `docs/LESSONS.md`, cross-referenced in BL-014's
   own `actual_note`, and folded into Claude's own memory
   (`feedback_fork_git_isolation.md`) as a standing rule for any future
   task that starts real multi-process services inside a worktree fork.
2. Dispatched a qa-evaluator-intended review task via the Agent tool
   without setting `subagent_type: "qa-evaluator"` explicitly (prompt
   text alone doesn't confer the real `disallowedTools` restriction).
   Caught immediately, reinforced via message, no bad write happened.
   **DONE** — logged to Claude memory the same session, no further
   action.

**3. Neither, but still needed**
1. BL-019 and BL-021 independently added same-lettered "§S" sections to
   `docs/TESTING_ARCHITECTURE_V1.md` — two parallel workstreams both
   appending to the end of the same shared doc in the same sprint with no
   coordination, producing a real merge conflict this session resolved by
   hand (BL-021's section relettered to §T, content otherwise unchanged).
   **DONE** — resolved and merged. **Future rule worth trying next
   sprint:** when 2+ parallel forks are each expected to append a new
   lettered/numbered section to the same shared doc, either pre-assign
   the letter/number before dispatch or anchor each addition to a unique
   heading name rather than a shared incrementing scheme.
2. `ACT-014` (eureka-server/api-gateway: zero automated tests, excluded
   from the CI matrix) — a real, currently open, sizeable gap found by
   BL-022's retroactive review. Correctly left `open` (not auto-executed)
   in `docs/ACTION_QUEUE.json` as the natural next-sprint candidate, per
   this project's own proactive-action-policy boundary (architecture-
   adjacent, needs its own sizing).
3. BL-021's real-topology harness is real, repeatable, and proven (3
   consecutive clean passes) but deliberately not wired into
   `.github/workflows/ci.yml` yet — same reasoning as BL-007's own
   original CI-wiring deferral (§R). Left as an explicit, tracked-not-
   forgotten open item for a future task to decide, not auto-executed
   here.

Retro prepared 2026-09-20, 15:49–15:57 CEST, entirely within the sprint
the Owner explicitly authorized unattended ("do not expect me for next
few hours"). All 10 sprint items plus the BL-014 carryover are merged
into `master` and pushed to `origin/master`; the sprint's own real
process-kill incident and merge-conflict resolution are durably recorded
(`docs/LESSONS.md`, `docs/BACKLOG.json`, Claude memory) rather than left
only in this retro. Next sprint scoping awaits the Owner's return.
