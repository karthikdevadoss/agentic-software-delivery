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

### 2026-09-20 — second pass (BL-034): the rework tail this project cannot yet see

Second run of the standing commitment, scoped specifically to look for
material published since the first pass that either **confirms or
challenges** this project's own two current headline findings.

**The headline finding is a CHALLENGE, not a confirmation — and it is
the most important thing this pass found.** This project's last three
retros all read the same way: nearly every item finished at 0.06–0.42×
its estimate, and the conclusion drawn each time was "the rubric is
calibrated too slow for this context." The 2026 industry telemetry says
that reading is premature, because the speed is real but the cost of it
lands *outside the sprint window*. Faros AI's 2026 data: epics completed
per developer **+66%**, task throughput **+33.7%** — alongside bugs per
developer **+54%** (versus +9% the prior year), code churn **+861%**,
incident-to-PR ratio **+242.7%**, and **31.3%** of PRs merged with no
review at all. The report attributes the churn explicitly to rework:
developers "accept AI-generated code quickly, then come back to replace
it when it proves insufficient in practice"
([Mneme HQ on the Faros 2026
data](https://mnemehq.com/insights/ai-coding-productivity-gains-rework/)).
Forrester's companion figure is the sharper one for this project:
**unmeasured rework absorbs 22–38% of self-reported time savings in
mature programs, and 50%+ in early-stage ones** ([Developer Productivity
Benchmarks
2026](https://larridin.com/developer-productivity-hub/developer-productivity-benchmarks-2026)).
By any definition this project is early-stage — four sprints old, with
zero elapsed calendar distance between any item's "done" and its retro.
**Every 0.06–0.42× ratio in this file was measured inside a window too
short for a rework tail to have appeared in it.** That does not
invalidate the ratios; it means the rubric-is-too-slow conclusion is
currently unfalsifiable, and will stay so until something measures
correction-after-done. Recorded here as a real, named limitation of this
project's own existing conclusions, not as a reason to change the rubric
again.

**Confirmation of (a), the apply-a-known-pattern vs. genuine-first-of-
its-kind split — real, but weaker than it first looked, so stated
honestly.** The same benchmarks report finds "the multiplier compresses
at higher absolute CAT levels because hard PRs benefit less from current
AI tools than easy and medium ones" (ibid.). That is the same
*directional* shape as this project's own sprint-3 finding (BL-021 at
0.73 and BL-014 at 0.82 landing inside tolerance while the eight
apply-a-known-pattern items ran 0.06–0.42×), but it is measured as an
AI-speedup multiplier by PR complexity, **not** as estimate accuracy by
work type — the source was checked directly for the stronger claim and
does not make it. So: real independent support for the rubric split
added last sprint, via a different measure; not a direct external
replication of it. Worth saying plainly rather than overclaiming a match.

**(b) The "rework ratio" gap flagged last pass now has both a concrete
definition and a live owner inside this project.** Last pass could only
name rework ratio as a missing metric with no definition attached. Two
real, usable definitions now exist: **AI code turnover at 30 days** —
healthy <12%, watch 12–18%, warning 18–25%, critical >25% — with an
**AI-vs-human rewrite ratio above 1.5× as the team-level investigation
trigger** (ibid.); and the **40-20-40 split** (40% new feature work /
20% rework / 40% maintenance) as the sustainable-distribution frame,
with the warning that "if new feature work rises while change failure
rate also rises, the team may be generating debt faster than the system
can absorb it" ([Oobeya — Engineering Metrics in the AI
Era](https://oobeya.io/blog/engineering-metrics-in-the-ai-era)). On the
owner: **`BL-029`, active in this same sprint, is exactly this work** —
its own description commits to aggregating `agent/.verify_change_evidence/*.json`
into "first-pass-yield/rework/cost metrics across runs," and cites BL-023
(last pass's research) as the reason it exists. Verified honestly at the
time of writing: BL-029 is sized, started, and in-flight in a sibling
worktree, with **no commit yet** — the connection is real and traceable,
the delivery is not yet proven. The 30-day-window definition above is the
piece BL-029's scope does *not* currently cover, since evidence JSON is
per-run and carries no later-correction linkage; flagged for whoever
picks up the follow-up, not silently added to BL-029's scope here.

**One genuinely new process idea, not previously considered here:
capacity as two independent constraints, not one.** The argument is that
an agent team is bounded by both effort/velocity *and* a token budget,
while traditional planning tracks only the first, and that token budget
functions simultaneously as a computational resource constraint and a
financial governance mechanism ([Scrum.org — From Velocity to Agent
Efficiency](https://www.scrum.org/resources/blog/velocity-agent-efficiency-evidence-based-management-ai-era);
[AI Agent Token Budget Enforcement
2026](https://waxell.ai/blog/ai-agent-token-budget-enforcement)). This
project sizes exclusively in hours. It already *captures* real token
data (the `SessionEnd` hook, the event ledger, per-fork transcripts) and
it already has a hard-won institutional reason to care — the real €40
burn incident in CLAUDE.md — but it has never once used tokens as a
*pre-sprint capacity constraint*, only as post-hoc accounting. Noted as a
real candidate for a future `_sizing_rubric` addition; deliberately not
built this pass (out of scope for a 15–25 min research item, and it needs
the Owner's judgment on whether a second sizing axis is worth the
process overhead the Phase 3 category work exists to measure).

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

---

## Sprint retro: BL-024 through BL-035 (complete)

Sprint approved 2026-09-20 (Owner: "go ahead do the next sprint
estimation and wait for my approval. Its another 4 hour session" —
scope proposed via the mandatory pre-sprint-proposal checklist, then
"okay continue and finish the next sprint. start sprint now"). 12 items
dispatched as 7 parallel worktree forks (2 items bundled per fork in 4
cases, to avoid repeating the shared-file collisions found in earlier
sprints), plus `BL-033` (PROJECT_STATE.json sync) done directly by the
parent session, last, after everything else landed.

Pre-sprint estimates (given before work started, `1a7d3d0`, 2026-09-20 16:24:27 CEST):

| Item | Size | Estimate | Confidence |
|---|---|---|---|
| BL-024: eureka-server + api-gateway tests, CI matrix | MEDIUM | 30–50 min | MEDIUM |
| BL-025: wire BL-021's real-topology tier into CI | SMALL | 20–35 min | MEDIUM |
| BL-026: Triage Lab token/cost/time to UI (ACT-011) | MEDIUM | 30–50 min | MEDIUM |
| BL-027: Playwright spec for the Customer App frontend | MEDIUM | 30–50 min | MEDIUM |
| BL-028: MCP over real Streamable HTTP (ACT-005) | MEDIUM | 30–50 min | LOW_MEDIUM |
| BL-029: aggregate verify_change.py evidence | SMALL | 20–35 min | MEDIUM |
| BL-030: direct tools.py test file (ACT-002) | SMALL | 15–25 min | HIGH |
| BL-031: fix drive-letter error message (ACT-001) | SMALL | 10–15 min | HIGH |
| BL-032: investigate JaCoCo/JDK68 (ACT-012) | SMALL | 15–25 min | MEDIUM |
| BL-033: sync docs/PROJECT_STATE.json | MEDIUM | 25–40 min | HIGH |
| BL-034: standing Scrum-process research | SMALL | 15–25 min | MEDIUM |
| BL-035: prompting-style coaching check-in | SMALL | 20–35 min | MEDIUM |

*Total estimated (serial sum of midpoints): ~347.5 min ≈ 5h48m.*

### Final actuals — all 12 items done, three real "estimation wrong" verdicts and one genuinely new finding class

| Item | Size given | Ratio (actual ÷ midpoint) | Verdict | Real evidence |
|---|---|---|---|---|
| BL-024+025 | MEDIUM+SMALL, 50–85 min combined | **0.68** (fork's own wall-clock, dispatch → `a796280`) | Estimation wrong (fast), but the closest to matching this sprint | Real tests for eureka-server (2/2, including a real Eureka-wire-protocol registration test after hitting a real library NPE with the more obvious in-process-client approach) and api-gateway (3/3, real WireMock routing + outbound-header-propagation tests, deliberately broke one to prove it wasn't vacuous). Both added to the CI matrix, closing `ACT-014`. Found and logged a genuinely new gap: the real-topology CI job is informational-only, because ACT-013's legacy-billing-system dependency has no stub in the harness — logged as `ACT-015`, not silently worked around |
| BL-026 | MEDIUM, 30–50 min | **0.59** | **Estimation wrong — the task was a duplicate.** ACT-011 was already resolved by an earlier commit (`7a29928`) that never updated the tracked docs | Verified the full real chain (reasoning_gateway → 6 web_server routes → 3 JS frontends) was already correct; the one real gap closed was test coverage for a *populated* usage dict (6 new regression tests, proven to fail first against a deliberately reverted change, then pass) |
| BL-027 | MEDIUM, 30–50 min | **0.36** | Estimation wrong (fast) | `e2e/customer-app-frontend.spec.js`, 8 real tests against the live app (9/9 with the pre-existing spec), a real timeout bug found and fixed in the suite itself (parallel workers overloading one dev Tomcat instance), observed-failure check done |
| BL-028 | MEDIUM, 30–50 min, LOW_MEDIUM confidence | **0.24** | **Estimation wrong — also a duplicate.** ACT-005 was already resolved 8 hours earlier (`1a4f35c`) by the same night's earlier work, again never marked in the tracked docs | Re-verified anyway rather than trusting the commit message: real HTTP handshake, 5 tools discovered, a real tool call and a real rejected path-traversal call, both over actual HTTP, clean process teardown using only a tracked child PID |
| BL-029 | SMALL, 20–35 min | 0.99 (total wall-clock, dispatch → real completion) — **not comparable to a clean estimate, see below** | Estimation-wrong verdict not meaningful this item — see the sprint-level finding | `agent/aggregate_evidence.py`, 19/19 tests, honest `insufficient_data` for fields the real schema doesn't carry rather than fabricated numbers |
| BL-030+031 | SMALL+SMALL, 25–40 min combined | 1.32 (total wall-clock, dispatch → real completion) — **also not comparable, same reason** | Estimation-wrong verdict not meaningful this item — see the sprint-level finding | `agent/test_tools.py`, 24/24 tests + 2 documented skips; a real escaped defect found and fixed along the way (a second Windows `Path.is_absolute()` blind spot in `search_code`'s glob guard, previously an uncaught `NotImplementedError`); the drive-letter error-message fix |
| BL-032 | SMALL, 15–25 min | (folded into BL-029's total above) | **Neither wrong, and superseded by a same-night self-correction** — see the addendum immediately below the table | **Corrected finding (real, not narrative):** the "20–50x slower / 240s timeout" read was itself a misdiagnosis from a 2000-char-truncated evidence field. Re-run against real, untruncated `mvnw test` output, the true cause is `jacoco:check`'s BUNDLE 0.80 line-coverage floor — unrelated to Mockito/JaCoCo-version/JDK speed, and identical under both 0.8.12 and 0.8.13. Worse: `app/`'s own canonical `mvnw test` is failing this exact gate TODAY, independent of anything this sprint touched (real measured coverage 0.7736, independently confirmed by the parent session). 0.8.13 was re-applied (it does fix the real version-68 crash); the coverage-floor gap is tracked separately as `ACT-016` |
| BL-033 | MEDIUM, 25–40 min | **~0.44** (approximate — done by the parent session amid other work, start boundary is fuzzy) | Estimation wrong (fast) | `docs/PROJECT_STATE.json`'s `completed_capabilities`/`missing_capabilities`/`last_verified_code_commit` were 3+ sprints stale (predated the whole microservices decomposition); synced to real, evidence-anchored current state |
| BL-034+035 | SMALL+SMALL, 35–60 min combined | **0.24** | Estimation wrong (fast) | A 2nd Scrum-research pass that genuinely challenges the prior sprint's own conclusion (see below); a real, critical prompting-style coaching entry (private repo), including a self-caught duplicate-paste finding matching the project's own €40 incident's mechanism |

**Addendum — BL-032 self-corrected after the retro was already being drafted, and this is the sprint's single most significant finding.** The `BL-029+032` fork, resuming after a very long stall (~3.4M ms of real `duration_ms`, per its own usage report), independently re-investigated its own earlier conclusion and found it wrong: the "Mockito/JaCoCo-0.8.13/JDK24 interaction" hypothesis was built on a `[-2000:]`-truncated evidence tail (`agent/triage_execution.py`'s own `output_tail = compile_output[-2000:]`) that cut off the actual `[ERROR]` line. The parent session did not accept this correction at face value either — independently re-ran both the exact failing `-Dtest` command (73s, a real, directly-read `[ERROR] ... jacoco-maven-plugin:0.8.13:check ... Coverage checks have not been met` line) and the full, unscoped `app/` suite (116s, 152/152 tests genuinely passing, real measured line coverage 827/1069 = **0.7736** read directly from `target/site/jacoco/jacoco.csv`) before accepting the correction. **Real, standing consequence: `app/`'s own canonical `cd app && .\mvnw.cmd test` command is failing on this machine today, for a reason that predates this entire sprint and is unrelated to JaCoCo version.** The fork also independently assigned a new item ID, `ACT-015`, for this finding — which collided with an unrelated `ACT-015` already assigned earlier the same sprint by `BL-024+025` (the real-topology CI job's missing billing stub); caught and renamed to `ACT-016` before merging, another real, sprint-level ID-coordination gap to note below.

**Genuinely new finding, not just "fast again":** of this sprint's 12 items, **3 turned out to be duplicates of already-completed work** (`BL-026`/`ACT-011`, `BL-028`/`ACT-005`, and `BL-030`'s `ACT-002` test file already partially existed) — all three traced to the same root cause: an earlier session's real commit (`7a29928`, `1a4f35c`) did the actual implementation work but never updated `docs/ACTION_QUEUE.json`/`docs/BACKLOG.json` to reflect it, so the pre-sprint-proposal checklist (which reads those tracked files, correctly, per its own design) had no way to know the work was already done. This is not a checklist failure — it's a durable-state-discipline failure one layer upstream, three separate times in one sprint. Each duplicate finding was still verified for real rather than trusted from the commit message alone (all three found genuine, if small, real gaps: a missing test for a populated usage dict, a stale/incorrect tracked status, an actually-untested transport path), so no time was wasted on blind trust — but the sizing itself was wrong for a reason this sprint's rubric had never previously named.

**Sprint totals:** 12 of 12 items done and proven, 0 abandoned. 1 item (`BL-032`) self-corrected after an initial wrong root-cause call, with the final, evidence-verified fix genuinely shipped (not a non-fix) — the initial "revert, don't ship" call was itself a real, if honest, mistake, corrected same night rather than left standing. 2 items (`BL-029`, `BL-030+031`) required the parent session to take over mid-task after their implementing forks stalled — covered as the sprint's own significant implementation-mistake finding below.

**Overall sprint estimate vs. actual:**
- Summed estimate (serial sum of the 12 items' midpoints): **~347.5 min ≈ 5h48m.**
- Real wall-clock (sprint-start commit `1a7d3d0`, 16:24:27 CEST, through the final correction commit `8653f53`, 17:19:46 CEST — including all 7 worktree merges, one real merge-conflict resolution, and the parent session directly finishing 2 stalled items): **55m19s.**
- Ratio: **0.159** — the fastest of 4 sprints so far in raw terms, but this number is now known to be a *blend* of two very different real effects (see the synthesized finding above and the action items below): genuine execution speed on 9 of 12 items, and one real, unplanned 2-item rescue operation that cost the parent session real, substantial extra time not visible in this single top-line ratio.

**Token/cost accounting:** real, harness-reported `subagent_tokens`/`tool_uses`/`duration_ms` exist for all 7 forks (visible in each completion notification) but were not pulled into a consolidated total here — same minor, repeated gap the last retro flagged for `aggregate_evidence.py`/BL-029's own scope to eventually close, now with a second sprint's worth of real data waiting to be aggregated. Notably, the two stalled forks (`a32e298458203bf4f`, `a79a4ba812d0da391`) show real `subagent_tokens` climbing across each stall-and-resume cycle (168k → 188k → 198k → 207k for one; 225k → 245k → 268k → 290k → 336k → 342k for the other) — a real, measurable cost of the stalling pattern itself, not just wall-clock time, worth citing directly once `aggregate_evidence.py` is extended to ingest fork-level data.

### Standing Scrum-process research — this sprint's pass (BL-034, full entry above at "second pass")

Summarizing here for the retro, real challenge to last sprint's own conclusion: 2026 industry telemetry (Faros, Forrester) shows AI-driven throughput gains commonly come with **unmeasured rework absorbing 22–38% of the reported time savings in mature programs, 50%+ in early-stage ones** — and this project's own retros have zero calendar distance between any item's "done" and its own same-day retro, meaning a rework tail (if one exists) has never had time to surface in any of the 0.06–0.82× ratios recorded so far. **The standing "our estimates are calibrated too slow" conclusion is therefore currently unfalsifiable with this project's own data, not proven** — a real, honest walk-back of confidence, not a reversal. The first-of-its-kind-vs-apply-a-pattern split (BL-021/BL-014 landing inside tolerance, everything else fast) got indirect support from the same research (AI speedup compresses at higher task complexity) but not the stronger direct claim. `BL-029`'s new `aggregate_evidence.py` is confirmed as the real, live owner of the "rework ratio" gap flagged since `BL-023` — sized, built, and already scoped to note what it still can't measure (no later-correction linkage in the evidence schema yet).

### Action items

**1. Estimation mistakes**
1. **Sprint-level.** 3 of 12 items were sized as new work but were actually duplicates of already-completed, undocumented work (see the synthesized finding above). **Action:** the mandatory pre-sprint-proposal checklist's step 4 ("real work items already sitting in `docs/ACTION_QUEUE.json`") is necessary but was shown this sprint to be insufficient on its own — it trusts the tracked file's `status` field, and that field can be wrong. **Recommended addition, pending Owner approval:** for any `ACTION_QUEUE.json` item still `open` that references a specific file/module, do a cheap real check (does the referenced capability already exist in the current repo, e.g. `git log --oneline -- <path>`) as part of sizing it, not just after the fact when a duplicate is found. Not yet applied — flagged for the Owner's decision before the next sprint, since it adds real steps to an already-detailed checklist.
2. `BL-029` and `BL-030+031`'s ratios (0.99, 1.32) are **not directly comparable** to every other item's ratio this sprint — both are contaminated by their forks stalling and the parent session taking over mid-task. Reporting them without that caveat would have looked like "two items finally landed near/inside tolerance," which would be a false, misleading read of the real cause. **Action:** when an item's actual duration includes a real process failure and recovery, the retro must say so explicitly rather than let the number stand alone — applied here; no code change needed, a documentation-discipline note for future retros.

**2. Implementation mistakes**
1. **Sprint-level, the significant one.** Two of seven forked subagents (`BL-029+032`, `BL-030+031`) stalled mid-task: each launched a real, legitimate long-running local command (a full `mvnw test` run, a JaCoCo reproduction suite), said some version of "I'll wait for this to finish," and then the agent process itself ended without ever receiving or acting on the actual completion — repeating this pattern 2–4 times per agent across `SendMessage` resumes rather than resolving it. The parent session ultimately took over both directly: inspected the worktree state, ran the same commands itself, and finished the real work. **Root cause not fully diagnosed** — plausibly a long-running foreground `Bash` call inside a subagent losing its connection to that agent's own turn/notification loop, but this is a genuine, currently-unexplained platform-level gap, not something this project's own code can fix. **Action:** when dispatching a fork whose task is expected to run a real command that legitimately takes several minutes (a full Maven test suite, a multi-instance harness), prefer `run_in_background` semantics inside that fork's own instructions (poll/monitor rather than a single long foreground call) where practical, and budget parent-session attention to check in on long-running forks rather than assuming a "completed" status notification always means real, final work — this sprint's evidence says it sometimes doesn't. Logged here as a real, sprint-level process finding; no fix is fully known yet, so this stays an operating note, not a closed item.
2. **Sprint-level, self-caught.** The parent session merged 5 of 7 forks in order but never actually ran `git merge` for 2 of them (`BL-029+032`, `BL-030+031`) — instead finishing their work directly inside the worktree and mentally treating "TaskList task marked completed" as equivalent to "merged into master," which it is not. Caught only because `BL-033`'s own PROJECT_STATE.json sync work double-checked real file presence on master and found `agent/aggregate_evidence.py` genuinely missing. **Fixed:** both branches were properly merged (one real, clean conflict in `docs/LESSONS.md`, resolved by keeping both independently-appended lessons), verified with a real test run (43/43 passing) before pushing. **Action:** after finishing work directly inside a worktree (as opposed to dispatching and later merging a fork's own commits), explicitly run `git log --oneline --all --graph` or equivalent before considering a sprint's merge phase complete — a task-tracking system marking something "done" is not evidence a git merge actually happened.
3. **The parent session's own first real root-cause call on `BL-032` was itself wrong**, and only corrected because the stalled fork independently returned and re-investigated on its own initiative, not because the parent re-checked its own conclusion. The original "Mockito/JaCoCo-0.8.13/JDK24 interaction, 20-50x slower" diagnosis was built from real `duration_ms`/`output_tail` fields in the isolated-workspace harness's own structured result dict — genuinely real data, correctly read, but from a field (`output_tail = compile_output[-2000:]`) that had already discarded the actual `[ERROR]` line before the parent session ever saw it. **This means "verify the real, structured evidence, not a narrative" — this project's own standing discipline — was followed and was still not sufficient**, because the evidence itself was truncated upstream of where it was read. **Action, applied same night:** the parent session then independently re-verified the fork's OWN correction too, directly, rather than accepting a second self-report in a row (ran the exact failing command and the full suite itself, read the real `jacoco.csv` ratio directly) — this asymmetry (verify a correction harder than the original claim, because the original claim already proved evidence-reading isn't foolproof) is itself worth carrying forward: **when re-investigating a past wrong conclusion, prefer the FULL real output over any pre-truncated/pre-summarized evidence field, every time, not just when something looks suspicious.**
4. A real ID collision: the returned `BL-029+032` fork assigned `ACT-015` to its coverage-floor finding, independently of `BL-024+025`'s fork already having claimed `ACT-015` for an unrelated finding (the real-topology CI job's missing billing stub) earlier the same sprint. Both forks worked from the same sprint-start snapshot of `docs/ACTION_QUEUE.json` and had no way to see each other's concurrent ID assignment. **Fixed:** renamed to `ACT-016` before merging. **Action:** when multiple forks may each mint a new `ACT-NNN`/`BL-NNN` ID independently and concurrently, either pre-reserve ID ranges per fork before dispatch, or treat "assigned a new tracked-item ID" as something the parent session must explicitly reconcile at merge time, same as the file-content merge itself — not merely check for JSON validity.
5. A stray test-artifact file (`agent/claude_hook_test_spool_*.jsonl`) was found uncommitted twice across two different forks' worktrees — `agent/test_claude_code_hook.py` creates a uniquely-named real spool file per test run and does not appear to always clean it up. **DONE** — the `BL-030+031` fork, resuming after this retro's own action items were already being drafted, independently found and fixed the same gap: added a `.gitignore` pattern (`agent/claude_hook_test_spool_*.jsonl`) so this class of artifact never surfaces as an untracked file again. Also worth recording: that same late resume ran the FULL `agent/` suite to completion (810 tests, ~21.5 min) and traced all 30 failures/41 errors to one real, pre-existing environmental cause (`EVENT_LEDGER_DATABASE_URL` not configured in that worktree) — stronger, independent confirmation that BL-030/031 caused zero regressions, beyond the narrower adjacent-suite check already recorded above.

**3. Neither, but still needed**
1. `ACT-015` (the real-topology CI job is informational-only because `ACT-013`'s legacy-billing-system dependency has no stub in the harness) — a real, currently open gap found by `BL-025`, correctly left open (not auto-executed, since building a 5th harness process is real new design, out of that item's SMALL scope) as a next-sprint candidate.
2. **`ACT-016`, high real priority for the Owner's attention: `app/`'s own canonical `cd app && .\mvnw.cmd test` command is failing TODAY**, independent of this sprint, independent of JaCoCo version — real measured line coverage (0.7736) has drifted below the checked-in 0.80 floor, plus a separate structural issue where any `-Dtest=`-scoped partial run can never reach a bundle-wide floor at all. This is not a new defect introduced this sprint; it's a pre-existing, live gap this sprint's investigation happened to surface. Left open, not auto-fixed (lowering the floor or adding real tests to close the gap are both real product/quality decisions, not mechanical fixes) — real options laid out in `docs/ACTION_QUEUE.json` and `docs/LESSONS.md` for the Owner to choose from.
3. `ACT-012` is now `verified` (the JaCoCo 0.8.13 bump was re-applied and independently confirmed) — closed for real this time, distinct from `ACT-016`.
4. The Scrum-process research's own genuinely new finding (rework costs may not be visible in a same-day retro window) is itself a real, open methodological question this project's calibration process has no answer for yet — not actioned this sprint (it would require either waiting real calendar time before retro-ing an item, or building a mechanism to revisit an old item's verdict later), flagged here as a real candidate for the Owner to weigh, not decided unilaterally.

Retro prepared 2026-09-20, ~17:20–18:10 CEST (extended after `BL-032` self-corrected mid-retro-write-up), within the sprint the Owner explicitly authorized and started ("start sprint now"). All 12 items plus the `BL-032` correction and the `ACT-015`/`ACT-016` ID-collision fix are merged into `master` and pushed to `origin/master`; the sprint's own real findings (3 duplicate-item discoveries, the agent-stalling pattern, the parent session's own merge omission, a wrong root-cause call caught and corrected same night with independent re-verification on both sides, a real ID collision, and a genuinely live, pre-existing `app/` build gap found along the way) are durably recorded here and cross-referenced in `docs/LESSONS.md`/`docs/ACTION_QUEUE.json` rather than left only in this retro. Two worktree directories (`agent-a32e298458203bf4f`, `agent-a79a4ba812d0da391`) remain on disk, un-removed, because their tracked agent processes still show as alive on the harness side despite their work being fully merged — flagged for manual cleanup rather than a forced process kill. Next sprint scoping awaits the Owner's discussion.

---

## Sprint retro: BL-036 + BL-037 (complete)

Sprint approved 2026-09-20 (Owner: "continue building the app as per our plan
-- finish NRG related technologies work done... Before this sprint do
estimate and then start the sprint yourself. Do not wait for me... keep
this sprint shorter. Do not spend more than 1 hour"). Scoped by reading
the private career-context repo's real, CONFIRMED (not candidate) NRG
technical stack against what already exists in this codebase — both items
existence-checked first per the just-added checklist step, both sized
using `suggest_estimate()` for real.

| Item | Size | Estimate | Confidence |
|---|---|---|---|
| BL-036: structured JSON logging across microservices | SMALL | 15–20 min | MEDIUM |
| BL-037: MapStruct DTO mapping, first use in this codebase | SMALL | 20–35 min | LOW_MEDIUM |

*Total estimated: ~45 min.*

### Final actuals

| Item | Ratio | Verdict | Real evidence |
|---|---|---|---|
| BL-036 | **0.17** | Estimation wrong (fast) — for a real, honest reason, not a sizing miss on new work | 5 of 6 services already had `logging.structured.format.console=ecs` from an earlier sprint; only `eureka-server` was missing it. Verified with real, live boot proof (real ECS JSON on stdout) for both the pre-existing config (customer-service) and the newly-added one (eureka-server) |
| BL-037 | **0.25** | Estimation wrong (fast) | Real MapStruct 1.6.3 dependency + annotation processor, first use in this codebase; real generated code inspected directly; `CustomerPreferenceResponse.from()`'s dead manual mapping deleted, not left behind; 3 new tests proven non-vacuous by deliberately breaking the mapping and confirming the right failure; full suite 46/46 passing |

**Overall sprint estimate vs. actual:**
- Summed estimate: **~45 min.**
- Real wall-clock (sprint-start commit `0d6cf48`, 18:49:53 CEST, through the last commit `0c4aa83`, 19:01:23 CEST): **11m30s.**
- Ratio: **0.256** — continuing the same directional pattern as every prior sprint; both items were genuinely "apply an already-decided pattern" work, and both landed in the same fast range that pattern has consistently shown.

### Action items

**1. Estimation mistakes**
1. BL-036's 0.17 ratio has a specific, checkable cause the existence-check step (added this same session) only partially caught: it confirmed the *technology* (structured JSON logging) wasn't a full duplicate, but didn't check *how many of the 6 services* already had it before sizing for all 6. **Action, real and cheap:** when a sprint item spans N identical targets (N services, N files), the existence-check should count how many already satisfy the requirement before pricing the item — not just confirm the requirement isn't fully met anywhere. Not yet built into `suggest_estimate()` or the checklist; flagged for the next time this shape of item comes up.

**2. Implementation mistakes**
1. **The exact `--`-inside-an-XML-comment bug already documented in `docs/LESSONS.md` (twice, from two earlier sprints this same session) was hit a THIRD time, by the same AI, in a brand-new comment written in this very sprint** (`services/customer-service/pom.xml`, "not remembered -- 1.6.3..."). Caught immediately by the real Maven parse failure, not silently — but the recurrence itself is the finding: a rule that has now been written down twice and still didn't prevent a third real occurrence is exactly the "written rules don't reliably survive real pressure" pattern named in this same session's Scrum-process cleanup. **Action:** a real, cheap STATIC-tier check (`perl -0777 -ne 'for (/<!--(.*?)-->/gs) { print "VIOLATION\n" if /--/ }' <file>`, already known-working from `docs/LESSONS.md`'s own entry) should run automatically on any `.xml`/`.pom` file touched in a diff, not be left as something to remember. Not yet built — a real, concrete next candidate for the same treatment the Scrum-cleanup gave other repeat problems.

**3. Neither, but still needed**
1. `ACT-017` (a real BCBSA-domain gap: HL7/SMART FHIR healthcare APIs have no representation in this app) found and logged, deliberately NOT started despite ~49 minutes remaining in the sprint's own 1-hour cap — genuinely first-of-its-kind/LARGE, and starting it with that little real budget risked either a rushed, unconvincing implementation or blowing the explicit time box. Left for the Owner's own scoping decision.
2. Marsh's confirmed technical stack (Eureka/Hystrix/Zuul-family service discovery) was checked too and found to be **already well-represented** by the existing microservices architecture — a real, positive confirmation, not a gap, worth recording so it isn't re-investigated later as if it were still open.

Retro prepared 2026-09-20, ~19:01–19:08 CEST, within the sprint's own 1-hour cap (used: ~19 minutes total, including this retro). Both items merged to `master` and pushed. Next sprint scoping awaits the Owner.


## Sprint 6 retro: RA-1, RA-2, BL-038, BL-056, BL-057, BL-046, BL-040, BL-039, BL-041 (DRAFT -- numbers computed 2026-09-22 night; diagnosis and action items to be done WITH the Owner when he is awake, per his instruction)

Sprint approved 2026-09-22 ~21:50 CEST by the Owner ("start... test end to end and commit and make sure the app and the ai
system in prod is deployed... dont wait for any of my approval"), unattended, single session, no Fable subagents, no
parallel agents (one sequential qa-evaluator run on opus for the security item). Branch `sprint-6/trainer-blockers-nrg-tech`.

### Estimate vs actual (computed from docs/BACKLOG.json started_at/completed_at; wall-clock, includes test/harness runs)

| Item | Size | Estimate | Actual | Ratio actual/mid | Verdict (computed) |
|---|---|---|---|---|---|
| BL-038 | MEDIUM | 60-90 min (mid 75 min) | 7.9 min | 0.11 | outside band [0.7, 1.3] |
| BL-039 | MEDIUM | 70-100 min (mid 85 min) | 9.2 min | 0.11 | outside band [0.7, 1.3] |
| BL-040 | SMALL | 25-40 min (mid 32 min) | 1.4 min | 0.04 | outside band [0.7, 1.3] |
| BL-041 | SMALL | 30-45 min (mid 38 min) | 2.1 min | 0.06 | outside band [0.7, 1.3] |
| BL-046 | LARGE | 2-3 h (mid 150 min) | 7.2 min | 0.05 | outside band [0.7, 1.3] |
| BL-056 | SMALL | 20-30 min (mid 25 min) | 0.2 min | 0.01 | outside band [0.7, 1.3] |
| BL-057 | MEDIUM | 60-90 min (mid 75 min) | 6.7 min | 0.09 | outside band [0.7, 1.3] |
| **SPRINT** | 7 sized items | mid 480 min (8.0 h) | **35 min** | **0.07** | outside band |

Retro actions RA-1 (XML-comment gate wired blocking in CI) and RA-2 (N-target existence count in the sizing checklist) were
done first, unsized per the Owner's carve-out; RA-1's gate already existed in agent/static_gate.py from a prior session but
was not in CI.

### Evidence per item (real, quoted)
- BL-038: stub tests observed failing (2/3) then 3/3; harness runs 20:03-20:10, 20:10:58-20:13:14, 20:13:14-20:15:13 UTC exit 0.
- BL-056: continue-on-error removed after the three runs; first real CI run happens on push.
- BL-057: full `mvnw test` with the 0.80 gate enforced: exit 0, 162 tests, bundle 0.9036 (was 0.7736); seeded-mutation run
  showed 'expected: 2.0' failure then pass; -Djacoco.check.skip proven on a scoped run.
- BL-046: 47/46/40/14/13 tests across services; harness with RS256 across 5 processes exit 0; qa-evaluator PASS 6/6 with
  two follow-ups done (8 stale comments, JWKS test). Two real defects found by running: PKCS#1 vs PKCS#8 key encoding from
  OpenSSL 3.5; ambiguous constructors -> @Autowired.
- BL-039: BFF test observed failing (404 x3) then 3/3; a real regression in the existing routing tests (500) caught and fixed
  with a @Primary plain RestClient.Builder; harness BFF step: partial=true, usage UNAVAILABLE for the absent metering-service,
  89 ms.
- BL-041: unit tests observed failing (ImportError) then 4/4 after correcting one wrong test expectation; real tree 8/8 PASS;
  CI step blocking.

### Observations for the joint retro (not yet verdicts)
1. Every item landed at 0.01-0.11 of its estimate midpoint -- the same direction as sprints 1-5, now on a sprint that
   included a LARGE security change and a first-of-its-kind BFF. The raw rubric bands are still human-calibrated;
   suggest_estimate() had n=0 for every combination, so nothing could correct them. This sprint adds 7 ratios to the
   history: the next sizing for (MEDIUM, MEDIUM, apply_known_pattern) and (LARGE, LOW_MEDIUM, first_of_kind) will have
   real reference classes for the first time.
2. Implementation findings worth a rule: (a) generated key material must be verified by parsing before use (the PKCS#1/#8
   slip cost one extra test cycle across four services); (b) adding a second Spring constructor needs @Autowired --
   caught by tests, cheap, but the same class of 'framework wiring assumed' mistake as the RestClient.Builder @Primary
   regression in BL-039.
3. Sprint-level: total wall-clock ~35 min for work estimated at 8 h, with three background JVM runs overlapped. The
   binding constraint was not time but the usage limit (34% used at sprint start, per Owner).
4. Post-merge CI on master (run 35780938679) was red in two jobs, neither caused by Sprint 6 code: billing-service's
   Docker-gated Redis tests were already failing on the pre-sprint 11:06 run (unmocked `LegacyBillingSystemClient` from
   ACT-013 -> 503), and the Customer app's Kafka fan-out test had a baseline race (`expected 5L but was 6L`). Both fixed
   the same night as an in-scope proactive fix (see docs/LESSONS.md, 2026-09-22 entry); verification is CI-only because
   neither test can run on the Docker-less dev machine. For the joint retro: "merged + pushed" was reported before the
   post-merge CI result was known -- the sprint's own 'CI gating' work made that gap visible.
