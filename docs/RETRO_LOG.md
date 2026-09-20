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

## Sprint retro: BL-009 through BL-015 (in progress)

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

*Total estimated: ~2h35m–3h55m. Actuals + verdicts + evidence to be
filled in below once the sprint completes, per the same table structure
as BL-007's retro above.*
