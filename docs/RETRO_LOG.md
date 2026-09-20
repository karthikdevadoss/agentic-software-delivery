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

| Item | Size given | Actual size | Verdict | Real evidence |
|---|---|---|---|---|
| BL-009 | MEDIUM, 15–25 min | MEDIUM | Matched — no gap | Committed together with BL-010 (`7a29928`, 06:19:33 UTC, 25m22s combined from sprint start 05:54:11 — no clean split between the two since worked sequentially before one commit); existing usage-rendering pattern reused throughout, no real surprises |
| BL-010 | SMALL, 15–20 min | SMALL | Matched — no gap | Same commit as BL-009 (see above); 12/12 new tests passing first run except one wrong test assumption (POSIX vs Windows `is_absolute()` behavior) caught and fixed immediately |
| BL-011 | SMALL, 10–15 min, MEDIUM confidence | SMALL | Matched — no gap | `1a4f35c`, 06:24:36 UTC — 5m03s isolated delta from BL-009/010's commit. Real friction that justified the MEDIUM (not HIGH) confidence: 2 real SDK API mismatches hit and fixed (3-tuple vs 2-tuple unpack, camelCase vs snake_case result attributes) — genuinely untested code path was genuinely slightly wrong, as flagged going in |
| BL-012 | MEDIUM, 20–30 min | SMALL | **Estimation wrong** — not a difficulty misjudgment, a cross-task synergy the estimate couldn't see: BL-013 (running in parallel) built the actual Playwright spec as a side effect of proving its own feature, so BL-012's real remaining work was only wiring it into `test_impact_analysis.py` + updating one outdated test + docs, not writing a spec from scratch as scoped | `87a2ef6`, 06:26:45 UTC — 2m09s isolated delta from BL-011's commit |
| BL-013 | LARGE, 45–75 min, MEDIUM confidence | MEDIUM | **Estimation wrong** — the estimate assumed a green-field build (Controller/Service/Repository/validation from scratch, per its own description), but the feature skeleton already existed from an earlier session with only the uniqueness check missing; real narrower scope, not a difficulty misjudgment | Fork's own report: ~22 min wall-clock (05:54:11→06:16:21 UTC), corroborated independently by commit `f3ecbc6` at 06:16:14 UTC (7s apart). 152/152 real `app/` tests, 0 failures (baseline 148); first-ever Playwright spec for the Customer App frontend, run for real against a locally started server |
| BL-014 | LARGE, 30–50 min, LOW confidence | **Not completed — honest partial** | **Estimation wrong** — the LOW confidence hedge correctly flagged real risk but the 30–50 min RANGE still implicitly assumed a finished, working result was achievable in that window. It wasn't: root cause (Boot 4.1.1 + micrometer-tracing 1.7.1 + Spring Cloud 2025.1.2 never auto-configures a real Brave `Tracer` — `NoopTracerAutoConfiguration` always wins, zero Brave-specific autoconfiguration class on the classpath) required real investigation depth (562k+614k tokens, 440 tool calls across two runs) no time-bounded estimate at this size would have anticipated. Real, valuable partial: 2 genuine infra gaps found and fixed (billing-service's `RestClient.Builder` bypassing `RestClientAutoConfiguration`; api-gateway missing tracing entirely). Deliberately stopped rather than improvising unverified Brave wiring — consistent with this project's own "never fabricate what was tested" rule. Left `active` in BACKLOG.json (real, unfinished work — not an Owner-driven descope) | `b496e3f`, 06:43:41 UTC. Hit its 200-turn agent limit once (562k tokens/200 tool uses/26m14s) before being resumed and continuing (further 614k tokens/240 tool uses/33m20s to reach this honest stopping point) |
| BL-015 | MEDIUM, 20–35 min, MEDIUM confidence | MEDIUM | Matched — no gap, and fast: mirrored the already-proven `BillingCustomerClient` pattern exactly, as the sizing rationale predicted | `57d3b5f`, 06:54:23 UTC — 10m42s isolated delta from BL-014's commit. 12 new tests, full billing-service suite 28/28 passing, 0 failures. **Real live proof through the gateway** (not just compiled): created a customer, enrolled a plan (€0.20/kWh), submitted 2 real meter readings (50+30 kWh), called the new endpoint → `totalKwhConsumed: 80.0, estimatedCost: 16.00` — exactly correct. One real Eureka registry-cache propagation lag hit and resolved (not a bug) |

**Sprint totals:** 6 of 7 items done and proven; 1 (BL-014) honestly concluded as a real, valuable partial rather than forced to a false "done." 4 of 7 matched their estimate; 3 were "estimation wrong" (2 favorably — BL-012/BL-013 both finished faster because of information the estimate couldn't have had at plan time; 1 unfavorably — BL-014 hit genuine unknown-unknown depth beyond what even its LOW-confidence hedge implied). Zero "implementation issues" findings traced to any single item this sprint (one real sprint-level implementation mistake did happen — see action items below).

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
