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


## Sprint 9 — retro write-backs, SI deploy, Books 01–04 titles (2026-09-27) — CLOSED, one item incomplete

### Scope, as the Owner pre-approved it

> "1) Apply any Sprint 8 retro action items that MUST be done before deploy…
> 2) Deploy Standing Interview to production with private corpus. 3) Unfreeze
> Books 01–04 ONLY for two titles… Size items with backlog.py. If
> suggest-estimate n=0, write 'no reliable estimate' and still proceed — do not
> invent hours from the rubric and call them an estimate."

Three items, all sized before work, owner pre-approved so no second start gate.

### Sizes given, before any work

| Item | Size | Estimate | Confidence | Pattern | suggest-estimate |
|---|---|---|---|---|---|
| BL-081 retro write-backs | SMALL | 3–4 min (mid 3.2) | MEDIUM | apply_known_pattern | **COMPUTED** n=4, median_ratio 0.16 — adopted |
| BL-082 deploy SI | MEDIUM | **NO RELIABLE ESTIMATE** | LOW_MEDIUM | first_of_kind | **INSUFFICIENT_HISTORY** n=1 — no hours recorded, per the new rule |
| BL-083 Books 01–04 titles | SMALL | 2–4 min (mid 2.4) | MEDIUM | apply_known_pattern | **COMPUTED** n=4, median_ratio 0.16 — adopted |

BL-082 is the first item in this project's history sized with **no hour range at
all**. That is the Sprint 8 action item working as designed.

### Final actuals

| Item | Size | Estimate (mid) | Actual | Ratio | Verdict |
|---|---|---|---|---|---|
| BL-081 | SMALL | 3.2 min | **~6 min** | **1.9** | outside band [0.7, 1.3] — **ABOVE** |
| BL-083 | SMALL | 2.4 min | **~8 min** | **3.3** | outside band — **ABOVE** |
| BL-082 | MEDIUM | *no estimate* | **~85 min, INCOMPLETE** | n/a | cannot be scored |
| **SPRINT** | 3 items | 5.6 min scoreable | ~14 min scoreable + 85 min unscoreable | — | mixed |

### Diagnosis — ESTIMATION WRONG, and for the first time in the OTHER direction

Both scoreable items landed **above** the band. Every item in sprints 1–8 came in
**below**. That is a genuine reversal and it has a real cause: I adopted the
COMPUTED suggestion, and the engine's ratio history (median 0.16) is built from
sprints where the work was over-estimated. Feeding a 0.16 multiplier into a
correctly-sized task over-corrects.

So Sprint 8's proposed fix — *apply the residual bias as a second factor inside
`suggest_estimate`* — would have made this sprint **worse**, not better. It is
now recorded as a rejected hypothesis rather than a pending improvement. Two
sprints of data now say the engine oscillates rather than converges: 0.30 under
in Sprint 8, 1.9 and 3.3 over in Sprint 9.

Running total: **2 of 39 items inside the ±30% band.**

There is no IMPLEMENTATION ISSUES verdict for BL-081 or BL-083. Both landed,
verified, pushed, no rework.

**BL-082 is a genuine IMPLEMENTATION ISSUE**, and the honest classification is a
wrong architectural assumption, not slow execution. See below.

### The incomplete item, stated plainly

Standing Interview is **NOT live**. Local replay passed 3/3 before each deploy.
Two production deploys shipped without the corpus. Production reports
`{"loaded":false,"chunks":0}`, the page returns HTTP 200 and says the knowledge
base is not loaded, and the nav entry stays hidden.

The fail-closed design is the one thing that went right: nothing is
misrepresented on a public surface, and I did not have to remember to check —
the mechanism enforced it.

**Attempt 1 root cause, my error.** Option C was built on the belief that
`railway up` uploads gitignored files. I inferred that from
`deploy_customer_app.sh`'s note that it "does not include the .git folder" — a
statement about `.git`, not about ignored files. Railway respects `.gitignore`.

**Attempt 2** added `.railwayignore` (verbatim `.gitignore` minus exactly the one
corpus line, 35 → 34 active patterns), with two tests guarding the real hazard
that Railway uses that file *instead of* `.gitignore` and would otherwise start
uploading `.env`. Both guards proved capable of failing. It still shipped empty.
`.dockerignore` has no matching pattern either, so the corpus is not reaching
Railway's upload at all.

Remaining hypothesis: this service builds from the connected GitHub repository
rather than the uploaded working directory — in which case a gitignored file can
**never** ship by this route and option C needs a different mechanism.

I stopped rather than trying a third variation. Each cycle costs a ~10 minute
corpus rebuild plus a container build, and every remaining candidate changes
either the security boundary or infrastructure configuration.

### Action items

**(1) Estimation-mistake improvements**

- **Withdraw Sprint 8's residual-bias proposal.** It would have amplified this
  sprint's error. Record it as tested-and-rejected in
  `_calibration_process` so it is not re-proposed from the Sprint 8 retro text.
- **Two sprints of oscillation is now the signal, not the noise.** 0.30 under,
  then 1.9 and 3.3 over. The mechanism is not converging, and a third
  adjustment aimed at the mean would be curve-fitting to four data points. The
  defensible next move is what the Architecture V1 dossier already recommended
  and nobody has acted on: stop using advance prediction as a control and use
  adaptive guardrails instead.
- **"No reliable estimate" worked and should stay.** BL-082 ran 85 minutes
  against no predicted number, and nothing was lost by not having invented one —
  whereas BL-079's fabricated 5–8h band actively misled planning last sprint.

**(2) Implementation-mistake improvements**

- **Verify an infrastructure assumption against the tool, not against a comment
  about the tool.** The entire option-C mechanism rested on one inferred
  sentence. A five-minute check — deploy one throwaway gitignored file and look
  for it in the container — would have invalidated the design before any of it
  was built. **New rule: any delivery mechanism that depends on what a build
  tool includes gets a one-file probe before the feature is built on it.**
- **`cmd | tail` masked a killed process as success.** Already written to
  `LESSONS.md` this sprint; it recurred here and cost a full wasted cycle,
  because the corpus appeared rebuilt when it was two hours stale. Caught only
  by comparing output mtime against input mtime.
- **Two duplicate build processes competed for memory** (4.8 GB + 1.2 GB, 87%
  load, <2 GiB free) after earlier timeouts left them running. Killing them
  restored 7.7 GiB. A long-running local build should check for an existing
  instance before starting.

**(3) Neither, but still needed**

- **A vacuous test was found and replaced.** With all six frozen books now
  carrying an authorised correction, the "these four must be byte-identical"
  test was checking zero books — green and incapable of failing. Replaced with
  "every frozen book is either untouched or a declared correction with a
  recorded reason", proved capable of failing by seeding undeclared drift. Worth
  generalising: an exemption list that grows can silently empty the test it
  guards.
- **SPRINT AS A WHOLE:** the two small, well-understood items went fine and were
  over-estimated; the one item with an unvalidated external dependency consumed
  six times their combined effort and did not finish. The pattern across Sprints
  8 and 9 is consistent — effort is not driven by code volume but by how many
  assumptions about *someone else's system* are load-bearing and unverified.
  That, not size labels, is what a useful estimate would have to capture.

### Carried forward

- **BL-082 remains `active` and NOT complete** — awaiting an Owner decision on
  the corpus delivery mechanism.
- BL-080 (access gate, notification) still `planned`, untouched.
- ACT-019 open: triage the SI review queue (2 rows) before the next sprint.

## Sprint 8 — Standing Interview v0 (2026-09-27) — CLOSED

### Scope, as the Owner approved it

> "1. Corpus deploy: C — Private books are delivered to the container at deploy
> time (Railway volume or private fetch — you pick the smallest option that
> works). Public repo must contain ZERO book text. Do not weaken
> ask_codebase.py's outside-repo guarantee. SI must use its own isolated corpus
> path… SI MAY go in the live nav only if the production page can actually
> answer. 2. Books 5 and 6: YES, unfreeze and re-hash for the owner packet only…
> 3. …Mark that May-2026 'supersedes present' sentence SUPERSEDED. Keep the old
> sentence visible as a withdrawn claim. 4. Start the sprint — Implement only
> BL-078 and BL-079 as scoped. BL-080 stays planned."

Two items in sprint. BL-080 (access gate + notification) remained `planned` and
was not started.

### Sizes given, before any work

| Item | Size | Estimate | Confidence | Pattern | suggest-estimate |
|---|---|---|---|---|---|
| BL-078 | MEDIUM | 18–30 min (mid 23.4) | MEDIUM | apply_known_pattern | **COMPUTED**, n=5, median_ratio 0.39 — suggestion ADOPTED over a raw 45–75 min instinct |
| BL-079 | LARGE → **XLARGE** | 3–5 h → **5–8 h** (mid 390) | LOW_MEDIUM | first_of_kind | **INSUFFICIENT_HISTORY** n=2, then n=0 after re-size; fallback to the raw rubric band |

BL-079 was re-sized **before** implementation, not after: the original LARGE
assumed the corpus was already reachable in production. It is not — the root
`Dockerfile` does `COPY . .` over the public repo only. Option C added a
genuinely novel deploy-data path, so the size moved. `deviated_from_suggestion:
false` on both.

### Final actuals — real timestamps, not recollection

| Item | Size | Estimate (mid) | Actual | Ratio | Verdict |
|---|---|---|---|---|---|
| BL-078 | MEDIUM | 23.4 min | **7 min** (15:18:51 backlog activated → 15:25:48 commit `fe9484c`) | **0.30** | outside band [0.7, 1.3] |
| BL-079 | XLARGE | 390 min | **~32 min** (15:25:48 → ~15:58) | **0.08** | outside band |
| **SPRINT** | 2 items | **413 min (6.9 h)** | **~39 min** | **0.09** | outside band |

Evidence: `docs/BACKLOG.json` mtime 15:18:51 (both items set `active`), private
commit `fe9484c` at 15:25:48, last sprint artifact
`scripts/deploy_platform_with_si_corpus.sh` at 15:52:08, plus the final 581-test
suite run. Deliverables: private `fe9484c`, public `224676a` → merged `1b564a9`.

### Diagnosis — ESTIMATION WRONG

Not implementation issues. Both items landed, verified, pushed, CI-green, with
no rework and no scope cut. The gap is entirely in prediction, and it is the
**seventh consecutive sprint** to miss low. Running total: **2 of 36 items inside
the ±30% band.**

The new and more interesting datum is BL-078. Sprint 6's named failure was
silently overriding a COMPUTED suggestion; this sprint I adopted it, which moved
the ratio from 0.12 (against my raw 60-min midpoint) to 0.30 (against the
computed 23.4). **The engine is directionally right and still magnitudinally
short by roughly 3x.** Adopting it was correct and insufficient. That is a
finding about the calibration mechanism itself, not about this sprint's
discipline.

BL-079's 0.08 is the more honest signal about XLARGE: the rubric band for a
first-of-kind XLARGE (5–8 h) is derived from nothing, because
`suggest_estimate` returned n=0. A band with no reference class is a guess
wearing a number.

### Action items

**(1) Estimation-mistake improvements**

- **Stop treating the rubric band as an estimate when `suggest_estimate` returns
  n=0.** BL-079's 5–8 h had zero historical basis and was wrong by roughly 12x.
  When the engine says INSUFFICIENT_HISTORY, record the size label and an
  explicit "no reliable estimate" rather than inventing hours — a number with no
  reference class is worse than an honest absence, because it gets planned
  against.
- **Apply a standing correction factor to COMPUTED suggestions.** BL-078 shows
  the engine's own output is still around 3x high. `suggest_estimate` already
  computes median_ratio; applying it twice — once for the size class, once for
  the observed residual bias — is a small, testable change.
- **Size the VERIFICATION separately from the BUILD.** Both items' code was
  fast; what actually consumed the sprint was acceptance testing, the two
  defects it found, and three full 581-test suite runs at roughly 94 s each.
  That is predictable work and it is currently invisible in the estimate.

**(2) Implementation-mistake improvements**

- **Measure a retrieval threshold before shipping it, never guess one.** I set
  `GROUNDING_THRESHOLD = 0.34` from intuition. Real cosines: 0.69 answerable,
  0.4491 nonsense. 0.34 admitted everything, which silently disabled the
  refusal path — the single most important behaviour in the feature. Any future
  threshold gets a measured pair of examples recorded next to it.
- **A single numeric gate was never going to separate "not in the corpus" from
  "lexically similar to the corpus."** The private-details question scored
  0.6816. The fix that worked was a second, semantic gate: the model's own
  decline. Design an ungrounded path with two independent signals from the start.
- **Do not quote a withdrawn claim inside its own withdrawal.** The first
  version of the BL-078 correction reproduced the stale sentence verbatim,
  leaving the exact string retrievable and quotable — defeating the whole
  purpose of the edit. Caught only because the verifier was tightened from "the
  specific sentences are gone" to "no such reference survives anywhere".

**(3) Neither, but still needed**

- **The gate that saved this sprint was one I did not write for it.**
  `test_reasoning_gateway_enforcement` failed the build on a direct Anthropic
  SDK import in `standing_interview.py`. Without it, a second uncontrolled model
  call site would have shipped. That is evidence the architectural-enforcement
  tests are earning their cost, and an argument for adding more of them rather
  than relying on review.
- **Deployment is not done.** SI is verified locally against the real 361-chunk
  corpus, and the nav entry self-hides in production until
  `/api/standing-interview/status` reports `loaded: true`.
  `scripts/deploy_platform_with_si_corpus.sh` exists and fails closed on all
  three invariants, but **has not been run**. SI must not be described as live
  until it has.
- **SPRINT AS A WHOLE:** every defect this sprint was found by *exercising the
  thing*, not by reading it — the threshold, the missing logging, the
  over-firing decline gate, the verbatim-quote mistake, and the SDK import. Four
  of five were invisible in the code as written. The sprint-level lesson is that
  for a feature whose output is prose, acceptance testing against real data is
  not a final step but the primary defect-detection mechanism, and should be
  budgeted as such.

### Carried forward

- BL-080 (access gate, notification) remains `planned`, correctly unstarted.
- The packet's Marsh and BCBSA role titles were **not** applied: that needs
  Books 01–04 unfrozen, which was not authorised. Reported, not silently closed.
- Two review rows are already in the queue from acceptance testing and should be
  triaged before the next sprint (`python agent/si_review.py`).

## Sprint 6 retro: RA-1, RA-2, BL-038, BL-056, BL-057, BL-046, BL-040, BL-039, BL-041 (CLOSED 2026-09-23, corrected same day after an independent Shiva review of the DRAFT found the diagnosis itself was wrong -- see the correction note before the diagnosis section)

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

### Correction, made 2026-09-23 after an independent Shiva review of the DRAFT above

The DRAFT's own Observation 1 (kept below, not deleted) claimed "suggest_estimate() had n=0 for every
combination, so nothing could correct them." **That claim is false**, and false in the direction that
excused the estimation gap rather than diagnosing it. The real `size_rationale` fields recorded in
docs/BACKLOG.json BEFORE the work show three of the seven items had a real COMPUTED suggestion available:

| Item | Chosen estimate (mid) | COMPUTED suggestion | Real actual | Suggestion vs. chosen: closer to actual? |
|---|---|---|---|---|
| BL-038 | 75 min | 30.4 min (n=4) | 7.9 min | Suggestion off by 22.5 vs chosen off by 67.1 |
| BL-040 | 32.5 min | 11.7 min (n=3) | 1.4 min | Suggestion off by 10.3 vs chosen off by 31.1 |
| BL-056 | 25 min | n=3 (no midpoint recorded) | 0.2 min | -- |

`docs/BACKLOG.json`'s own `_calibration_process` states: "A deviation from a COMPUTED suggestion must be
stated explicitly with a real reason, never silently overridden." Neither BL-038 nor BL-040 recorded a
deviation at the time -- both have now been recorded retroactively via `record_deviation()`, 2026-09-23,
with an honest note that no contemporaneous reason exists. The ONE other time in this project's history
this exact situation occurred (BL-036, prior retro), the retro's own conclusion was that the override was
wrong and the original computed suggestion was right. The correct diagnosis is therefore not "the rubric
needs recalibrating someday" -- a working, evidence-based correction mechanism exists and was silently
bypassed.

The DRAFT's sprint-level figure ("total wall-clock ~35 min") was the SUM of the seven items' individual
`started_at`/`completed_at` spans, not the commit-to-commit wall-clock figure prior sprints (2-5) used --
it excluded the merge, the post-merge CI-fix cycle, and the final state-sync merge. Recomputed on the same
basis as prior sprints: first real work evidence at 2026-09-22T20:03 UTC (BL-038 started) to the final
Sprint-6 state-sync merge at 2026-09-22T22:55:22 CEST (20:55:22 UTC) = **~52 minutes** commit-to-commit,
not 35. Both figures are given, explicitly labeled, per `_calibration_process`'s own requirement.

### Diagnosis (corrected 2026-09-23)

- **ESTIMATION WRONG, with a real, named mechanism, not just "rubric miscalibrated."** All 7 items landed
  outside tolerance, same direction as sprints 1-5. But 3 of 7 had a real COMPUTED suggestion available and
  it was silently overridden without the required deviation record, and in the one historical case this
  project can check, the override was empirically wrong. The action is enforcement/accountability of
  `suggest_estimate()` output, not another rubric-recalibration item written down and not applied.
- **IMPLEMENTATION ISSUES, real and separate from estimation.** (a) generated key material (PKCS#1 vs
  PKCS#8, OpenSSL 3.5) must be verified by parsing before use -- cost one extra test cycle across four
  services. (b) BL-039's `@LoadBalanced` bean collision (the gateway proxy silently picked up the wrong
  `RestClient.Builder`) is **not a new finding** -- it is a RECURRENCE of a pattern this project already
  named explicitly (CLAUDE.md's own AI-characteristic-defect-discipline section: "a new `@Bean` of a
  framework-owned, auto-configured type is HIGH/CROSS_MODULE... `@ConditionalOnMissingBean` matches by TYPE")
  and already logged once before (BL-007 item 7, this same RETRO_LOG.md). It was never written into
  `docs/LESSONS.md` either of the first two times. That absence, not the bug itself, is the real finding.
- **Neither, but still needed.** "Merged + pushed" was reported as sprint-complete before post-merge CI
  status was known -- two jobs did come back red (neither caused by Sprint 6 code; both real, root-caused,
  fixed the same night, see the note below). Sprint completion should not be declared until post-merge CI
  result is known, not just "merged and pushed."
- **Sprint-level finding.** The real binding constraint was never wall-clock time (52 min commit-to-commit
  for 8h of estimated work) -- it was the API usage budget (34% used at sprint start, per Owner). Future
  sprint planning and reporting should track against usage budget explicitly, not only estimated hours.

### Action items (three buckets, per CLAUDE.md's required structure)

1. **Estimation-mistake improvements**: treat an unrecorded override of a COMPUTED (n>=3) `suggest_estimate()`
   suggestion as a real process violation -- require `record_deviation()` at estimation time, not
   retroactively. Record this sprint's two now-populated reference classes (MEDIUM/MEDIUM/apply_known_pattern;
   LARGE/LOW_MEDIUM/first_of_kind) so the next sizing for either combination uses real history. Re-run
   `suggest_estimate()` for every Sprint 7 candidate now that this sprint's 7 new ratios exist, before using
   any previously-computed estimate range.
2. **Implementation-mistake improvements**: add a `docs/LESSONS.md` entry for the framework-owned-`@Bean`
   recurrence (its third occurrence, never previously logged there) and add a deterministic STATIC-tier
   check flagging a new `@Bean` method whose return type is a framework-owned auto-configured type without
   an explicit qualifier/`@Primary` review note -- same precedent as RA-1's XML-comment gate. Add: generated
   cryptographic key material must be verified by parsing before being wired into config.
3. **Neither, but still needed**: sprint completion reporting must wait for, or explicitly flag, post-merge
   CI status before being declared done. Fix `docs/PROJECT_STATE.json`'s stale `next_phase` (was still
   reading "Sprint 4 retro" two sprints later). Also: Sprint 5's own retro (above in this file) omitted the
   required sprint-level finding entirely -- the "one finding every sprint" rule has already drifted once
   before this correction; worth a standing reminder, not a one-off fix.

### Post-merge CI note
Post-merge CI on master (run 35780938679) was red in two jobs, neither caused by Sprint 6 code: billing-service's
Docker-gated Redis tests were already failing on the pre-sprint 11:06 run (unmocked `LegacyBillingSystemClient` from
ACT-013 -> 503), and the Customer app's Kafka fan-out test had a baseline race (`expected 5L but was 6L`). Both fixed
the same night as an in-scope proactive fix (see docs/LESSONS.md, 2026-09-22 entry); verification is CI-only because
neither test can run on the Docker-less dev machine.

### Original DRAFT observations (kept, not deleted, per this project's own record-keeping convention -- superseded above where they conflict)
1. Every item landed at 0.01-0.11 of its estimate midpoint -- the same direction as sprints 1-5, now on a sprint that
   included a LARGE security change and a first-of-its-kind BFF. ~~The raw rubric bands are still human-calibrated;
   suggest_estimate() had n=0 for every combination, so nothing could correct them.~~ **CORRECTED above: false -- 3 of
   7 items had real COMPUTED suggestions, silently overridden.** This sprint adds 7 ratios to the history: the next
   sizing for (MEDIUM, MEDIUM, apply_known_pattern) and (LARGE, LOW_MEDIUM, first_of_kind) will have real reference
   classes for the first time.
2. Implementation findings worth a rule: (a) generated key material must be verified by parsing before use (the PKCS#1/#8
   slip cost one extra test cycle across four services); (b) adding a second Spring constructor needs @Autowired --
   caught by tests, cheap, but the same class of 'framework wiring assumed' mistake as the RestClient.Builder @Primary
   regression in BL-039. **CORRECTED above: (b) is a recurrence of an already-logged pattern, not a fresh finding.**
3. Sprint-level: total wall-clock ~35 min for work estimated at 8 h, with three background JVM runs overlapped. The
   binding constraint was not time but the usage limit (34% used at sprint start, per Owner). **CORRECTED above: ~35
   min was a sum of item spans, not commit-to-commit wall-clock (~52 min) as prior sprints reported it.**
4. Post-merge CI on master (run 35780938679) was red in two jobs, neither caused by Sprint 6 code: billing-service's
   Docker-gated Redis tests were already failing on the pre-sprint 11:06 run (unmocked `LegacyBillingSystemClient` from
   ACT-013 -> 503), and the Customer app's Kafka fan-out test had a baseline race (`expected 5L but was 6L`). Both fixed
   the same night as an in-scope proactive fix (see docs/LESSONS.md, 2026-09-22 entry); verification is CI-only because
   neither test can run on the Docker-less dev machine. For the joint retro: "merged + pushed" was reported before the
   post-merge CI result was known -- the sprint's own 'CI gating' work made that gap visible.

## Sprint 11 — Standing Interview answer quality from Owner-logged failures (2026-09-27) — CLOSED, all items complete

### Scope, as the Owner pre-approved it

> "SI quality from OWNER-LOGGED failures... A. READ FIRST — dump the SI review
> queue + ACT-019... reproduce six questions with traces; quote current refuse
> rules from code and do not change them until the trace exists. C. FIX only
> what the traces show; do not lower the France refuse to make Kafka pass; add
> regression tests for the six questions; two independent signals; do not guess
> a new threshold without measuring. D. DEPLOY + PROVE LIVE on the same Railway
> host, corpus still untracked; if generic Kafka still refuses, STOP and report
> the new trace; do not loop."

Three items, sized BUILD / ACCEPTANCE / DEPLOY separately, all sized before work.

### Sizes given, before any work

| Item | Size | Estimate | Confidence | Pattern | suggest-estimate |
|---|---|---|---|---|---|
| BL-084 BUILD — trace + fix | MEDIUM | **NO RELIABLE ESTIMATE** | LOW_MEDIUM | investigation_only | **INSUFFICIENT_HISTORY** n=0 |
| BL-085 ACCEPTANCE — regression + gate | SMALL | **NO RELIABLE ESTIMATE** | MEDIUM | verification_only | **INSUFFICIENT_HISTORY** n=0 |
| BL-086 DEPLOY — ship + prove live | SMALL | 3–4 min (mid 3.3) | MEDIUM | apply_known_pattern | **COMPUTED** n=6, median_ratio 0.16 — adopted |

Two of three items carry no hour range at all. That is the Sprint 8 action item
working as designed for the second sprint running: a diagnosis whose cause is
unknown at sizing time cannot honestly be timeboxed, and the rubric's 20–40 min
would have been a guess dressed as a number.

### What the traces actually said — before anything was changed

The refuse rules were quoted from code and left alone until the trace existed:
`GROUNDING_THRESHOLD = 0.50` (measured, not guessed) and the first-sentence
`DECLINE_MARKERS` gate. **Neither was the cause of either failure, and neither
was changed.** The France refusal was never lowered.

| Question | scope | best | outcome (pre-fix) | real cause |
|---|---|---|---|---|
| explain your experience with kafka | career | 0.7332 | **leak_blocked** | leak-scanner false positive |
| explain your experience in using oauth or jwt | career | 0.7181 | answered, Dissatisfied | retrieval covered 1 employer |
| How did you use Kafka at BCBSA? | career | 0.7606 | **leak_blocked** | same false positive |
| Did NRG use Kafka? | career | 0.7791 | answered (good) | — |
| Tell me about Kafka at NRG | career | 0.7381 | answered (good) | — |
| How did you use Spring Security at NRG? | career | 0.6915 | answered (good) | — |
| What is the capital of France? | both | 0.4491 | ungrounded (correct) | — |

**Cause 1 — the generic Kafka "refusal" was not a refusal decision at all.**
Retrieval scored 0.7332 and the model produced the best Kafka answer the system
has ever produced. The leak scanner then matched `(the|my) ...source` inside the
sentence *"That let the receiving side stay current without the source service
having to synchronously coordinate with every consumer"* — ordinary backend
English for the upstream service, zero provenance leakage — and because a leak
triggers a refusal, that whole answer was replaced with the standard refusal
line. The Owner saw an unexplained refusal. The queue row said `leak_blocked,
best_score=0.7332`, which is why dumping the queue first mattered: the refusal
text pointed at a corpus gap and the row pointed at the real cause.

**Cause 2 — the OAuth/JWT Dissatisfied click was a retrieval problem, not a
wording problem.** Five of six chunks came from one employer's books and one
from another's. Pure cosine top-k has no reason to spread. The model produced one
paragraph with no employer attached to any claim, because two of the three
employers' material was never in its context. The system prompt already asked
for specificity; it could not comply with material it did not have.

### What was changed

1. `source` narrowed to provenance senses only (`the sources say`, `my source
   material`, …). Every other provenance word untouched.
2. Employer-balanced retrieval for questions that name no employer: a reserved
   slot per employer, most recent first, and any employer whose own best chunk
   is below the grounding threshold is dropped. A question that *does* name an
   employer stays pure top-k — those answers were already the ones to keep.
3. Every excerpt is labelled with its employer, so attribution is supplied
   rather than inferred from mid-book text that often never repeats the name.
4. System prompt: one employer at a time, never blend two, a confirmed absence
   is a real answer.
5. Corollary bug found by its own test: with hits in employer order,
   `hits[0]["score"]` is no longer the maximum, so the grounding gate now reads
   `max(...)` — otherwise the fix would have started refusing answerable questions.
6. A recurrence of the 2026-09-14 `load_dotenv` defect: reached outside the web
   server, `standing_interview` had no `.env`, so the very first trace read
   `no_model` and looked like an empty corpus.

### Verification

- **41 hermetic SI tests** (was 30); whole suite **593** (was 581), 0 failures.
- **9 of the 11 new tests observed FAILING** against the pre-fix module for the
  intended reasons. The other two are deliberate no-regression guards on the
  part of the leak pattern that was narrowed away — they must pass before and
  after, and without them the narrowing would be unguarded.
- `agent/si_acceptance.py` replays all seven questions against the real
  361-chunk corpus and a real model, with the **same assertions locally and
  over HTTP**. Local 7/7. **Run against the pre-fix module it goes RED on
  exactly the two Owner-reported defects and stays green on the four
  already-good questions** — the gate is proven to detect the known-bad case
  rather than being a green rubber stamp.
- **Production, after the deploy:** 7/7 PASS on
  `agentic-platform-backend-production.up.railway.app`. `/standing-interview`
  HTTP 200, nav entry present, corpus `{"loaded":true,"chunks":361}`, and the
  Dissatisfied path still writes a real ledger row (verified by posting one and
  reading it back through `si_review.py`). Corpus tracked in git: 0 files.

Production generic Kafka now opens: *"At NRG Energy, Kafka wasn't used at all —
I confirmed this was a comprehensive absence, zero hits across the full file
census... At BCBSA, I directly worked on Kafka producer/consumer application
code..."* Production generic OAuth now opens by employer, NRG first, with Marsh's
Apigee edge in its own paragraph and the RS256/key-rotation detail explicitly
declined.

### Final actuals

| Item | Size | Estimate (mid) | Actual | Ratio | Verdict |
|---|---|---|---|---|---|
| BL-084 BUILD | MEDIUM | *no estimate* | ~16 min | n/a | cannot be scored |
| BL-085 ACCEPTANCE | SMALL | *no estimate* | ~14 min | n/a | cannot be scored |
| BL-086 DEPLOY | SMALL | 3.3 min | **~9 min** | **2.73** | outside [0.7, 1.3] — **ABOVE** |
| **SPRINT** | 3 items | 3.3 min scoreable | ~48 min total (3.3 min scoreable → 9 min) | — | over on the one scoreable item |

Wall-clock markers: sprint start ~20:45, fix verified 21:01, tests+CI green
21:15, commit `8f2b012` 21:24, upload 21:28, production replay green 21:30.
Running total: **2 of 39 items inside the ±30% band** (`BL-021`, `BL-029`;
computed from `docs/BACKLOG.json`, not asserted).

### Diagnosis — ESTIMATION WRONG (third consecutive over), and one real IMPLEMENTATION ISSUE

**ESTIMATION WRONG, BL-086, ratio 2.73.** This is now the *third consecutive*
COMPUTED suggestion to land above the band (1.9 and 3.3 in Sprint 9, 2.73 here).
Three in a row in the same direction is no longer oscillation — it is a
consistent bias, and its mechanism is identifiable: the engine's `median_ratio`
of 0.16 is built almost entirely from Sprints 1–7, where the *estimates* were
inflated. Multiplying a correctly-sized task by 0.16 produces a number that
cannot be met. I adopted it anyway, deliberately and on the record, because
overriding a computed number with a narrative feels better and is exactly what
this project's own rule forbids. That was the right call for the data and the
wrong call for the schedule, and it is now answerable with three points instead
of two.

Specifically, the 3.3 min midpoint priced "run a deploy script" and nothing
else. The real 9 minutes was: one acceptance run that **correctly blocked the
upload**, one assertion of my own to re-scope, the upload, a real container
build, and a full production replay. None of that is overhead — it is what
"prove it live" costs, and no estimate in this project has ever included it.

**IMPLEMENTATION ISSUE, mine, caught by the gate rather than by the Owner.**
My first version of `_check_generic_kafka` asserted NRG had to be named *before*
BCBSA. The Owner stated NRG-first for the OAuth/JWT question; for Kafka the
stated requirement is content ("BCBSA producer/consumer hands-on + NRG has no
Kafka"). My invented ordering rule failed a genuinely good answer that opened
with the real hands-on experience and then stated the absence — which is better
interview technique for a technology the current employer doesn't use. Removing
it restores the Owner's stated criteria rather than weakening a gate, and the
reason is written into the code beside the check so a later reader cannot
mistake it for a quiet relaxation. Same shape, twice in one sprint: my blanket
first-person pronoun check also failed the correct, pronoun-free *"No, Kafka
wasn't used anywhere on the NRG project"* answer.

**No IMPLEMENTATION ISSUES verdict for BL-084 or BL-085.** Both landed, verified,
proven capable of failing, pushed, no rework.

### Action items

**(1) Estimation-mistake improvements**

- **Stop adopting the COMPUTED suggestion for `apply_known_pattern` until the
  ratio history is re-based.** Three consecutive overs with an identified
  mechanism is enough evidence. The concrete fix is not another multiplier: it
  is to compute `median_ratio` only over items whose estimate was itself
  produced by the engine, so the 2016-era inflated-estimate sprints stop
  poisoning it. Until that exists, `apply_known_pattern` items get
  NO RELIABLE ESTIMATE like everything else — which is honest, and which has now
  worked twice.
- **Any item whose acceptance criterion contains the words "prove live" is not
  SMALL.** Three sprints of evidence: the deploy step is never the cost, the
  proof is. A deploy item's estimate must include a gate run, a container build
  and a production replay, or it is estimating a different task than the one in
  the acceptance criteria.
- **"No reliable estimate" continues to earn its place.** Two of three items ran
  against no predicted number and nothing was lost by not inventing one.

**(2) Implementation-mistake improvements**

- **An assertion I invent is a requirement I invented.** Twice this sprint a
  check of my own failed a correct answer (ordering, first-person). New rule:
  every assertion in an acceptance gate is traceable to a quoted line of the
  Owner's criteria, or it is labelled in the code as my own inference and
  reviewed against a known-good output before it can block a deploy.
- **A gate that blocks must be run against known-good output before it is
  trusted to block.** This sprint's gate was correctly proven against the
  known-BAD case (it went red on the pre-fix module). It was not proven against
  known-GOOD output, which is how two false-positive checks reached it. Both
  directions, same as the leak-scanner lesson this sprint is built on.
- **The deploy script had been enforcing the bug it was written before.** Its
  header still claimed `railway up` uploads gitignored files and its guard still
  *required* the corpus to be gitignored — so running it would have aborted a
  correct deploy. Sprint 10 fixed the mechanism and never revisited the script
  that encodes it. Rule: when a root cause inverts an assumption, grep for every
  artefact that asserts the old one in the same sprint, scripts and comments
  included, not only the code path that failed.

**(3) Neither, but still needed**

- **The review queue paid for itself on its first real use.** Both Owner rows
  had causes that the user-visible text actively pointed away from: a "refusal"
  that was a leak-block at 0.73, and a Dissatisfied click that was a retrieval
  coverage problem rather than a prompt problem. ACT-019 stays open as a
  standing per-sprint step and now carries a `triage_log`.
- **A one-sided safety control destroys good output silently.** Written to
  `docs/LESSONS.md` as its own lesson. The leak scanner had seven LEAKY fixtures
  and three short hand-written CLEAN ones — a green 30-test module with an
  invisible false positive in its highest-value path. Any blocking content gate
  needs CLEAN fixtures copied verbatim from real generated output.
- **SPRINT AS A WHOLE:** every minute of diagnosis in this sprint was spent on
  the two failures the Owner logged, and both root causes were in code the
  Owner never saw and neither was where the symptom pointed. The sprints that
  went badly (8, 9) were the ones that started from an assumption about someone
  else's system; this one started from a recorded row and a trace, and it landed
  in under an hour including a production proof. The transferable rule is not
  about Kafka or OAuth: **reproduce with a trace before touching a rule, and
  the fix is usually somewhere the symptom was not.**

### Carried forward

- BL-080 (access gate, SMS notification) still `planned`, untouched.
- ACT-019 open by design; Sprint 11's triage recorded in it.
- Sprint 10 retro still not written (Owner deferred it: "retro only if there is time").
- Remaining Owner-packet facts not yet applied to the books (Marsh Liberty
  Mutual/Bavaria, Progressive/Velocity, incidents A and C, NRG EVgo removal,
  Lambda 2025) — unchanged by this sprint.

## Sprint 12 — Standing Interview interview voice (2026-09-27) — CLOSED, all items complete

### Scope, as the Owner approved it

> "GOAL: Answers must sound like Karthik in an interview, not like a search
> report… HOW: Change the SI generation prompt + a post-check that rejects
> banned phrases and truncated last sentences. Do not rebuild retrieval unless
> a trace shows voice cannot be fixed in the prompt. Add tests that fail on the
> OLD kafka-generic text… Prove the kafka-generic question LIVE."

Three items, sized BUILD / ACCEPTANCE / DEPLOY separately, all sized before work.

### Sizes given, before any work

| Item | Size | Estimate | Confidence | Pattern | suggest-estimate |
|---|---|---|---|---|---|
| BL-087 BUILD — voice spec + post-check | MEDIUM | 11.2 min (mid) | MEDIUM | apply_known_pattern | **COMPUTED** n=6, median_ratio 0.375 |
| BL-088 ACCEPTANCE — tests + gate | SMALL | **NO RELIABLE ESTIMATE** | MEDIUM | verification_only | **INSUFFICIENT_HISTORY** n=0 |
| BL-089 DEPLOY — ship + prove live | SMALL | 6.8 min (mid) | MEDIUM | apply_known_pattern | **COMPUTED** n=7, median_ratio 0.68 |

Sprint 11's retro proposed withholding COMPUTED suggestions for
`apply_known_pattern` until the ratio history is re-based. That action item is
**not Owner-approved**, and this project requires approval before acting on
retro action items, so the computed numbers were adopted. Worth recording
separately: the SMALL/`apply_known_pattern` median had **already moved 0.16 →
0.68 on its own** once BL-081/083/086 entered its history, which substantially
weakens the case for the re-basing fix that retro proposed.

### What the traces said, and the question the Owner left open

The Owner's condition for touching retrieval was "unless a trace shows voice
cannot be fixed in the prompt". **It can.** Retrieval still returns NRG's
chunks first, and after the prompt change the model leads with BCBSA anyway.
Retrieval was not rebuilt.

One rule turned out to cover both requirements with no conflict: **lead with
where you actually used it.** For Kafka that is BCBSA first; for OAuth/JWT that
is NRG first. The spec looked like two ordering rules and was really one.

Three failures the prompt alone could not fix, each found by a real trace:

1. **The model repeated the books' own audit register.** "no genuine evidence
   of Kafka" is a phrase the Marsh book literally contains. Banning the word
   "genuine" produced "no real evidence" on the next run; banning the noun
   phrase produced "a clean absence". Fixed by a prompt rule that explicitly
   *translates* audit wording into speech, plus a maintained ban list.
2. **It recited interview-prep excerpts as memory.** BOOK-03 contains practice
   Q&A and a general trade-off discussion; the model served it as experience,
   which is where the invented member-ID partition key came from. Fixed by
   naming preparation material as not-memory.
3. **A retry told only a violation CATEGORY swapped one banned phrase for
   another.** "invents an exact cron count" → the retry removed it and said
   "substring". Fixed by quoting the matched words back, and then by giving the
   retry the whole register rather than the single phrase it was caught on.

### What was built

- **Frozen voice spec in the system prompt**: lead with where the work
  happened; one employer at a time; omit an employer you have nothing to say
  about; state the boundary in one sentence; at most one uncertainty line;
  translate audit wording; never recite prep material; 6–10 spoken lines.
  Three worked Not/Say example pairs, which consistently outperformed abstract
  rules.
- **`voice_violations()`** — a deterministic gate, separate from `leaks()` on
  purpose (a leak refuses immediately; a voice violation gets one retry).
  Every banned phrase chosen by counting the real corpus: "partition key" 0
  occurrences in all 361 chunks, "at-least-once" and "schema evolution" 0 in
  the hands-on books, "cron" 0 in the hands-on books.
- **One corrective retry, then `voice_rejected`** with its own outcome, and
  the matched phrases recorded into the ledger and shown by `si_review.py`.
- **`MAX_ANSWER_TOKENS` 400 → 1000** as a truncation safety net set far above
  the length target, so an over-long answer fails as "reads as an essay"
  rather than as an ambiguous cut-off.

### Verification

- **22 new hermetic tests** (SI module 41 → 63; suite 593 → 614, 0 failures).
  18 of the first 19 observed FAILING against the pre-Sprint-12 module; the
  one that passes both sides is the guard that a clean first attempt must not
  pay for a retry. The two later gap tests were also observed failing against
  the intermediate commit.
- **Sprint 11's seeding trick did not work here** — the new checks call
  `si.voice_violations()`, which the old module lacks, so importing it raises
  `AttributeError` and proves nothing. Replaced with something better: a
  `--selftest` that asserts every check rejects the **verbatim Owner-rejected
  answer** pulled from the event ledger, and it runs automatically before
  every real gate invocation, so it cannot rot the way a one-off shell
  demonstration does.
- **Local acceptance 8/8 on three consecutive runs**; the absence-only
  question stress-tested 6/6 answered.
- **Production 8/8 on two consecutive runs** after the final deploy, plus the
  live generic-Kafka answer read in full.

Live now, verbatim: *"My hands-on Kafka experience is from BCBSA. I wrote
producer and consumer application code there… Outside of BCBSA, Kafka wasn't
part of the picture. At NRG the async work ran through SQS with a dead-letter
queue and some scheduled jobs, not Kafka."*

### Final actuals

| Item | Size | Estimate (mid) | Actual | Ratio | Verdict |
|---|---|---|---|---|---|
| BL-087 BUILD | MEDIUM | 11.2 min | **~56 min** | **5.00** | outside [0.7, 1.3] — **ABOVE** |
| BL-088 ACCEPTANCE | SMALL | *no estimate* | ~22 min | n/a | cannot be scored |
| BL-089 DEPLOY | SMALL | 6.8 min | **~25 min** | **3.68** | outside band — **ABOVE** |
| **SPRINT** | 3 items | 18.0 min scoreable | ~87 min total, 81 min scoreable | **4.50** | **ABOVE** |

Markers: start ~21:55, first clean trace 22:27, first commit `ffd12b1` 22:51,
gap fix `c760b73` 23:06, absence fix `afb2d9b` 23:13, production green 23:17.
Running total: **2 of 39 items inside the ±30% band** (computed from
`docs/BACKLOG.json`).

### Diagnosis — ESTIMATION WRONG, and this time the *pattern type* was wrong, not the multiplier

Fourth and fifth consecutive COMPUTED suggestions above the band. But the
useful finding is not "the multiplier is biased again" — it is that **I chose
the wrong `pattern_type` for both items, and the multiplier was then applied
correctly to the wrong base.**

I labelled both `apply_known_pattern`. Editing a prompt and adding a regex list
*looks* exactly like work this project has done many times. The actual work was
**iterative convergence against a non-deterministic generator**: five prompt
iterations, each requiring a real model call to evaluate, each revealing a
failure mode that could not have been predicted from reading the code — the
audit register, then the prep-material recitation, then the retry swapping one
banned phrase for another, then the absence-only shape, then two more register
variants found only by reading live output. That is `investigation_only`
behaviour wearing `apply_known_pattern` clothes.

This is a better diagnosis than Sprint 11's because it is actionable in
advance: the tell is not the size of the diff, it is **whether the acceptance
criterion can be evaluated without running the model.** If it cannot, no
number of past prompt edits makes it a known pattern.

There is no IMPLEMENTATION ISSUES verdict for BL-088. There is one for BL-087
and one for BL-089, both below.

### Action items

**(1) Estimation-mistake improvements**

- **New sizing rule, and the one worth keeping from this sprint: if the
  acceptance criterion can only be evaluated by running a non-deterministic
  model, the pattern is `investigation_only`, never `apply_known_pattern` —
  regardless of how familiar the code change looks.** Both of this sprint's
  misses come from that single mislabel. This is a rule about choosing the
  input to the estimator, which is the part I actually control; the multiplier
  was applied correctly to a base I had picked wrongly.
- **Withdraw Sprint 11's "re-base median_ratio" proposal as premature.** The
  SMALL/`apply_known_pattern` median self-corrected 0.16 → 0.68 within one
  sprint purely by accumulating real data. Re-basing it by hand would have been
  a manual intervention into a mechanism that was already converging. Recorded
  as tested-and-withdrawn so it is not re-proposed from the Sprint 11 text.
- **Sprint 11's "prove live is not SMALL" was right and I overrode it.** I
  kept BL-089 SMALL on the argument that the deploy path is now a single gated
  script, and recorded that as a prediction to be scored. It scored 3.68. The
  script is not the cost; three deploy-verify-fix cycles are. Reinstated: an
  item whose acceptance contains "prove live" is at least MEDIUM.

**(2) Implementation-mistake improvements**

- **A banned-phrase list is never finished by reasoning about it.** Three
  separate times this sprint, banning one word moved the model to the next one:
  genuine → real → clean. Each widening was correct and none was predictable.
  **Rule: after any change to how answers are generated, read real output
  again before calling the gate done — and treat the first live answer that
  passes as evidence to be read, not as a result to be filed.** The two gaps in
  `c760b73` were found exactly that way, in an answer the gate had already
  passed.
- **Two of my own checks contradicted each other and the product paid for it.**
  `_check_generic_kafka` accepted the words "absence" and "zero" as proof the
  NRG absence was stated, while the voice spec bans those same words — so a
  correctly-voiced answer failed the content check. Second sprint running that
  an assertion I invented failed a good answer. **Rule: when a sprint adds a
  gate that bans vocabulary, grep every existing assertion for that vocabulary
  in the same change.**
- **The deploy cycle was entered three times because each fix was found after
  deploying, not before.** The first two were legitimate (live output is the
  only place those gaps were visible), but the third — the absence-only
  question — was reproducible locally and would have been caught by stressing
  each question more than once before the first deploy. **Rule: for a
  non-deterministic surface, the pre-deploy gate runs each question N times,
  not once.** One run proves it can pass; it does not prove it does.

**(3) Neither, but still needed**

- **Recording `voice_violations` into the ledger paid for itself inside the
  same sprint.** The production `voice_rejected` was diagnosed from one read of
  `si_review.py` — both the first-attempt and retry causes, no local
  reproduction. Sprint 11's lesson ("an unexplained refusal is the expensive
  kind") applied prospectively for once, rather than after the fact.
- **Known residual, stated rather than chased.** Roughly one run in six still
  narrates how the JMS lead was investigated. The prompt has a worked example
  against it and the register ban catches its common forms, but paraphrase is
  open-ended, and widening further starts risking refusals on good answers —
  which is the Sprint 11 defect this project already paid for once. Left open
  deliberately, not overlooked.
- **SPRINT AS A WHOLE:** every previous SI sprint fixed something that was
  *wrong*. This one fixed something that was *correct but badly said*, and it
  cost more than any of them — because correctness has a test and voice has a
  judgement, and the only way to turn a judgement into a test was to read real
  output over and over until the patterns were empirical rather than
  imagined. The transferable rule is the sizing one above: **work whose
  acceptance can only be evaluated by running the model is investigation, no
  matter how small the diff looks.**

### Carried forward

- BL-080 (access gate, SMS notification) still `planned`, untouched.
- ACT-019 open by design; Sprint 12's triage recorded in it.
- Sprint 10 retro still not written (Owner deferred it).
- Remaining Owner-packet book facts (Marsh Liberty Mutual/Bavaria,
  Progressive/Velocity, incidents A and C, NRG EVgo removal, Lambda 2025) —
  unchanged by this sprint.


## Sprint 13 — three-task autonomous sprint: Standing Interview P0, durable LangGraph workflow, JD Match (2026-09-29) — CLOSED, all nine items done

### Scope, as the Owner approved it

Three independent tasks, in this order, each committed, deployed and verified before the
next: (1) the Standing Interview must answer ANY on-book question like the candidate in a
real interview — a mechanism (career map, query rewrite, only-where-used policy), with the
six exam questions as a regression pack that must not be hard-coded; (2) one bounded,
production-grade durable agentic workflow on LangGraph with persisted checkpoints,
human-in-the-loop interrupt/resume, crash recovery and idempotent side effects, the
model gaining no authority; (3) JD Match, a public page mapping a pasted job description
to verified evidence where the model proposes and code decides. Twelve decisions were
taken with the Owner before the start (recorded in DECISIONS.md). Run on Fable 5.1.
The Owner asked for the retro to be written without waiting for approval.

### Sizes given, before any work

Nine items, sized against the rubric, `suggest-estimate` run for each. Seven were
`INSUFFICIENT_HISTORY` (n=0 for every `first_of_kind` / `investigation_only`
combination) and used their raw range; two `apply_known_pattern` MEDIUMs were COMPUTED
(n=7, median_ratio 0.39) and adopted, recorded as predictions to be scored.

### Final actuals

| Item | Size | Estimate (mid) | Actual | Ratio | Band |
|---|---|---|---|---|---|
| BL-090 | LARGE | 120 min | ~30 min | **0.25** | BELOW |
| BL-091 | MEDIUM | 67.5 min | ~26 min | **0.39** | BELOW |
| BL-092 | MEDIUM | 13.7 min | ~33 min | **2.41** | ABOVE |
| BL-093 | XLARGE | 240 min | ~25 min | **0.1** | BELOW |
| BL-094 | LARGE | 120 min | ~25 min | **0.21** | BELOW |
| BL-095 | MEDIUM | 60 min | ~11 min | **0.18** | BELOW |
| BL-096 | MEDIUM | 21.4 min | ~8 min | **0.37** | BELOW |
| BL-097 | LARGE | 160 min | ~15 min | **0.09** | BELOW |
| BL-098 | MEDIUM | 70 min | ~29 min | **0.41** | BELOW |
| **SPRINT (summed items)** | 9 items | 872.6 min | ~202 min | **0.23** | BELOW |
| **SPRINT (wall-clock)** | | | ~180 min (22:05Z → ~01:05Z) | **0.21** | BELOW |

The two figures answer different questions: summed-item actuals count only the minutes
attributed to an item's own work; wall-clock includes every deploy wait, gate run and
watchdog kill. Roughly 20 minutes of Task 2 and 10 minutes of Task 3 drafting happened
inside Task 1's and Task 2's deploy waits and are counted once, under the item that used
them. Running total: **2 of 48 items inside the ±30% band** (this sprint added 0).

### Diagnosis — ESTIMATION WRONG on all nine, in the opposite direction from Sprints 11–12; and real IMPLEMENTATION ISSUES on three

**ESTIMATION WRONG (nine of nine, all BELOW).** Sprints 11 and 12 ran 3–5× ABOVE their
COMPUTED midpoints; this sprint ran 0.1–0.4× BELOW its raw ranges. The raw ranges were
sized as if each item were built sequentially from a blank page by an executor who waits
for its own builds. The actual working pattern was different in two ways the rubric only
half anticipates: (a) every long wait (corpus rebuild, gate run, deploy, drill) was used to
draft the next item in the scratchpad, so `first_of_kind` items arrived at integration
with their code, tests and drill already written; (b) the estimator had n=0 for every
`first_of_kind` combination, so nothing could correct the raw ranges. The rubric's
sequential-vs-parallel instruction is written for parallel subagents; it applies just as
much to one executor overlapping drafting with waits, and it was not applied. The two
COMPUTED items behaved differently from each other: BL-096 (a YAML transform) scored
0.37 — the historical 0.39 was right; BL-092 (prove-live) scored 2.41 — the third sprint
in a row where a "prove live" item ran far above a COMPUTED midpoint, now with the cause
visible: the deploy loop is a convergence loop against a non-deterministic surface
(seven attempts, each stopping on something real), which is `investigation_only` work
wearing an `apply_known_pattern` label.

**IMPLEMENTATION ISSUES (named separately, each real).**
- BL-092: two of the eight deploy attempts were self-inflicted. A patch routed through a
  Bash heredoc lost its `\b` escapes (three times in one night, once after the lesson was
  already written down), and a test command piped into `tail` masked a red suite so a
  deploy started on failing tests and had to be stopped by hand.
- BL-094: the first mutation check ran against an unmutated copy because a Git-Bash
  `/tmp` path was handed to Python as a Windows path; a green result that proved nothing,
  caught by re-reading the traceback.
- BL-098: the first production ledger check compared laptop timestamps with container
  timestamps (laptop 6.3 min ahead) and looked like a missing write for twenty minutes.

### What the sprint found that was not in its scope (all recorded, none silently fixed)

- `demo_catalogue`'s `footer_text` anchor cannot match the real `index.html` (ACT-022).
- LangGraph's default `durability="async"` loses a node's checkpoint on a kill at the next
  node boundary; the durable workflow now asks for `"sync"` (DECISIONS.md, LESSONS.md).
- Railway's cutover routed a remote gate to the previous container; the deploy script now
  gates on a per-upload marker (LESSONS.md).
- `leak_blocked` rows carry the refused model text — an Owner decision (ACT-023).
- The untracked corpus is one `git add -A` from being committed (ACT-020).
- The audit register returned in two shapes found by the independent QA pass on a fresh
  draw (ACT-021, fixed, rode the Task 2 deploy).
- The host's memory watchdog killed six long background runs; every long drill and gate
  now has a per-scenario switch and the critical runs were done in the foreground.

### Action items (three fixed sections; NOT sized; Owner approval required before any is acted on)

**(1) Estimation-mistake improvements**
- Record this sprint's nine `first_of_kind` / `investigation_only` actuals so
  `suggest-estimate` stops returning `INSUFFICIENT_HISTORY` for them; the raw ranges were
  4–10× too high and the estimator had no data to say so.
- Extend the rubric's parallel instruction to a single executor: when an item can be
  drafted during another item's waits, give the sequential-effort figure AND the expected
  overlap, and score against the wall-clock figure for the sprint.
- Label any item whose acceptance is "prove live" on a non-deterministic surface
  `investigation_only`, regardless of how proven the deploy script is (BL-089 scored 3.68,
  BL-092 scored 2.41; the script was never the cost either time). This repeats Sprint 12's
  unapproved item with two more data points.

**(2) Implementation-mistake improvements**
- Make "no backslash through a heredoc" mechanical: patches to files are written to a
  scratchpad script with the Write tool and executed; the Bash tool is not used to author
  file content that contains a backslash. Three real incidents in one night.
- Never chain a deploy after a piped test command; pipelines mask exit codes. A deploy
  chain uses the script (which has `set -euo pipefail`) or an explicit exit-code check.
- Before comparing a timestamp from another host, print the two clocks side by side
  (`SELECT now()` vs `date -u`) and record the skew; laptop ahead by 6.3 min today.

**(3) Neither, but needed — and one for the sprint as a whole**
- SPRINT AS A WHOLE: three XLARGE tasks in one session worked, but only because every wait
  was used for drafting and because the host's memory kills were survivable with
  foreground re-runs. The Owner's own operating policy names session length as a cost
  driver; this session's token cost was not measured by me and should be read from the
  Claude Code hook's ledger rows before deciding whether to repeat this shape. The
  recommendation is to keep multi-task sprints but budget a deliberate `/compact` between
  tasks next time.
- Owner decisions queued: ACT-020 (corpus guard), ACT-022 (footer anchor), ACT-023
  (refused text in the ledger), the retryable-leak rule (DECISIONS.md), and the FHIR
  clause removed from the Sprint 12 frozen fixture under the Sprint 13 Q3 rule.
- The 29 pre-existing backlog items with statuses outside `_status_values`
  (BL-042…BL-080) are doc drift the brief already flags; a one-line normalisation would
  make `state_brief.py`'s status counts trustworthy again.

### Cost and usage, honestly labelled

- Standing Interview gate runs: ~14 full or partial runs (local and remote) at 15–17 real
  model calls each — roughly 230 Sonnet-5 calls; measured per-run cost is not aggregated
  by the gate, so the total is an estimate of $5–7, not a measured figure.
- JD Match: eval run 1 $0.1732 and run 2 $0.1366 (measured); one production submission
  $0.0302 (measured); three Playwright real runs ~$0.03 each (estimated from the same shape).
- Durable workflow: the advisory investigate call is ~130 tokens per workflow start
  (measured on the production run, $0.0009); ~12 starts in the drills.
- qa-evaluator subagent: 91,516 tokens, 41 tool uses, 20.6 minutes (reported by the tool),
  cost not exposed to this session.
- This session's own tokens: not measured by me; the Claude Code SessionEnd hook records
  them in the ledger under `claude_code`.

### Carried forward

- Not verified on production: a kill DURING the durable workflow's pipeline (local drill
  only) — an ephemeral filesystem plus no push credential means a lost workspace fails
  safely rather than resuming; the Owner may configure `DEMO_GIT_PUSH_TOKEN` to make the
  applied branch durable off-box.
- JD Match's shortlist is a cosine over 22 registry entries; a broad requirement can be
  assessed against a neighbour. Cooldown and daily cap are per instance.
- Playwright E2E's pre-existing non-blocking failure was not touched.


## Sprint 14 — recruiter-facing homepage, public-navigation cleanup, durable-agent case study (2026-09-29) — CLOSED

### A. Scope

**Planned (11 sized items, 452 min summed midpoint).** Homepage at `/`; durable-agent case
study; canonical navigation; Learn/JD Match unpublished; independent re-verification of six
evidence rows; forbidden-claim and truth guards; bounded truth-smoke of linked pages; the full
UI acceptance matrix at three viewports; deploy and production verification; qa-evaluator
stranger check; retro plus backlog write-back.

**Completed:** all eleven.

**Deliberately not done, and why:**
- **No CV button.** No PDF exists in the repository and the contract forbade placeholders, so
  the slot was left out entirely rather than shipped dead. `BL-153`.
- **Standing Interview is nav-only, not a homepage CTA.** The 2026-09-29 SI audit found it
  volunteering unsolicited negatives on 39% of answered questions and refusing one legitimate
  interview question 3 of 3 times. Fronting the site with it would have led on the weakest
  surface. `BL-155`.
- **Dashboard de-emphasized, not rewritten.** 3,470 words and 13 jargon terms, measured. Out of
  public nav, still reachable from Usage. `BL-157`.
- **Privacy notice / Impressum not written.** Both need decisions this executor cannot make, and
  one collides with the Owner's own rule against publishing a home address. `BL-150`, `BL-151`.

### B. Time

| | |
|---|---|
| Summed item midpoints | 452 min |
| Actual wall-clock | ~218 min |
| Ratio | 0.48 |

Single executor, so the summed and wall-clock figures answer the same question this time —
unlike Sprint 13, where overlapping waits made them diverge.

### C. Defects discovered

| # | Defect | Found by | Should an existing test have caught it? | Root cause | Regression added |
|---|---|---|---|---|---|
| D1 | `tools.py` reported "file is not valid UTF-8 text" about a perfectly valid file | The hermetic suite (8 `test_rag_index` errors) | Yes — and it did, once a file existed that triggered it | Raw bytes truncated at 20,000 then decoded, splitting a multi-byte character | Covered by the existing suite, now green |
| D2 | `static_gate.py` XML-comment gate died with `TypeError: NoneType` | The hermetic suite | Yes — and it did | `subprocess.run(text=True)` with no encoding decodes with the Windows locale codec; any committed file it cannot map kills the gate | Covered by the existing suite |
| D3 | **Navigation sat 22px left of the content column** | **Screenshot inspection. No automated check saw it** | **No. Every DOM, overflow and existence assertion passed** | Nav lived in a wrapper with its own horizontal padding while the content column had its own | **Yes** — numeric alignment assertion at all three viewports |
| D4 | **`/learn.html` and `/jd-match.html` served a full page, 200** | **Manual probing of the static mount before deploy** | **No — my own new guard asked only about `/learn` and `/jd-match`** | The app ends in `Mount("/", StaticFiles(html=True))`; unregistering a route does not unpublish a filename | **Yes** — guard widened to 14 paths including `.html`, `.js`, `.css` and the three `learn-*.json` files |
| D5 | The forbidden-claim guard could not see an overclaim written inside the scope-boundaries block | **Seeded mutation M1** | No — the guard was new and wrong | The block was excluded wholesale so it could legitimately name absent capabilities | **Yes** — the check is now sentence-scoped: a forbidden term must share a sentence with a negation marker |
| D6 | The first proof card deep-linked to `/workbench#verified-run`, an anchor that does not exist | Reading `workbench.html` before shipping | No test existed | Invented an anchor from memory instead of checking | **Yes** — anchor targets are verified against the target page's real element ids |
| D8 | **`/usage` and `/dashboard` scrolled the whole page sideways** | **The production UI matrix** | **No — nothing measured horizontal overflow on those pages before this sprint** | A wide `.cap-table` dragged the document with it; `overflow-x` needs `display:block` on a `<table>` | **Yes** — 6 assertions, both routes x three viewports |
| D7 | `test_event_ledger` leaves far-future mock rows in the live ledger and then fails on them | The suite, before any sprint change | It is the test | Accumulated fixture rows from prior runs | No — pre-existing, CI-excluded, `BL-162` |

D3, D4 and D8 are the three that matter for the Owner's question about the framework. All
were **real defects that every automated check passed**, and each was caught by a different kind
of human attention: D3 by looking at a screenshot, D4 by typing a URL by hand, D8 by running the
production matrix at three viewports instead of one.

D8 is worth singling out. It was pre-existing and on pages this sprint never edited, and
`/usage` is one click from the home page in the canonical navigation — so a recruiter opening
the site on a phone would have met a page that scrolled sideways. It was fixed rather than
deferred precisely because the release standard is zero known defects on recruiter-visible
surfaces, not zero defects in code this sprint happened to touch.

### C2. Deploy attempts

Four platform deploys, which is itself a finding:

| # | Outcome |
|---|---|
| 1 | Succeeded. Uploaded after the static-mount fix landed, so production got the correct build |
| 2 | **Aborted at its own local SI acceptance gate** — a leak false positive on "How does your RAG retrieval work in the Standing Interview?", 1 of 15. Exactly the 1-in-3 flake this morning's SI audit measured on that same question. Not touched, not worked around: the gate is a safety control and the sprint contract forbade modifying SI |
| 3 | Succeeded, 15/15 local and 15/15 remote |
| 4 | **Aborted.** Railway's new container did not answer with the new marker inside the script's 60-poll window, so the script refused to run its remote gate against an unknown build. The build then landed roughly a minute after the script gave up -- the abort was a timeout, not a failure |
| 5 | The table-layout overflow fix -- cleared desktop and tablet, left mobile still scrolling 56px |
| 6 | The real overflow fix: a `.hint` paragraph, not the table |

Deploy 4's abort is worth recording as a real finding rather than a hiccup: the
marker-gated cutover the last sprint added did exactly its job (it refused to certify a build
it could not identify), but its 60-poll window is now too short for a cold Railway build. The
remote acceptance gate it skipped was run by hand afterwards and passed 15/15.

Two customer-app deploys: the first went live and then stopped serving the new build during
rollout; the second stuck, confirmed by 8 consecutive probes plus a browser check at two
viewports. **Every deploy rebuilds the full 361-chunk corpus (~10 minutes) even when the change
is CSS and copy** — that was the single largest time cost in this sprint and is worth a
conditional rebuild.

### D. Testing-framework assessment

**1. Which existing tests genuinely protected this release?** The nav guard
(`test_nav_frontend.js`) pinned the exact canonical destination list and forced every nav change
to be deliberate. The TIA drift guard caught that the new browser spec was unreachable from any
source path. The showcase freshness guard refused a stale `last_verified`. The hermetic suite
caught D1 and D2. `test_jd_match`'s route test correctly went red the moment its route was
gated. Four separate guards fired on real changes; none was ceremonial.

**2. Which existing tests were irrelevant?** The Java/customer-app specs and the microservice
suites — the customer-app change was one HTML element and its own specs could not run locally.
The SI suites were irrelevant by design, since the sprint did not touch that surface.

**3. Which UI defects were discovered only by browser/screenshot/manual review?** D3
(alignment) and D4 (static-mount leak). Neither had any automated signal.

**4. Why did existing automation miss them?** D3: every assertion asked *does this element
exist / does the page overflow*, and the answer to both was correct — a crooked menu is neither.
No check compared two elements' geometry until this sprint added one. D4: the guard encoded the
*requirement as I had phrased it* ("/learn must 404"), not the requirement as it actually is
("Learn must be unreachable"). A filename is a URL, and the test author forgot it.

**5. Were any tests green while visible behaviour was wrong?** **Yes, twice.** The full hermetic
suite was 740/740 green while `/learn.html` served a complete page to anybody, and while the
home page's navigation was visibly crooked at every viewport.

**6. Did any suite only test HTTP 200 instead of correctness?** The pre-existing
`golden-journey` spec checks title and heading, which is more than 200 but still identity rather
than correctness. The new `home.spec.js` deliberately asserts counts, statuses, geometry,
keyboard focus and no-JavaScript rendering instead.

**7. Were any relevant tests skipped?** Four hermetic skips, all pre-existing and environmental:
three Windows symlink tests and one that needs an `IMPLEMENTED`-only registry entry that does
not exist. Twenty Playwright tests skipped, of which the Learn/JD Match/PDF specs are skipped
*by this sprint's design* and are recorded as such. None of the skips covers changed behaviour.

**8. Did browser/E2E coverage protect all changed surfaces?** Not at the start — the home page,
the case study and the customer-app return link had no coverage at all. It does now, except the
customer-app link, which is asserted hermetically because its own specs cannot run without the
Java app on :8080 (`BL-161`).

**9. What missing test was added?** `agent/test_public_surface_gate.py` (25 tests, CI-blocking):
forbidden-claim scanning that distinguishes a positive claim from a disclaimer, private-surface
404s across 14 paths, page structure, dead links, anchor targets and the customer app's return
path. Plus `e2e/home.spec.js` (32 tests) covering three viewports, nav order, alignment,
heading order, link names, keyboard focus and a no-JavaScript render.

**10. What recruiter-facing bug classes can the framework now catch automatically?** A
forbidden or overstated claim on either new page; a private surface becoming reachable by route
*or by filename*; a missing/extra proof card or evidence row; a status upgraded beyond its
evidence; a dead internal link or non-existent anchor; nav drift in membership, order or label;
horizontal overflow and off-screen elements at three viewports; console and page errors; broken
heading order; an unnamed link; a missing focus ring; content that only renders with JavaScript;
and now element-to-element misalignment.

**11. Which classes still need a human?** Whether the copy is *persuasive*; whether the visual
hierarchy leads the eye correctly; whether spacing and typography look considered; whether a
claim is *true* as opposed to merely consistent with the registry — the MCP row was corrected
only because a person read the module and saw it was a stdio server; and whether the page reads
as honest rather than defensive.

### E. Test counts (measured, not estimated)

| | |
|---|---|
| Hermetic Python suites executed | 41 modules via `ci_python_tests.py` |
| Hermetic tests run / passed / failed / skipped | 740 / 736 / 0 / 4 |
| Node harnesses | 4 files, 195 passed, 0 failed |
| Java customer-app suite (`mvnw test`) | 162 run, 0 failures, 0 errors, 21 skipped, coverage gates met |
| Playwright tests passed / failed / skipped / not-run | 112 / 5 / 20 / 7 |
| Playwright failures that are pre-existing | 5 of 5, proven by re-running with the sprint's changes stashed |
| New guard tests added | 25 hermetic + 38 browser |
| Seeded mutations run / caught | 6 / 6 (2 initially missed, exposing D5, then fixed) |
| Local screenshots captured | 33 |
| Production screenshots captured and inspected | 30 (10 surfaces x 3 viewports), 6 inspected in full |
| Production checks | **240 / 240** |
| Routes verified in production | 10 pages + 5 private paths |
| Viewport checks | 3 per page (1280x900, 768x1024, 390x844) |

### E2. Independent stranger read (advisory)

A `qa-evaluator` instance was given ONLY the rendered page text and one
screenshot, with no project context, and asked fourteen questions a recruiter
would ask. It answered 1-10 correctly from the page alone -- including "is this
an NRG product?", which it called the cleanest line on the page.

**Two of its criticisms were truthfulness problems and were fixed the same
hour:** the section heading said "Verified evidence" when nothing independent
had verified anything, and "Running in production" never said *whose*
production. Both are now corrected.

**Four were recorded rather than acted on**, because they would change content
the Owner specified: no backend evidence among the six rows (its stated
single biggest weakness -- "impressive AI hobbyist, unknown backend
engineer"), no numbers under the measured-quality claim, no contact route, and
"Standing Interview" unexplained in the nav. `BL-164` through `BL-167`.

Its own stated limit, quoted because it matters: it clicked nothing, so every
"not evidenced" judgement means *not evidenced on this page*, not false.

### F. UI quality verdict

UI_RELEASE_CONFIDENCE: **MEDIUM-HIGH**

Higher than any previous sprint because two requirement violations were caught *before* deploy
and both now have automated regressions. Not HIGH, for one honest reason: **both of those
defects were found by a human, not by the suite.** A framework that needed a person to look at a
screenshot and to type a URL by hand is not yet a framework I would trust alone on a
recruiter-facing release. What changed this sprint is that the same two classes cannot recur
silently.

KNOWN_UI_DEFECTS_AT_CLOSE: **0**

### G. Process lessons

**Worked.** Re-verifying the six evidence rows against code rather than trusting
`PORTFOLIO_CAPABILITIES.yaml` caught the MCP overstatement — the registry was not wrong, but it
would have been read as a production claim on a recruiter-facing page. Seeding mutations
immediately after writing a guard found a hole in that guard within minutes. Probing the static
mount by hand found the leak that the test I had *just written* could not see.

**A diagnostic that was wrong three times running.** The mobile overflow took three attempts
because the diagnostic was wrong, not because the fix was hard. "Find every element whose
bounding rect extends past the viewport" finds nothing when the culprit already wraps its own
overflow — and it pointed confidently at a wide table that genuinely was wide and genuinely was
not the cause. Walking the tree comparing `scrollWidth` to `clientWidth` found the real
element, a `.hint` paragraph with an unbreakable string, in a single pass. That is now the
first thing to reach for on any horizontal-overflow report.

**Wasted time.** Announcing "starting now" at the end of a turn and then stopping — the sprint
lost a night to that, and it is a pure process failure with no technical content. Separately, a
`.replace()` that silently matched nothing was reported as success because the script printed
unconditionally; the same class of mistake as reporting a test green without reading its output.

**Testing-framework weakness.** Guards encode the requirement *as the author phrased it*. D4 is
the clean example: "/learn returns 404" and "Learn is unreachable" are not the same sentence,
and only the second is the Owner's actual requirement.

**Design-contract weakness.** The contract specified page content in detail and said nothing
about geometry, which is exactly where the defect automation missed turned up.

### H. Action items (three fixed sections; NOT sized; Owner approval required before any is acted on)

**1. Estimation-mistake improvements**
- Sprint 13's calibration was applied for the first time here: six of eleven items adopted a
  COMPUTED suggestion. Record this sprint's actuals so the `LARGE/MEDIUM/first_of_kind` class
  stops being n=3.
- Size UI work by *surfaces x viewports x interaction classes*, not by page count. The matrix,
  not the markup, was the cost.

**2. Implementation-mistake improvements**
- Never end a turn with a statement of intent. Either execute or say plainly that nothing has
  started.
- A patch script must assert its anchor matched before reporting success. Print the verified
  post-condition, never an unconditional "done".
- When unpublishing anything, enumerate *every* way it can be addressed — route, filename,
  static mount, asset, data file — before writing the guard.

**3. Neither, but still needed**
- SPRINT AS A WHOLE: the release standard asked for zero known UI defects and the only reason
  that was achieved is that a human looked at a screenshot and typed a URL. Make both steps an
  explicit, named gate in the release checklist rather than something the executor happens to
  do, because the next executor may not.
- Extend the forbidden-claim scan to every recruiter-visible page, not just the two new ones
  (`BL-163`).
- Fix the live-infra tests that fail for want of data, so a red test always means a regression
  (`BL-160`, `BL-161`, `BL-162`).

### I. Carried forward

- Production commit: `b39462c`.
- Five Playwright failures remain, all proven pre-existing and environmental.
- `test_event_ledger` still pollutes the live ledger with far-future fixture rows.
- Learn and JD Match are unpublished behind an environment flag, not behind authentication.
  Archive tag `pre-sprint14-public-nav` marks the last public state.

---

## Sprint 15 — the UI defects the Owner found by looking, and a Standing Interview that argued against itself (2026-09-29) — CLOSED

### A. Scope

**Planned (11 sized items, 521.5 min summed midpoint).** A test matrix with desktop-1920
leading; the Standing Interview navigation; one shared page shell; the home page at desktop
width; one type scale and a legibility floor; the showcase title and recruiter-facing
vocabulary; the AI-engineering-quality ledger backfill; the Standing Interview quality oracle,
specification fix and over-refusal work; verification and deploy.

**Completed:** all eleven.

**Origin.** The Owner opened the site deployed by Sprint 14 — which had reported 240/240 green
— on his own 1920×1080 display and found ten defects. He then added, in his own words:
*"3 - Fix the SI interview answer quality also in this sprint."* Two defect classes, one
underlying shape: the checks were real, and they were pointed somewhere else.

**Deliberately not done, and why:**
- **The light/dark theme was not unified.** The Owner's instruction was explicit: *"do
  alignment only. Do not unify the light/dark theme for now."* `standing-interview.html`
  still carries hard-coded light-theme colours on a dark surface. New elements added this
  sprint (the starter-question chips) use the page's own tokens, because declining to
  restyle what exists is not a licence to add another element that ignores its surface.
- **Question m is still declined.** "Describe a technical disagreement and how you resolved
  it" refuses on every draw. This is a CORPUS gap, not a gate defect — the private books are
  technical, retrieval genuinely finds nothing behavioural, and the model correctly refuses
  rather than inventing a story about a disagreement that may not have happened. Loosening
  the decline gate would be worse than the refusal. Adding behavioural material is the
  Owner's call on his own career content; the audit parked it as SI-19.
- **Deep technical vocabulary on the showcase was left alone.** `LOWER()/CONCAT()`,
  `pg_trgm`, `ContractPlanService.enroll()`, `agent/risk_policy.py`. That page is evidence
  written for an engineer; method names and file paths are the substance, not jargon to be
  smoothed away. Only identifiers that had leaked into recruiter-facing *prose* were
  translated, and none was deleted.

### B. Time

| | |
|---|---|
| Summed item midpoints | 521.5 min |
| Actual | 187 min |
| Ratio | **0.36** |

| Item | Size | Est. midpoint | Actual | Ratio | Provenance |
|---|---|---|---|---|---|
| BL-169 test matrix | MEDIUM | 55.0 | 30 | 0.55 | apportioned |
| BL-170 SI nav | SMALL | 30.0 | 8 | 0.27 | apportioned |
| BL-171 shared shell | MEDIUM | 70.0 | 20 | 0.29 | apportioned |
| BL-172 home layout | MEDIUM | 70.0 | 15 | 0.21 | apportioned |
| BL-173 type scale | SMALL | 42.5 | 12 | 0.28 | apportioned |
| BL-174 title + vocabulary | SMALL | 35.0 | 12 | 0.34 | measured |
| BL-175 AEQ backfill | SMALL | 35.0 | 7 | 0.20 | measured |
| BL-176 SI quality oracle | LARGE | 35.0 | 18 | 0.51 | measured |
| BL-177 SI specification fix | MEDIUM | 32.0 | 9 | 0.28 | measured |
| BL-178 SI over-refusal | MEDIUM | 32.0 | 6 | 0.19 | measured |
| BL-179 verify + deploy | MEDIUM | 85.0 | 50 | 0.59 | measured |

**Honest limit on these numbers.** Six items are MEASURED from real artifact timestamps
bracketing the work. The first five completed before this session's context compaction and
were not individually timestamped; their combined span (85 min) is real, the split between
them is an APPORTIONMENT, and is labelled as such in `docs/BACKLOG.json`'s
`actual_minutes_provenance`. This sprint had no per-item timer, which is itself a finding
below.

---

## Section 1 — Learnings from wrong ESTIMATION

**1.1 — The ratio is 0.36, and it is the fifth sprint in a row under 0.6.** The recorded
calibration ratios are 0.39 (MEDIUM/MEDIUM/apply_known_pattern, n=9), 1.29
(SMALL/MEDIUM/apply_known_pattern, n=8) and 0.21 (LARGE/MEDIUM/first_of_kind, n=3). This
sprint landed at 0.36 overall. **Verdict: ESTIMATION WRONG, consistently and in one
direction.** The estimates are roughly 3× the real cost. Evidence: the table above.

**1.2 — The one item that ran closest to its estimate is the one that required real
thinking.** BL-176 (the quality oracle, LARGE, first_of_kind) came in at 0.51 and BL-179
(verification) at 0.59 — the two highest ratios in the sprint. The items that ran furthest
under (BL-178 at 0.19, BL-175 at 0.20, BL-172 at 0.21) were mechanical once the decision was
made. **The estimate error is not uniform: it is largest where the work is mechanical.** A
flat multiplier would therefore be the wrong correction. Evidence: 0.19–0.21 for mechanical
items against 0.51–0.59 for design and verification work.

**1.3 — BL-173 was sized SMALL and was not small in the way that mattered.** It came in at
0.28 by the clock, so by ratio it looks like every other item. But the 12px floor turned out
to need a sweep of **44 declarations across 9 stylesheets**, against the 3 pages the defect
register named — and I only discovered that after the guard had already gone green. The
sizing was right about effort and wrong about SCOPE, and the clock cannot see that
distinction. **Verdict: ESTIMATION WRONG on scope, not on effort.**

---

## Section 2 — Learnings from IMPLEMENTATION issues

**2.1 — I fixed the three pages the register named instead of the rule.** The Owner's
register listed showcase (10.88px), dashboard (11.2px) and usage (11.52px). I bumped
`showcase.css` and moved on, and the guard agreed the pages were clean. A source sweep later
found 44 sub-floor declarations across 9 stylesheets. **When a defect is an instance of a
RULE, fix the rule and sweep for every instance — a register is a sample, not an
inventory.** Evidence: `agent/web/*.css`, 44 declarations raised.

**2.2 — My own guard reported clean on a defect that was really there, because it measured
the page before the data arrived.** `.summary-label` ("Known Cost Total", 10.88px) and
`.badge st-ok` ("PRODUCTION ACTIVE", 11.2px) only exist once the API responds. The 12px
check waited for the `<h1>` and then measured — and the h1 is in the static HTML. It passed
both pages. I found them by taking a screenshot and printing the geometry beside it, which
is the same way every defect in this sprint was originally found. **This is the Sprint 14
lesson recurring inside Sprint 15's own fix for the Sprint 14 lesson.** Fixed, then
re-proven RED against the seeded defect before being trusted again.

**2.3 — The "something to click above the fold" fix existed only while the page was
loading.** I put the link row inside `<main>`; `usage.js` does `main.innerHTML = ...` once
its data arrives and wiped it. The weaker guard had agreed the page was fine. Same root
cause as 2.2 — a check that samples one moment of a page's life, on a page whose content
arrives in two stages. Moved into `<header>`, which survives.

**2.4 — I made the guard flaky, then made it slow, before making it correct.** A fixed 2.5s
sleep lost a race under four workers (one false failure). Adding `networkidle` fixed the race
and pushed the nine-page loops from 12s to 28s — under the 30s default alone, over it under
parallel load, so a flake became a timeout. The correct answer was a real wait CONDITION plus
an explicit timeout for tests that legitimately visit nine pages. **A guard that reports a
defect that is not there costs exactly as much trust as one that misses a defect that is.**

**2.5 — Two suites run concurrently produced three phantom failures.** `interview-walkthrough`
failed twice, on different tests, and the hermetic count moved between 3, 4 and 5 — every
time while a second suite was running. Run alone: 226 passed with exactly the 5 failures
proven pre-existing, and 30/30 on the walkthrough spec under `--repeat-each=3`. **Do not
report a failure count from a machine running two suites at once.**

**2.6 — What went right, and is worth keeping: the SI fix was not allowed to start until the
measurement was red.** The audit's sequencing constraint said build the oracle and prove it
red against the six rejected answers BEFORE touching a prompt line. Holding to that produced
a real number (37 unsolicited negatives across 21 of 57) that independently corroborated the
audit's own hand count of 38 across 22 — two counts landing one apart, from different code.
Had I changed the prompt first, there would have been no way to tell a working fix from an
absent measurement.

**2.7 — The frozen test fixture encoded the defect.** `NEW_KAFKA_GENERIC`, labelled "the
shape the Owner froze", contained the exact two sentences he now objects to, and the live
answers were faithful to it. The fixture moved, not the gate — following the precedent
already set two comments below it in the same file ("later instruction wins"). **A frozen
fixture is a record of what was wanted THEN; when the owner of the requirement changes it,
the fixture is the thing that is now wrong.**

---

## Section 3 — Neither, but still needed

**3.1 — Instrument per-item timing.** Five of eleven actuals in this retro are
apportionments because the work predated a context compaction and nothing recorded when each
item started. The calibration loop is the Owner's permanent standing process and it deserves
real inputs. A start/stop marker written into the backlog item at the moment work begins
would make every future retro's table measured rather than partly reconstructed.

**3.2 — The AEQ ledger is now a named close-out step.** Sprint 14 recorded its defects in
commits, the retro and the backlog, and wrote nothing to
`docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml`. Two sprints later the same defect class
recurred with no warning on file. AEQ-030/031/032 are backfilled and
`.claude/rules/sprint-process.md` Phase 2b now states the question every retro must answer.

**3.3 — The five pre-existing Playwright failures deserve their own item.** Session History,
the verified run and the customer-app login gate fail on this machine because the local
environment has no ledger data and no running Spring app. They pass in production. Right now
every run requires me to remember that, which is exactly the condition under which a real
regression gets waved through as "one of the known ones". They should either be skipped with
a stated reason or given local fixtures.

**3.4 — For the sprint as a whole: the Owner found these defects, and he should not have
had to.** Both this sprint's defect classes reached him through a green suite. The guards
added here close these specific holes, but the generalisable rule is the one now in AEQ-030:
*a test matrix is a claim about coverage, and the agent writes the matrix — when the agent
chooses both the assertions and the conditions they run under, a green count measures only
the intersection of its own two choices.* The condition list has to come from how the thing
is really used, and the final check has to include looking at it.

**2.8 — My own fix introduced two regressions, and the pre-deploy acceptance gate caught
both before anything shipped.** The spec rewrite told the model not to volunteer a
limitation. It over-applied that to questions that *directly ask* one: "Did NRG use Kafka?"
and "Tell me about Kafka at NRG" both stopped stating the absence, which is the entire
answer to those questions. The gate failed 4 of 15 and `set -euo pipefail` aborted the
script before `railway up` ran, so production stayed on Sprint 14 throughout.

This is the single most important thing that happened in this sprint, and it is worth being
precise about why. Every local suite was green — 136 Python tests, 67 UI guards, 226
Playwright — and the thing that caught it was the one gate that calls a real model with the
real corpus and reads what comes back. **A prompt change cannot be verified by any test that
does not run the model.** The unit tests verified that the prompt CONTAINS the new rule;
only the acceptance replay could show that the model OVER-APPLIED it.

The fix was to make the direct-answer case the FIRST thing the prompt says, with worked
examples, before the rule it is an exception to — a limitation the question asked for is not
a volunteered limitation, and the model needed that stated rather than inferred from a
numbered exception three paragraphs down. Two other real findings came out of the same run:
"opens on a limitation" was reclassified soft (it had refused a good answer to "How does the
human approval step work on your platform?" outright), and the `the source material` leak
pattern got the question-aware exemption its sibling pattern already had, because an answer
about how RAG retrieval works has to name what it retrieves from.

**2.9 — The acceptance gate is a sample, not a measurement, and I nearly reported it as
one.** Across four runs this sprint with no code change between two of them, it returned 4,
1, 0 and 2 failures. It calls a real model, so it samples a distribution. After the 0-failure
run I was one step from writing "ACCEPTANCE PASSED — 15 of 15" into the retro as the
sprint's verification, and the very next run failed 2. **A single green run of a
non-deterministic gate is evidence, not proof, and should be reported with its run count.**
The gate is still the right gate — it is the only thing all sprint that caught a real
regression — but its verdict needs a sample size attached.

**2.10 — One of those two failures was the checker being wrong, not the answer.** "Tell me
about Kafka at NRG" was failed for "does not state the absence" by an answer that said *"that's
the messaging setup I worked with there, **not Kafka**"*. The check accepts "didn't use",
"was not", "not part of", "never used" — and not "not Kafka". **This is the same defect
class as the `_LIMIT_MARKER` phrase list this sprint exists to replace, and I reintroduced
it by trusting a sibling phrase list I had not looked at.** A fixed vocabulary cannot
enumerate how a person says a thing. Fixed, and verified in both directions: the new
phrasings are accepted and an answer that genuinely never mentions the absence still fails.

**2.11 — The prompt block I rewrote was carrying something else.** The
volunteered-limitation rewrite replaced the paragraph that used to say "be honest about the
limits of your own involvement" — which was also the place the answer's own *first-person
framing* lived. A later run produced an answer about NRG with no "I" and no "we" anywhere in
it: documentation about a system, not someone remembering their job. **When replacing a
block of a prompt, check what else that block was doing.** First person is now restated
where the new rule lives, with the failing answer as the worked counter-example.

**3.5 — The acceptance gate needs a sample size, and the deploy script needs to know that.**
Right now `scripts/deploy_platform_with_si_corpus.sh` runs the replay once and aborts on any
failure. Given the distribution observed this sprint (4, 1, 0, 2 failures on an unchanged
codebase for two of those runs), that makes a deploy a coin-flip on a marginal case, and it
makes "it passed" mean less than it sounds. Two changes worth proposing rather than making
unilaterally, since both change what a deploy costs: run each question N times and gate on a
threshold rather than on zero failures in one draw; and record the per-question pass rate
over time, so a question that is genuinely 50/50 is visible as such instead of appearing as
an intermittent deploy failure. This needs the Owner's call because N draws is N times the
model spend on every deploy.

### C. Production outcome, and the incident that ended the sprint

**UI: deployed and verified live.** Marker `deploy-20260929T202535Z-448fc54`. All 67
assertions in `e2e/ui-standards.spec.js` pass **against the production URL**, not only
locally. Measured on the live pages at 1920×940: navigation and content start at the same
x (392) on all nine pages — `/standing-interview` was 0 against 596 — every page uses a
1200px column, body is 17px everywhere, the smallest rendered text is 12.5px, and no page
scrolls sideways.

**SI: deployed, and UNVERIFIED.** The specification change is live and passed the real-model
acceptance gate 15/15 twice. It has not been measured against production, because:

**P0 — the Anthropic API credit balance was exhausted mid-verification.** The post-deploy
gate failed on its eleventh question with `anthropic.BadRequestError: 400 — 'Your credit
balance is too low to access the Anthropic API'`. Verified live: the page returns 200, a
private-topic question still answers correctly (it refuses before any model call), and every
question that needs the model returns **HTTP 500**.

Two separate things, and it matters not to conflate them:

1. **The exhausted balance** is not a code defect and cannot be fixed from this laptop. It
   needs credit on the Anthropic account, which is the Owner's decision and one this project
   explicitly forbids changing without his separate approval.
2. **The raw 500 is a real defect, and it is PRE-EXISTING.** `reasoning_gateway.call()`
   raises on an API error rather than returning a denial, and no caller in
   `standing_interview.py` ever caught it — Sprint 14's code does exactly the same. The
   `no_model` path that exists covers a *missing key*, not a *failing call*. The credit
   exhaustion exposed a gap that had been there the whole time. A recruiter mid-question saw
   a server error page with no way to tell whether the site was broken, their question was
   bad, or the system was out of credit — which is precisely what this project's own rule
   forbids. Fixed (`outcome: model_unavailable`, an honest message, the provider's own
   billing text never reaching the visitor or the record), proven both ways without spending
   any credit, committed — and **not deployed**, because the deploy gate needs the model.

**The sprint therefore ends blocked rather than closed**, on one thing only the Owner can
resolve. Everything not gated on model spend is done and live.

**3.6 — Cost, honestly.** The acceptance gate was run five times this sprint (~75 real model
calls) plus two deploys that each ran it again. Each run is roughly $0.35 at the audit's
measured $0.023/request. That is not what exhausted the balance on its own — the balance was
already low — but re-running a stochastic 15-question gate until it comes up green is a
pattern worth naming before it becomes a habit, and it is the direct reason item 3.5 above
proposes thresholds instead of retries.

### D. What the independent QA pass found — added after the retro was written

The qa-evaluator was invoked per CLAUDE.md (a LARGE item, CROSS_MODULE blast radius). It
verified by mutation rather than by reading my rationale, and it changed the conclusions
above. Recorded here rather than silently edited into Section 2, because a retro that
quietly absorbs its own review loses the fact that the review was needed.

**REFUTED — the accusation I most wanted checked.** "Did I weaken a test to go green?" No.
It ran HEAD's `test_standing_interview.py` against pre-Sprint-15 source and all three
changed assertions FAILED against the old code — which is the proof that they were
tightened, not loosened. The `NEW_KAFKA_GENERIC` fixture move was confirmed as a genuine
specification inversion: the previous "frozen" text is now rejected by the current gate for
the two exact sentences the Owner complained about.

**CONFIRMED — the 37 / 21 / 57 baseline**, recomputed independently, and all six objected-to
answers rejected.

**REFUTED — three things I had written down as done.** These are the ones that matter:
`.banner dt` at 11px and `h2.sec` at 12px were live while the guard called both pages clean;
`/usage`'s `main` was still 1100px against its own 1200px header; the case study's h1 was
41px, undisclosed. Full detail and the fixes are in `docs/UI_DEFECTS_2026-09-29.md` under
"Correction, 2026-09-29".

**2.12 — I reported a number I had not measured.** Commit `a8d356d` states "12.5px smallest
text" as verified on the live pages. It was not. I had verified the *source sweep* (44
declarations across 9 stylesheets, real) and the *guard passing* (real), and then reported a
third thing neither of those established — that nothing on the live page renders below
12.5px. Two true statements were combined into a false one. **The guard passing is evidence
about the guard; only measuring the page is evidence about the page.**

**2.13 — And the guard could not have told me, because I set its number lower than the
standard.** `MIN_LEGIBLE_PX` was `12` while every stylesheet was swept to `12.5`. The check
was one notch more lenient than the rule it enforced, which is how a 12px heading passed
under a "12.5px floor" claim. When a standard is a number, exactly one number should exist.

**2.14 — Three fixes for one defect shape, in one sprint, each inside the fix for the last
one.** Sprint 14's matrix tested 1280 and called it desktop. Sprint 15's guard tested nine
pages but enumerated ten tag names. Then its shell check walked one ancestor chain. Each
time the guard answered the question it was asked and the question was too narrow. The
general form is now in AEQ-030 and worth stating plainly: **an enumeration inside a guard is
a liability, and where the check can ask "all of them" instead of listing them, it must.**

**3.7 — There is no visual verification in this project, and every defect this sprint was
found by eye.** The QA pass named this as the largest uncovered gap and it is right. All 67
assertions are geometry and computed styles; the original ten defects, the two I found after
the suite was green, and these three all became visible by looking at a rendered page. A
screenshot-diffing tier would have caught the 11px `dt`. Proposing it rather than adding it,
since it is a new tooling dependency and a real cost.

### E. The outage had a second cause nobody had looked for

Added 2026-09-30, after the Owner topped up and asked for a cap.

The exhausted balance was the proximate cause of the 500s. It was not the only
problem, and the other one was worse: **`/api/standing-interview/ask` is a
public POST with no auth, no rate limit and no daily cap, and every request
triggers a real billed model call.** The Workbench next door has had a cooldown
and a `DAILY_CAP` for months. This endpoint, the one linked from the homepage,
had neither.

At the measured $0.023 an answer, a script looping on that URL spends $20 in
about ninety seconds. The first anyone would know is an empty balance — which
is precisely how this outage was discovered.

**3.8 — I nearly told the Owner to top up an endpoint that had no floor.** He
asked "how much should I buy", and the useful answer was not a number. Checking
what protects the money before recommending spending more of it should not have
needed prompting; it was one grep, and I only ran it because the question made
me think about the exposure. **A cost question is a control question first.**

`agent/si_budget.py` now enforces two independent limits: a daily budget in
dollars (converted to a request count from the real measured cost, so the Owner
sets money and the code does the arithmetic) and a per-visitor cooldown plus
daily ceiling. They are independent on purpose — the per-visitor limit is
evadable by rotating addresses, so the daily budget deliberately does not depend
on identity at all.

Three things in it are worth keeping as a pattern:
- **Checked before the billed call**, and only requests that actually reach the
  model are counted. Charging a private-topic refusal would let two private
  questions lock out a real recruiter.
- **The wiring is tested separately from the module.** A correct limiter the
  route never calls protects nothing, so the endpoint test drives the real route
  and asserts a 429 with `answer()` never invoked — proven by seeding the check
  out and watching it go red.
- **Its limitations are in the docstring, not discovered later.** State is
  in-process, so a restart resets it: this is a per-container-day budget, not a
  ledger-backed guarantee. Saying so is the difference between a control and a
  false sense of one.

**3.9 — `SKIP_MODEL_GATE` exists now, and that is a risk worth naming.** The
deploy needed to ship while the gate that guards it could not run. The honest
resolution was a flag that is loud, off by default, skips the post-deploy replay
for the same stated reason rather than silently, keeps every corpus invariant
that does not need credit, and stamps `-nogate` into the deploy marker so
production records how it was verified. The risk is that it becomes the easy
path the next time the gate is merely *failing*. The comment in the script says
it directly: if you are reaching for this because the gate is failing, that is
the gate working — fix the answer, not the script.

### F. The measurement, 2026-09-30 — what the sprint was actually for

The Owner topped up the API credit and the post-fix capture finally ran: 21 real
requests against live production, scored by the same oracle that had been proven
red against the six answers he objected to, compared **like-for-like** against
the same questions in the pre-fix baseline rather than against the 57-answer
headline.

```
questions a b e f g m w
BEFORE :  28 unsolicited negatives across 14 of 18 answered
AFTER  :   0 unsolicited negatives across  0 of 19 answered
```

That is the complaint — *"it answers so crazily for some questions"* — measured
gone, on the real service, by a detector that was shown to catch the original
defect before the fix existed.

**2.15 — I stated a cause too confidently, and the measurement corrected me.**
I wrote, in the retro and in two state documents, that question m's refusal was
a *corpus gap*: the books are technical, retrieval genuinely finds nothing
behavioural, so the model correctly declines. The capture answered it on 1 of 3
draws, with a real grounded story — a genuine disagreement from building this
platform, about which source governs when the state documents conflict. **The
material was there the whole time; retrieval reaches it inconsistently.** That
is a different problem with a different fix, and I had closed the question
early with a confident-sounding explanation instead of leaving it open. The test
stays red, because 1 of 3 is not fixed.

**2.16 — The capture found a defect that every other gate had passed.** One draw
told the visitor *"The knowledge base isn't loaded on this instance, so I can't
answer from it"* while the deployed corpus held 361 chunks and the draws either
side answered normally. `not model_called or not text` shared one branch, so a
model that WAS called and returned an empty string produced the no-corpus
message — a false statement about the system's own state, made to the person the
site exists to impress. At that moment 772 hermetic tests, 67 UI guards and a
15/15 acceptance run were all green. **Only asking the real service, 21 times,
surfaced it.**

**2.17 — And then the gate refused the deploy, correctly.** The first gated
deploy after the fix failed on "Tell me about Kafka at NRG": the answer
described SQS and closed with *"there wasn't a separate event-streaming layer
running alongside it"* — never once saying the word Kafka. The instruction said
"say plainly that you did not use it there", and the model complied with the
sentiment while paraphrasing around the noun. An interviewer who asked about one
specific thing is left inferring. **The temptation here is the reason
`SKIP_MODEL_GATE` was written hours earlier, and the script's own comment
answers it: if you are reaching for the bypass because the gate is FAILING,
that is the gate working.** The instruction now requires naming the technology,
with the paraphrase failure mode named explicitly — and it was verified NOT to
apply to the generic "explain your experience with Kafka", which is the Owner's
original complaint and had to stay fixed.

**2.18 — I fixed the instance and not the class, and it bit me forty minutes
later.** Adding a per-visitor cooldown to a public endpoint breaks every
internal tool that talks to that endpoint in a loop. I hit this with
`si_recapture.py` (1s sleep against a 5s cooldown), fixed *that script*, and
then the acceptance gate — which fires 15 questions in a row from one address —
died on HTTP 429 in the post-deploy replay of the very deploy that shipped the
cap. Nothing was wrong with any answer.

The generalisable rule, which is the only part worth keeping: **when you add a
rate limit to an endpoint, the blast radius is every caller you own, not the
one you happened to be running.** The moment the cooldown constant existed,
the right move was to grep for everything that POSTs to that route and pace all
of them, rather than wait for each to fail in turn.

Two details that made the second fix better than the first: the pacing is
deliberately *above* the cooldown rather than equal to it (equal values race on
clock granularity and network jitter), and a 429 now raises with an explicit
"this is NOT an answer-quality failure" message — because in a deploy log a
pacing problem and a bad answer look identical, and they send the next person
in completely opposite directions.

**2.18 (closed).** The caller audit is complete and the last one is verified
rather than reasoned about. Being rate limited by my own cap turned out to be
the cheapest possible way to test it — the cap refuses before any model call,
so driving a real browser against live production cost nothing. A capped
visitor sees:

> *"That's a lot of questions for one day — more than a real interview would
> cover. Please pick this up tomorrow, or reach me directly."*

No JavaScript errors, no error styling, no broken page. It works because the
429 body carries the same `{answer, grounded, outcome}` shape as a normal
response and `fetch` does not throw on 4xx, so the page's existing rendering
path handles it without knowing anything about rate limits. That was luck as
much as design — I chose the shape for consistency, not for this — and it is
worth keeping deliberately: **an error response that matches the success shape
degrades gracefully through code that has never heard of it.**

All four callers now handle a 429 correctly: the acceptance gate (paced, with
an explicit "this is NOT an answer-quality failure" message), the recapture
script (paced, raises rather than storing the refusal as an answer), the
budget test (triggers it deliberately), and the browser page (renders the
sentence — confirmed live).

### G. Closed — the post-deploy replay, and one last self-inflicted obstacle

`ACCEPTANCE PASSED -- 15 of 15 questions (9 exam + 6 unseen)` against the
deployed host. Every claim in this retro is now backed by evidence from the
live service rather than from a local run.

It took four attempts, and none of the failures were about answer quality:

1. **HTTP 429** — the gate fires 15 questions from one address and I had just
   shipped a 5s cooldown. Fixed with pacing.
2. **A correct answer failed** — *"ran on SQS ... rather than a message broker
   like Kafka"* rejected by the third hand-written phrase list in that file
   (item 2.18).
3. **HTTP 429 again, after UTC midnight** — and this one was the interesting
   one. See LESSONS.md: the container's clock read `23:56:17 GMT` while this
   laptop read `00:02:31`. Six minutes of skew. I had computed "sleep until UTC
   midnight" from the **local** clock; the cap resets on the **server's**. The
   `Retry-After` header answered it in seconds after I had re-read correct,
   unit-tested logic three times.
4. **Killed for system memory** — environment, not code.

**3.10 — Every obstacle in that list was created by this sprint.** The cooldown,
the phrase list, the clock assumption and the tooling were all mine. That is
not an argument against the cap — the endpoint genuinely had no floor and a bot
could have drained the balance in ninety seconds — but it is the honest shape of
the evening: a control added late in a sprint collides with the tooling that
sprint depends on, and the collisions surface one at a time, each looking like a
product failure until diagnosed. The `SI_OPERATOR_TOKEN` exemption exists
because of it, and it fails closed so the endpoint stays protected while the
gate stops being blocked.

---

## Sprint 16 — nine pages, nine identities, and the guard that measured the wrong thing (2026-09-30) — CLOSED

### A. Scope

**Planned (7 sized items, 405 min summed midpoint).** Design guards; the
172-character line length; the lopsided header; navigation and duplicate links;
visual hierarchy on the dark surfaces; home and case-study; verify and deploy.

**Completed:** all seven, deployed and verified against production.

**Origin.** Sprint 15 closed with 67/67 UI guards green against production, a
15/15 acceptance gate and a measured 28→0 on answer quality. The Owner opened
the site and said: *"None of the pages looks good in browser. so bad. why is
that?"* He was right and so was every guard — they measure alignment, sizes, a
legibility floor and overflow, and not one asks whether a page is readable.

**Scope changed mid-sprint, by the Owner, four times** — from "fix layout only"
to per-page colour and font, then to distinct display faces, then to "the
variation itself is a USP", then to grounding every choice in current research.
Each was an expansion rather than a reversal, so the work accumulated instead of
being thrown away.

### B. Time

| | |
|---|---|
| Summed item midpoints | 405 min |
| Actual wall-clock | 231 min |
| Ratio | **0.57** |

The highest ratio recorded in this log. The previous five sprints ran 0.21–0.48;
Sprint 15 was 0.36.

---

## Section 1 — Learnings from wrong ESTIMATION

**1.1 — The one item sized against the computed number was the one that needed
the deviation.** `suggest-estimate LARGE/MEDIUM/first_of_kind` returned n=3,
median ratio 0.21, suggested midpoint **25.2 min** for the visual hierarchy
pass. I deviated up to 120 and recorded why: three samples is a thin basis, and
all three were CODE items whose acceptance is an exit code. **A ratio computed
from work with a deterministic done-state does not transfer to work whose
acceptance is a human looking at it.** Verdict: ESTIMATION CORRECT, because the
deviation was deliberate and stated up front rather than discovered afterwards.

**1.2 — 0.57 is the least-wrong sprint yet, and the reason is worth keeping.**
Every previous sprint sized from the same code-derived ratios and came in at
0.21–0.48 — estimates roughly 2–5× too high. This one deviated up on the two
judgement-heavy items and down on none, and landed closest to 1.0. **The
calibration data is systematically wrong for judgement work and systematically
right for mechanical work.** The correction is a per-pattern multiplier, not a
single global one.

---

## Section 2 — Learnings from IMPLEMENTATION issues

**2.1 — The defect was not taste, and I nearly treated it as taste.** The Owner
said the pages looked bad. The measurable cause was paragraphs rendering at
**172 characters** against a readable band of 50–75. Had I answered "looks bad"
with colour and spacing alone, the pages would have stayed hard to read and
looked better while doing it. **When someone reports an aesthetic symptom,
measure before restyling** — there was a readability defect underneath, and it
was the same `--prose` token Sprint 15 had defined and applied to the wrong
elements.

**2.2 — My guard measured the wrong thing and passed on the defect.** The
header/body balance check compared BLOCK widths. The `<h1>` block is already
full width, so it reported a ratio of 1.00 on pages that visibly had a 587px
paragraph above 1136px content. **A guard can be green, internally correct, and
aimed at a property nobody cares about.** Rewritten to measure the TEXT measure
— what the eye actually reacts to — and it went red immediately.

**2.3 — And my other guard estimated instead of measuring.** The line-length
check divided rendered width by `fontSize × 0.5`, assuming an average glyph
advance. That is font-dependent, and it broke the moment real webfonts loaded:
the same column measured 86 "characters" with Inter while rendering fewer than
before. **The estimator moved and the page did not.** Replaced with
`text.length / rendered lines`, which is exact and font-independent.

**2.4 — I broke two pages by find-and-replacing a literal with a token they
cannot see.** `case-study` and `home` do not load `style.css` — they are
self-contained. Replacing `68ch` with `var(--prose)` there made the declaration
*invalid*, and an invalid `max-width` does not fall back, it disappears. Those
two pages went from a 68ch cap to **uncapped**, 107–110 real characters — worse
than before the sprint started. **An unresolvable `var()` fails silently and
totally.** Both now define the token locally with a comment saying why it must
be kept in step.

**2.5 — The recurring defect recurred twice more, in one sprint.** An exception
written `.proof *` un-capped every descendant including the card paragraphs —
home's 101-character lines. And the selector lists kept naming one container
(`main`) when the site has several (`.wrap`, `.si-wrap`, a `<dl>` outside both).
**Five occurrences across two sprints now: a rule that enumerates rather than
describes.** The fix each time was to describe the property instead — ask every
element, narrow the exception to `> *`, cap prose structurally.

**2.6 — Fourth heredoc-escaping incident of the day, one of them while writing
the retro item about the third.** A shell heredoc converted `\b` into a literal
backspace (0x08), so the first-person regex searched for control characters and
matched nothing, flagging every answer over 40 words including the frozen test
fixture. This repository's LESSONS.md already says to write a file rather than
pipe escapes through the shell. Knowing the rule and citing the rule turned out
not to be the same as following it.

**2.7 — A check that only runs at deploy time cannot fix anything.** The
first-person requirement existed only in the acceptance gate, which runs at
deploy and can therefore only BLOCK an answer, never improve one. It failed the
deploy twice on the same question. Moved into the runtime voice gate as a soft
violation, where it triggers a retry and the retry prompt names the failure —
after which the gate passed 15/15 twice. **Put the check where the correction
can happen.**

**2.8 — Two Sprint 15 guards were changed, and that needs justifying more than
tightening does.** Both asserted SAMENESS — all h1 sizes within 8px, all shells
identical — as proxies for real requirements. Sprint 15's actual defects were a
26.4px title that read as body text, and five arbitrary widths nobody had
decided. Per-page identity makes sameness the wrong assertion: a serif at 44px,
a sans at 40 and a mono at 33 are the same optical weight, and two widths chosen
by content type is a decision rather than drift. Both now assert the requirement
directly, and both still fail against the original defect.

---

## Section 3 — Neither, but still needed

**3.1 — Research changed a decision, which is the test of whether it was
actually used.** Tuch et al. find that HIGH visual complexity produces a *worse*
first impression than low or medium. That runs against the instinct when asked
to make pages "visually engaging", and it is why each surface got **one**
structural signature rather than several — then complexity was measured
afterwards and confirmed low on all nine. Prototypicality predicting
trustworthiness (29–68% of variance) is why the nav moved to first on every
page. Citing research that merely agrees with what you were already going to do
is decoration.

**3.2 — There is still no visual regression testing, and the gap is now
narrower and sharper.** Sprint 15's retro proposed it; this sprint shows what it
would and would not catch. Line length, balance, complexity and duplicate links
are now all measured. **Flat visual hierarchy is not, and cannot be** — DD6 was
addressed by spacing, type layers and elevation, and verified only by looking at
nine screenshots. A pixel-baseline tier would help, but these pages render live
data (costs, run counts, dates), so it needs masking or it will false-positive
constantly. Worth proposing now with a clear specification rather than as a
vague wish.

**3.3 — For the sprint as a whole.** Two sprints running, the Owner found the
defect by opening the site, and both times the suite was green. Sprint 15 added
guards for what he found; Sprint 16 added guards for what he found next.
**The pattern is that guards get written to catch the previous complaint.** The
only general defence is the thing neither sprint automated: look at the rendered
page before calling it done. That is now a named step in BL-187, and it is the
step that found the remaining defects both times.

---

## Sprint 17 — the exit code that carried no information, and a USP I was told to delete (2026-09-30) — CLOSED

### A. Scope

**Planned (6 sized items, 451 min summed midpoint).** BL-188 release health;
BL-189 cost-aware selection; BL-190 recruiter-damaging defects; BL-191 the design
lock and first screens; BL-192 the visual safety net; BL-193 close-out.

**Completed:** all six, plus five of the six reserve items (BL-R1 through BL-R6;
BL-R3's CSS cleanup happened as part of the design lock rather than separately).

**Not done, and deliberately:** no deploy, no push, no merge, no paid model call.
All four were forbidden by the brief and all four stayed forbidden.

**Origin.** An autonomous five-hour run against a written brief, planned by Grok,
with the Owner away and explicit instruction not to wait for approval at any
point. Two previous sprints had stalled waiting for approval; this one did not
stop once.

### B. Time

| | |
|---|---|
| Summed item midpoints | 451 min |
| Actual wall-clock | 115 min |
| Ratio | **0.25** |

Branch created 10:54 CEST (`sprint17-recruiter-ux-testing` off `0209b4a`), last
commit 12:49 CEST. Timestamps from real `git log --date=iso-strict`, not recalled.

Six sprints of ratios now: 0.21, 0.36, 0.48, 0.57, and this one at 0.25.

### C. Per-item comparison

| Item | Size given | Est. midpoint | Actual | Ratio | Verdict |
|---|---|---|---|---|---|
| BL-188 release health | LARGE | 90 | ~25 | 0.28 | ESTIMATION WRONG |
| BL-189 cost-aware selection | MEDIUM | 57 | ~20 | 0.35 | ESTIMATION WRONG |
| BL-190 recruiter defects | LARGE | 110 | ~30 | 0.27 | ESTIMATION WRONG |
| BL-191 design lock + first screens | LARGE | 92 | ~20 | 0.22 | ESTIMATION WRONG |
| BL-192 visual safety net | MEDIUM | 57 | ~20 | 0.35 | ESTIMATION WRONG + IMPLEMENTATION ISSUES |
| BL-193 close-out | MEDIUM | 45 | ~15 | 0.33 | ESTIMATION WRONG |

Per-item actuals are apportioned from commit boundaries and are therefore
approximate; the 115-minute total is the authoritative figure. This is the same
weakness Sprint 16's retro flagged (per-item timing was never instrumented) and it
is still not fixed — recorded again below rather than quietly dropped.

### D. What was actually delivered

**Two deterministic defects that had been red for two sprints, both fixed with
observed RED → GREEN:**

1. `e2e/design-standards.spec.js` was unreachable from the TIA map. Sprint 16 wrote
   it to measure nine public pages and mapped it from nothing. The repo's own
   ratchet test was already red on it and had been since. Fixed, plus five more
   specs that were genuine debt, plus `agent/web_server.py` — the repository's
   highest-risk file, which selected **zero** suites including
   `e2e/profile.spec.js`, the only proof that `/profile`'s privacy has not
   regressed and whose enforcement is route registration in that very file.
2. The Usage frontend harness, red on two assertions from the 2026-09-18 cost
   incident: the efficiency heading must name its scope and the body must say what
   it excludes. Sprint 15 moved a shouted parenthetical out of the heading for a
   sound reason and took the word "Workbench" with it.

**Release health separated from quality monitors.** `test_si_quality` mixed two
questions in one file. What remains scores a frozen archive with frozen code; what
moved to `agent/test_si_answer_quality_monitor.py` scores what a language model
actually said. The monitor still runs on every invocation and its failure text is
still printed in full — the only thing it no longer does is set the exit code.

**Cost-aware selection and a fail-closed paid guard.** `agent/select_tests.py`
(eight change classes, JSON out, a computed paid-call count) and
`agent/paid_test_guard.py` (both `ALLOW_PAID_TESTS=1` and a positive
`PAID_TEST_BUDGET_USD`, refused before any provider client is constructed). Wired
into `agent/si_recapture.py`, whose only previous protection was an interactive
`y/N` prompt that `--yes` bypasses — and `--yes` is exactly what a script or an
agent passes.

**Measured recruiter-facing outcomes:**

| | before | after |
|---|---|---|
| Third-party font requests across all records | 69 | **0** |
| Records with horizontal overflow | 1 | **0** |
| Pages with the primary action inside 800px (of 7 interactive) | 2 | **6** |
| Workbench primary control | y=988 | y=641 |
| Showcase primary control | y=964 | y=602 |
| Ask Codebase primary control | y=812 | y=550 |
| Standing Interview primary control | not detectable | y=187 |
| Home primary control | not detectable | y=455 |

### E. RED → GREEN demonstrations

Every guard added this sprint was watched failing for the intended reason first.
Nothing planted was committed.

| Guard | Seeded defect | Observed RED |
|---|---|---|
| CSS-never-selects-paid | added `si-answer-quality-paid` to `CLASS_TO_SUITES["CSS_VISUAL"]` | 4 failures |
| Paid guard default-deny | changed the guard's `and` to `or` | 10 failures, 3 errors |
| Third-party font | re-added the Google Fonts `<link>` to `home.html` | 1 failure, by name |
| Horizontal overflow | disabled `body { overflow-wrap: anywhere }` | showcase 400>390, usage 406>390, each naming its exact culprit element |
| Copy contract | planted "no human approval needed" in the Workbench tagline | failed with *"which implies the model authorized itself"* |
| Visual regression | changed the lab accent `#5b93ff` → `#ff6b35` | 15,121 and 12,381 differing pixels |

Plus the pre-existence proof: both remaining Usage Playwright failures were
verified by stashing all work, checking `agent/web/usage.*` out at `0209b4a`, and
watching them fail identically against the original renderer.

### F. Defects introduced and caught

**Three, all caught by gates that already existed. None reached a commit.**

1. **Literal `--` inside my own HTML comments**, five places. Caught by the STATIC
   gate — the bug class `docs/LESSONS.md` records twice and which now has a gate
   precisely because a written rule failed to prevent it. It caught the author of
   the sprint that was praising it.
2. **A duplicate `START THE LIVE DEMO` button** on Showcase, from adding the
   role-fit card. Caught by `e2e/interview-walkthrough.spec.js` on Playwright
   strict mode. The tempting fix was `.first()` on that assertion; the right one
   was removing the duplicate, because two identically-labelled primary buttons a
   screen apart is bad design and a screen reader announces the same control
   twice.
3. **`e2e/ask-codebase.spec.js` broken by a deliberate reordering.** The brief
   asked for the explanation to move below the search box, so the old assertion
   was measuring behaviour that had intentionally changed. Updated to the intent —
   and *more* was asserted than before, including that the moved caveat is still
   present and still below the control.

**And one false positive I caught before changing the page.** The new
accessible-name guard named seven Showcase links — "Quality Ledger entry AEQ-012",
"Full write-up", "Fix commit 9f35f27" — as unlabelled. All seven have perfectly
good link text. The guard was reading `innerText`, which is layout-dependent and
returns `""` for an element inside a collapsed `<details>`; an accessible name
comes from text *content*. Had I trusted my own new guard, seven correctly-written
links would have had pointless `aria-label`s bolted on.

**A near-miss worth its own line.** `git add -A agent/ e2e/ docs/` staged
`agent/.si_corpus/` — the private career corpus. That is exactly the stray-add risk
`ACT-020` exists to warn about, and `ACT-020` is still open. Caught by reading the
staged list before committing, unstaged, and the staged set then scanned for
secrets.

### G. Final state

| | |
|---|---|
| Paid application-model calls | **0** |
| Deployed | **NO** |
| Pushed | **NO** |
| Merged | **NO** |
| Branch | `sprint17-recruiter-ux-testing` (local only) |
| Commits | 4 |
| Python blocking tests | 812, 0 failures |
| Quality monitors | 3 tests, 1 known RED (question m), printed by name |
| Playwright | 388 passed, 4 failed — all four proven pre-existing local-environment |
| Visual regression | 16 baselines, gated OFF, stable across 3 consecutive runs |
| Claude Code session cost | **UNKNOWN / NOT AUTHORITATIVELY AVAILABLE** |

The session-cost figure is genuinely unavailable rather than omitted: Claude
Code's `SessionEnd` hook captures real usage only when the session ends, and this
shell holds no `EVENT_LEDGER_DATABASE_URL`, so there is no captured row to read.
Estimating it would be exactly the fabrication `CLAUDE.md` forbids.

### H. Did this sprint find an AI-characteristic defect?

**Yes — three, and two of them are new shapes for this ledger.**

1. **A guard measuring a proxy for the thing it names** (the `innerText` false
   positive). The guard was written from the *idea* of an accessible name rather
   than from its definition, and the proxy diverged on a real page. This is the
   same family as Sprint 16's AEQ entry about a guard measuring geometry while
   claiming to measure quality, one level down.
2. **An exit code that had stopped carrying information.** The hermetic suite had
   been red for two sprints for a reason nobody could fix by changing code, and
   the one real wiring defect alongside it was invisible because both produced
   exit 1. A characteristically agentic failure: each sprint read the log, knew
   which failure was expected, and moved on — so the signal decayed with no single
   decision ever taken to let it.
3. **Three wrong fixes before the right one**, on the visual-regression timeout. I
   raised the test timeout (wrong), shrank the mask list (wrong but a real
   improvement), and only then found that `fullPage: true` with a `clip` rasterises
   the whole 70,000px page before discarding the clipped part. Each wrong fix was
   *plausible*, which is what made it expensive.

AEQ entries to be written for all three.

---

## Section 1 — Learnings from wrong ESTIMATION

**1.1 — Every one of six items came in at 0.22–0.35, and the cause is one thing:
I sized cross-cutting work as though breadth implied depth.** BL-190 touched nine
HTML files, three stylesheets, the route layer and two test layers, and I called it
LARGE at 110 minutes on that basis. It took about 30. The work was nine *small*
changes that happened to be spread wide, and spread is not difficulty. The
rubric's LARGE criterion is "meaningful new logic or design decisions, real
ambiguity requiring investigation" — file count appears nowhere in it, and I used
file count anyway.

**1.2 — The one item I sized for judgement rather than code was still wrong, in the
same direction.** BL-191 got LOW confidence and 92 minutes explicitly because "the
acceptance criterion is a human opinion no assertion can predict" — Sprint 16's
lesson 1.1, applied deliberately. It took about 20. The reasoning was sound and the
number was still 4× too high, because what I actually did was *measure* first-screen
geometry and move elements to satisfy a number. That is mechanical work. The
judgement part — whether it looks good — I did not do and cannot do; it is the
Owner's. **I sized the work I could not do and then did the work I could.**

**1.3 — The correction is a per-pattern multiplier, and Sprint 16 already said so.**
Sprint 16's retro 1.2 concluded: *"The calibration data is systematically wrong for
judgement work and systematically right for mechanical work. The correction is a
per-pattern multiplier, not a single global one."* One sprint later, six items, all
mechanical, all ~0.25. That is not new information — it is the same finding with a
larger sample, and nothing has been built to act on it. The action item is the
multiplier, not another observation.

---

## Section 2 — Learnings from IMPLEMENTATION issues

**2.1 — An element-name list is a guess about where prose will live next, and mine
was wrong within one page.** The overflow fix started as an explicit selector list:
`p, li, dd, td`, headings, six classes. `/usage` still overflowed by 16px, because
its history rows put the same long identifiers inside plain `div.goal` and
`div.session-row` — which no reasonable list would have contained. `overflow-wrap`
inherits, so the correct fix was one declaration on `body`. **When a property
inherits and the defect class is "text anywhere", enumerate nothing.**

**2.2 — Three wrong fixes on one timeout, and the cost was the plausibility.** The
visual-regression suite timed out on `/usage`. I raised the test timeout — no
change, because `toHaveScreenshot` has its own fixed 5s budget. I shrank the mask
list from 511 locators to the ones actually in frame — a real improvement, still
failing. The actual cause was `fullPage: true` with a `clip`: Chromium rasterises
all 70,000px and *then* discards the clipped part. **Each wrong fix addressed a
real inefficiency, which is exactly why I believed it was the cause.** The lesson
is to find the binding constraint before fixing anything adjacent to it — the 5s
figure was printed in the error message from the first run and I read past it
twice.

**2.3 — A 4000px baseline of a live-data page differed from itself by 256,034
pixels.** On a repeat run, same machine, same tree. Correctly: the event-ledger
figures and session rows inside those 4000px change between runs, and index-based
masking cannot follow a row insertion that shifts everything below it. Sprint 16's
handoff predicted this exact failure for screenshot baselines on live-data pages,
and I hit it anyway by picking one cap for two pages with different content. The
answer was neither a looser threshold (blinds the suite everywhere) nor a bigger
mask (hollows out the coverage) but a per-page cap.

**2.4 — I broke two existing specs and the second one taught me the distinction
that matters.** The Showcase duplicate button was a straightforward regression. The
Ask Codebase spec was not: it asserted behaviour the brief had explicitly asked me
to change. The two need opposite responses, and the tempting error is to treat both
as "a test is in the way" — which is how assertions get loosened to match copy that
drifted by accident. **The test to change is the one whose INTENT is still right
while its literal expectation has been deliberately superseded, and you have to be
able to say which.**

---

## Section 3 — Neither, but still needed

**3.1 — Per-item timing is still not instrumented, two sprints after it was named.**
Sprint 16's retro recorded that its per-item actuals were never captured, only the
sprint total, and that this weakens the calibration loop. Sprint 17 has the same
gap: the per-item column in section C is apportioned from commit boundaries, which
is a reconstruction, not a measurement. The calibration loop is now being fed
estimated actuals to correct estimates — and nobody should be surprised when that
converges slowly.

**3.2 — The guards this sprint added are, again, guards for the previous
complaint.** Sprint 16's retro 3.3 named the pattern: *"guards get written to catch
the previous complaint."* Sprint 17 added a third-party-font guard after finding
third-party fonts, an overflow guard after finding overflow, a copy contract after
finding contradictory copy. Each is worth having. None of them would have caught
the next thing. The one genuinely forward-looking guard added is the visual
baseline, and it is off pending the Owner's acceptance — so the pattern is
unbroken for a third sprint.

**3.3 — For the sprint as a whole: this is the first sprint where the Owner cannot
check the work by opening the site.** Nothing was deployed, by instruction, so
every visual claim rests on local screenshots and a document. The BEFORE pack is
production and the AFTER pack is this laptop, and for two pages those are not
comparable — `/usage` is 6,759px in production and 69,830px here, purely because
this machine holds 511 session rows to production's 2. I said so at the top of
`docs/FIRST_SCREEN_REVIEW.md` and in the contact sheet, because a reader who
missed it would read a tenfold height difference as the worst regression in the
sprint. **An autonomous sprint that cannot deploy has to work much harder at
telling the Owner which differences are real**, and that obligation is not
discharged by the numbers being correct.

**3.4 — One thing this sprint did that is worth keeping: it reversed a stated
Owner decision and said so in the loudest place available.** The Sprint 16 per-page
identity — which he called a USP — is gone, because the Sprint 17 brief demanded
it four separate times and evidence precedence puts his current instruction above a
committed document. That is the correct resolution and it is also the kind of thing
an autonomous agent should never do quietly. It is the first section of
`docs/DESIGN.md`, the first item in `docs/OWNER_DECISIONS_PENDING.md`, and a
paragraph of the commit message. Whether it was intended is still his call.


---

# RETRO — Deep Consensus Sprints 3 and 4 (written 2026-10-02, LATE)

**This retro is itself overdue, and that is the sprint's largest finding.**
Sprints 3 and 4 both ran to completion, produced working software and honest
evidence, and were then followed immediately by the next sprint — with no
sizing beforehand and no retro afterwards. The estimation-calibration loop
(.claude/rules/sprint-process.md, Phase 2) was skipped at both ends, twice
in a row. It was caught only when the Owner asked whether the foundational
concepts were genuinely at the top of the system.

Per the Owner's 2026-10-02 statement, continuous improvement is the **core**
concept and action items close **before** the next sprint's sizing. Both
sprints violated that. Recorded here rather than quietly moved past.

## Scope correction, on the Owner's instruction (2026-10-02)

Sprint 4 was **NOT** a scope deviation. The approved autonomous handoff
stated: *"IF AND ONLY IF SPRINT 3 PASSES, START SPRINT 4."* Sprint 3 passed
on all twelve of its stated conditions, so starting Sprint 4 was explicitly
authorised. A search of `docs/evidence/` finds no text describing Sprint 4
as unauthorised, so there was nothing to retract — this paragraph exists so
the record is unambiguous.

## Section 0 — the comparison table (the Owner's required format)

| Item | Size given | Actual | Verdict | Evidence |
|---|---|---|---|---|
| Sprint 3 — subscription transport, claim-level governor | **NONE GIVEN** | not measured | **ESTIMATION WRONG** (by absence) | No entry in docs/BACKLOG.json; `grep -c deep.consensus docs/BACKLOG.json` = 0 |
| Sprint 4 — 20-case evaluation harness + live run | **NONE GIVEN** | not measured | **ESTIMATION WRONG** (by absence) | Same; no numeric hour estimate or confidence was ever recorded |
| Retro for Sprint 3 | required | **not done** | **IMPLEMENTATION ISSUES** | No Sprint 3 entry in this file before today |
| Retro for Sprint 4 | required | **not done** | **IMPLEMENTATION ISSUES** | No Sprint 4 entry in this file before today |

There is no tolerance-band calculation to report, because there was no
estimate to compare against. The absence IS the finding — a sizing that was
never given cannot be judged accurate or inaccurate, and recording "N/A"
would hide a process failure as a data gap.

## The Owner's four improvement axes, assessed honestly

**1. Value of work done.** Real. Sprint 3 delivered a genuinely
cross-family subscription-backed engine (`cross_family_real = true`,
anthropic × xai, 0 paid API calls) and Sprint 4 delivered the first honest
measurement of whether any of it is worth having. Both produced evidence
that changes decisions rather than output that merely exists.

**2. Wastage reduced vs the previous state.** Mixed, and measurably so.
Reduced: the minimum-call governor replaced Sprint 2's ratification round,
and 85% of Sprint 3 runs cost 2 turns instead of 4-6. Increased: Sprint 4
measured 4.75 average turns because the pairing fix converted missed
conflicts into false conflicts — net waste went UP against the immediately
preceding state. Named rather than averaged away.

**3. Closer to the goal / milestone.** Yes on capability, not yet on the
question that matters. Two real families now review each other under a
bounded governor. But the product gate came back **MIXED**: zero
FALSE→TRUE corrections, and on the one case where the baseline was
outright wrong both families were wrong the same way.

**4. Clarity of purpose and vision.** Improved, and this is the strongest
of the four. Three governing concepts were recorded and are now ordered
first in the memory index (Gita frame → Shiva/Vishnu/Shakti → dharmic
governance → SCRUM AI → continuous improvement). "Deterministic AI" was
pinned as a slogan and not a claim. The same-wrong-answer limitation moved
from asserted to demonstrated.

## Section 1 — Learnings from wrong ESTIMATION

**1.1 No estimate was given for either sprint, so no calibration happened.**
*Reason:* both sprints arrived as detailed execution prompts with their own
phase structure, and I treated the prompt's structure as a substitute for
sizing. It is not. A phase list says what to do; a size estimate is a
falsifiable prediction about effort, and only a prediction can be wrong in
a way that teaches anything. Two sprints of calibration data are
permanently unrecoverable.

**1.2 The arrival of a new prompt was treated as permission to skip the
loop.** *Reason:* each sprint ended with a report and the next prompt
appeared immediately, so the retro never had an obvious moment to happen. A
loop with no enforced gate between iterations silently becomes a sequence.

## Section 2 — Learnings from IMPLEMENTATION issues

**2.1 A guard was written as a test before it was written as code, and the
test found the bug.** The negation defect
(`values_agree("no transaction starts", "a transaction starts") -> True`)
was found while writing a test to justify *not* loosening the comparator —
not by reading the code. *Reason:* writing the test forced enumeration of
the dangerous cases, which reading never does. This is a repeatable
technique, not luck.

**2.2 Fixing one comparison layer moved the failure to the next.** The
Sprint 3 subject-pairing fix turned false negatives into false positives at
the value layer. *Reason:* I verified the fix against the cases it was
designed for and against false pairs, but not against the next stage of
the pipeline. A fix needs a check on the stage downstream of it.

**2.3 The repo-scanning CI was contaminated twice by my own concurrent
edits** before the cause was recorded as a lesson. *Reason:* the first
occurrence was explained as a one-off instead of being written down. A
problem seen twice is a recurrence; the lesson now exists in
docs/LESSONS.md.

**2.4 A true fact was deleted by over-caution.** Sprint 2 removed the
PostgreSQL `SHARE` lock-mode name as "unsupported" after checking only the
CREATE INDEX page. The explicit-locking page states it outright. *Reason:*
"I could not find it" was collapsed into "it is not established". Being
over-cautious looked like rigour and was a different way of being wrong.

## Section 3 — Neither, but still needed

**3.1 The sprint as a whole: the loop needs an enforced gate.** No sprint
should be startable while the previous sprint's retro is unwritten or its
action items are open. This addresses the sprint as a whole rather than any
individual task, as the Owner's structure requires.

**3.2 Deep Consensus has no entries in docs/BACKLOG.json at all.** Five
sprints of work exist entirely outside the tracked backlog, so none of it
is visible to the sizing rubric or the calibration process.

**3.3 Twelve of twenty prepared evaluation cases remain unrun**, stopped
correctly at the 40-turn ceiling. The prepared ground truth is frozen and
hashed, so they are resumable at zero re-preparation cost.

## ACTION ITEMS — awaiting explicit Owner approval

Per Phase 2 of the sprint process, action items require the Owner's
explicit approval before being acted on. These are written, not started.

| # | Action | Addresses |
|---|---|---|
| A1 | Add a sizing gate: no new sprint sizing while the previous retro is unwritten or its action items are open | 1.2, 3.1 |
| A2 | Give every future Deep Consensus sprint a real numeric hour estimate + confidence in docs/BACKLOG.json before work starts | 1.1, 3.2 |
| A3 | Backfill docs/BACKLOG.json with the five Deep Consensus sprints as completed items, explicitly marked "size never given" rather than retro-fitted with invented numbers | 3.2 |
| A4 | Adopt "write the safety test for the guard you are about to justify" as a standing technique | 2.1 |
| A5 | When fixing a comparison/matching layer, add a check on the stage immediately downstream before closing the item | 2.2 |
| A6 | Re-run the 8 executed evaluation cases once the typed comparator lands, so the numbers include the negation fix | Sprint 4 limitation 6 |

**A3 deliberately does not invent retrospective estimates.** Back-filling
plausible numbers would manufacture calibration data that never existed and
corrupt every future tolerance calculation.

## Why Sprint 5 proceeds before these are approved

The Owner issued the Sprint 5 execution prompt directly, with "Start now.
Do not ask routine questions." A direct instruction outranks the queued
action items. The items above remain open and unapproved, and this retro is
now on record so the gate can be applied from Sprint 6 onward.

---

# RETRO — Deep Consensus Sprint 5 (2026-10-02)

**Written before the next sprint's sizing, which is the first time that has
happened for a Deep Consensus sprint.** Sprints 3 and 4 were executed with no
estimate and no retro; that was the headline finding of the overdue
Sprints 3+4 retro written earlier today. Sprint 5 was sized first (BL-DC5)
and is retro'd before anything else starts.

## Section 0 — the comparison table (the Owner's required format)

| Item | Size given | Actual | Verdict | Evidence |
|---|---|---|---|---|
| BL-DC5 — typed claims, one-sided cross-check, 8-case rerun | **XLARGE, 360–540 min, midpoint 450, confidence MEDIUM** | **101 min** wall-clock (first Sprint 5 commit → live run complete) | **ESTIMATION WRONG — over-estimate**, ratio **0.224** | band [0.7, 1.3] from `docs/BACKLOG.json` `_calibration_process.tolerance`; computed, not judged |
| Same, including the pre-commit parallel-agent build phase | same | **~140 min** (floor; not precisely measurable from git) | **ESTIMATION WRONG — over-estimate**, ratio **0.311** | agents reported 761 s, 765 s, 1231 s; the fourth predates the measurable window |

**Both figures answer different questions and both are reported, as the
calibration process requires for parallel work.** Wall-clock is what the
Owner waited. The summed individual durations are higher than wall-clock
because four write-capable agents ran concurrently; a summed figure would
describe effort, not elapsed time, and neither is a substitute for the other.

**The 101-minute figure is a floor, stated as one.** Work began before the
first Sprint 5 commit — `typed_values.py` and its 29-test suite were already
built by parallel agents — and git cannot date that. I have not invented a
precise start time to make the table look complete.

**Calibration history, for context rather than comfort:** Sprint 8 ratio
0.30 (under-estimate of effort / over-estimate of time), Sprint 9 ratios 1.9
and 3.3 (the project's first over-runs), now 0.22–0.31 again. That is
**oscillation, not convergence**, and it is the third sprint in a row where
the band did not hold. The `residual_bias_factor` fix was already tested and
rejected in Sprint 9; this retro does not re-propose it.

## The Owner's four improvement axes

**1. Value of work done.** Real but narrow. The engine improved on every
axis measurable from inside it: 18 of 18 eligible one-sided claims examined
where Sprint 4 examined 0 of 29, UNCOMPARED now blocks CONVERGED, 4 of 8
statuses became correctly confident, zero regressions. The product question
— does this reduce published falsehood — is still unanswered, for the second
sprint running.

**2. Wastage reduced vs the previous state.** **No, slightly worse, and
named rather than averaged away.** Deep Consensus turns went 30 → 31 (3.750
→ 3.875 per case) and the single 2-call early stop disappeared. The typed
comparator removed Sprint 4's false disagreements and replaced them with
honestly-undecidable TEXT pairs plus new cross-check turns. `S4-DB-1` went
from 2 calls to 3 — a better run that costs more. That is a defensible
trade, but the waste figure moved the wrong way and claiming otherwise would
be spin.

**3. Closer to the goal / milestone.** On mechanism, yes. On evidence, no —
and this sprint established WHY, which is progress of a kind: the eight
available cases cannot answer the question because the frozen baseline is
already correct on all eight. Two sprints have now produced that same
non-answer. The bottleneck is case selection, not the engine.

**4. Clarity of purpose and vision.** Improved. The sprint produced a
sharper statement of what the product must prove and a specific, hard,
named obstacle to proving it (choosing cases where a strong model fails,
without choosing them by watching it fail).

## Section 1 — learnings from wrong ESTIMATION

**1.1 The estimate priced sequential execution and the work ran in
parallel.** Four write-capable agents produced roughly 2,900 lines
concurrently. Nothing in the XLARGE rationale accounted for that, so a
correctly-reasoned sequential estimate was ~3–4× the parallel actual. The
rubric has no parallelism input at all; until it does, any sprint executed
with concurrent agents will over-estimate by construction.

**1.2 Parallelism has an integration cost the estimate also missed, in the
opposite direction.** Two separate **contract divergences** followed from
running agents concurrently against a written spec — a bare `parse("yes")`
typed BOOLEAN by the engine and TEXT by the test, and the TEXT-pair routing
question — each needing a decision, a message to a running agent, and a test
edit. Parallelism is not purely a throughput multiplier; it generates
reconciliation work that scales with the number of agents.

**1.3 The estimate did not price defects in the sprint's OWN new code.** The
risk drivers named integration with the existing engine, the live rerun and
the gates. Four defects were found during integration and three were in code
written this sprint. Time spent debugging freshly-written code is a
different category from integration time, and only the second was estimated.

## Section 2 — learnings from IMPLEMENTATION issues

**2.1 A test's stated REASONING caught a defect its assertion alone would
not have.** `test_identical_text_on_both_sides_is_still_text_undecided`
argued that an identity fast path "would reintroduce exactly one
false-agreement route: normalisation collapsing two values that were never
the same." I had already written that exact route — `normalize_text` turns
punctuation into spaces, so `"x > y"` and `"x < y"` agreed. The test was
written by an agent that had never seen my implementation. **Reading a
disagreeing test's argument, not just resolving its assertion, is the
technique.** It paid out twice this sprint.

**2.2 Two of three defects in new code were in COST-motivated changes to a
correctness component.** The identity exception existed to stop a 4-call
blow-up; the VERSION-precedence override existed to stop losing a true
pairing. Both were cost fixes and both opened a correctness hole. A change
made to save turns deserves at least the scrutiny of one made to fix
correctness, because the motivation feels harmless and the review reflex is
weaker.

**2.3 The measurement tool had the same defect class as the thing it
measures, and it produced a false headline.** The scorer's wrong-answer
marker test was a plain substring match and read "they are **not** suited to
CPU-bound work" as publishing "suited to cpu-bound". On that single false
positive the run's first product verdict was that Deep Consensus had
introduced a material false claim. It had not. **Fixing negation blindness in
the comparator did not fix it in the scorer** — and a measurement is only as
trustworthy as its own worst bug. The project rule this vindicates already
existed: a diagnostic must be proven to detect the known-bad case before its
clean verdict is trusted.

**2.4 Model-supplied text was used as an identity key.** `pair_claims`
tracked consumed claims by `claim_id`, which a model writes. Two claims
sharing an id meant one vanished from the comparison entirely — not
UNCOMPARED, absent. Untrusted input must never be an identity key; the
identity is now the list position, which no model can influence.

**2.5 A structural guard that fires on an unrelated stdlib import is a guard
that gets switched off.** The coding-agent isolation test substring-matched
module names, so `import itertools` was reported as importing `tools`. It had
been correct only because nothing in the package had previously imported
itertools.

**2.6 A mutation gate found a hole 275 tests did not, and the hole was
exactly one assertion wide.** Nothing asserted that a material pairing with
no agreed state blocks CONVERGED. Two safety-critical mutants walked through
it. Coverage did not predict this; an adversarial mutation did.

## Section 3 — neither, but still needed

**3.1 The zero-turn dry run of the POST-TURN path paid for itself
immediately.** `outcomes.aggregate` expects rows keyed
`baseline_score`/`deep_score`/`outcome`/`noise`; the runner passed different
names. That `KeyError` would have fired after all eight cases were paid for
and destroyed the entire 40-turn budget. The brief's rule — never use live
subscriptions to debug — is exactly what this protects.

**3.2 Refusing to truncate evidence paid out for the first time.** Because
`baseline_result_full` and the whole `deep_consensus_result_object` were
stored untruncated, the scorer defect in 2.3 was corrected and all eight
cases re-scored at **zero model turns**. Had the evidence been truncated as
Sprint 4's was, re-measuring would have cost a second 40-turn budget. This
retires any remaining argument for trimming stored evidence.

**3.3 Verifying my own tool's NEGATIVE claim prevented a wrong escalation.**
The Grok preflight reported NOT_LOGGED_IN and told the Owner to run
`grok login`. Grok was logged in; the detector produced a transient false
negative. I was one step from asking the Owner to fix a problem that did not
exist. The "verify, don't dismiss" discipline applies to my own tools'
negatives, not only to the Owner's reports.

**3.4 `requested_model` and `reported_model` genuinely diverge in
production.** Requested `grok-4.6`, reported `grok-4.6-build`, on all 15
slot-B turns. Sprint 3's requirement to record both separately is
load-bearing, not ceremonial.

**3.5 `stage=one_sided_check` had no producer when the replay harness was
written and now has one.** The agent that built it flagged the stage as
possibly a spec drafting assumption and asked for confirmation. It was not:
`S4-DB-1`'s third turn was a cross-check-only turn.

**3.6 The product question is now bottlenecked on case selection, not on
the engine.** Eight cases where a strong single model is already correct
cannot demonstrate error catching. This is the single most important open
item and it needs design work before more turns are spent.

## ACTION ITEMS — awaiting explicit Owner approval

A1–A6 from the Sprints 3+4 retro remain **open and unapproved**. These are
additional, also unapproved and not started.

| # | Action | Addresses |
|---|---|---|
| A7 | Add a parallelism input to the sizing rubric: an estimate must state whether it prices sequential or concurrent execution | 1.1 |
| A8 | Price agent-contract reconciliation explicitly when a sprint plans N concurrent write-capable agents | 1.2 |
| A9 | When an agent-written test disagrees with my implementation, read and answer its stated ARGUMENT before resolving either way | 2.1 |
| A10 | Treat a cost-motivated change to a correctness component as a correctness change for review purposes | 2.2 |
| A11 | Audit the scorers and diagnostics for the defect classes already fixed in the engine — starting with negation and substring matching | 2.3 |
| A12 | Audit the engine for other places model-supplied values are used as identity keys | 2.4 |
| A13 | Design the "baseline actually fails" evidence set, including how cases are chosen without watching the model fail | 3.6 |
| A14 | Size the "does a stronger single Claude model beat the pair" question as its own item with its own turn budget | Sprint 4 limitation 3 |

A7 and A8 are the two that would have changed this sprint's estimate. A13 is
the one that would change the next sprint's value.

---

# RETRO — Deep Consensus Sprint 6 (2026-10-02)

Written before any next-sprint sizing, per the approved A1. Sprint 7 has not
been started.

## Section 0 — the comparison table (the Owner's required format)

| Item | Size given | Actual | Verdict | Evidence |
|---|---|---|---|---|
| BL-DC6 — close actions, safety audits, pre-registered evidence, one decisive run | **XLARGE, 300–360 min, midpoint 330, confidence LOW, CONCURRENT, 6 agents, 40 min reconciliation** | **97 min** wall-clock (first Sprint-6 commit → run complete + Phase 4) | **ESTIMATION WRONG — over-estimate**, ratio **0.295** | band [0.7, 1.3] from `docs/BACKLOG.json` `_calibration_process.tolerance`; computed, not judged |

**Parallel work, both figures, as the calibration process requires.**
Wall-clock 97 min is what the Owner waited. Summed agent effort was far
higher — six concurrent write-capable agents reporting roughly 1.14 million
subagent tokens — and the two answer different questions. Neither substitutes
for the other.

**Calibration history: oscillation, not convergence, for a fourth sprint.**
Sprint 8 ratio 0.30, Sprint 9 ratios 1.9 and 3.3, Sprint 5 ratio 0.224, now
0.295. The `residual_bias_factor` fix was already tested and rejected in
Sprint 9 and is not re-proposed.

**A7 and A8 were applied for the first time and did not fix the estimate.**
Stating which execution model was priced (CONCURRENT) and pricing
reconciliation at 40 minutes were both correct and both insufficient: the
estimate was still 3.4x the actual. The missing term is not parallelism — it
is that the dominant cost I feared (a 20-case live run) took ~50 minutes
while the work I under-priced (two audits that found eleven defects) was
absorbed by agents running concurrently with each other AND with my own work.

## WHAT WAS EXPECTED

That the audits would confirm the Sprint-5 fixes were complete and find
little else. That the mutation gate would pass first time. That the hard part
would be building 20 primary-source cases. That the decisive run would
finally answer whether governed review reduces published falsehood.

## WHAT HAPPENED

Three of those four were wrong, and the fourth produced a non-answer for the
third consecutive evidence sprint.

**The audits found eleven real defects, none of them the ones they were
chartered to verify.** Nine scorer, two identity. Two would publish a FALSE
AGREEMENT. One reproduced the Sprint-5 headline defect through a path the
Sprint-5 fix never touched.

**The mutation gate blocked twice**, both times usefully — once on a real
coverage question, once on a badly designed mutant of my own.

**The entitlement check failed in a way the frozen rule did not
anticipate.** Requesting `claude-opus-5` returned an answer from
`claude-haiku-4-5-20251001`.

**The decisive run completed and its mechanical verdict rests on an
artefact.** 20/20 cases, 99 turns, zero provider limits, zero billing
violations, zero introduced falsehoods. The challenge set produced ZERO
baseline falsehoods in 12 cases. The only two recorded baseline falsehoods
are a spelling artefact in one blind case.

## DEFECTS FOUND

| # | Where | Severity |
|---|---|---|
| 1 | `published_as_settled` stripped 3 of 4 annotated blocks; `NOT CROSS-CHECKED` counted as published fact | reproduced the Sprint-5 headline defect |
| 2 | Short accepted values matched inside words — "no" in *now/normal/not*, "io" in *production*, "17" in *2017* | an answer advocating the forbidden practice scored CORRECT_COMPLETE |
| 3 | `expected_values` credited an answer asserting the opposite ("blocked" inside "not blocked") | published falsehood recorded as correct |
| 4 | Cross-clause negation leak in `_marker_published` | a genuine catch booked as a completeness gain |
| 5 | Unanchored heading `find()` deleted the rest of an answer | manufactured COMPLETE_TO_INCOMPLETE |
| 6 | `disputed_text` omitted two warning buckets | specific exposure downgraded |
| 7 | Polarity applied to the wrong question in exposure detection | exposure missed |
| 8 | Marker matched a longer word ("it is safe" in "it is safer") | correct security answer charged with a falsehood |
| 9 | Subject-collision Stage-4 routing | **published false agreement** |
| 10 | `_closest_subject` picked a winner among equally plausible subjects | **published false agreement** |
| 11 | Entitlement accepted an answer from a different, weaker model as proof | would have made the whole measurement flattering |
| 12 | My own suspect-detector flagged `ACCESS EXCLUSIVE` vs `EXCLUSIVE` and `SHARE UPDATE EXCLUSIVE` vs `UPDATE EXCLUSIVE` as spelling differences | would have excused a real falsehood |
| 13 | My own suspect-detector linked catches by their own comparison verdict (AGREE by construction) so flagged zero catches | the figure the decision rule reads went unflagged |

## THE CENTRAL FINDING

**Every headline this project has produced has been decided by a defect in
its own measurement rather than by the product.**

- Sprint 5's headline was a manufactured REGRESSION: a substring read "not
  suited to CPU-bound work" as publishing "suited to cpu-bound".
- Sprint 6's headline is a manufactured CATCH: the baseline answered
  `PROPAGATION_REQUIRED` where the frozen golden claim pinned `REQUIRED`.
  Same answer, different documented spelling.

The two errors point in opposite directions, which rules out a simple bias
and indicts the method instead. It is a stronger argument for the
pre-registration discipline than anything the product itself has shown — and
it is the reason the Sprint-6 report publishes both verdicts rather than
choosing.

## EVIDENCE QUALITY

Best of any sprint so far, and still unable to answer the question.

Strong: 20 cases, every ground truth a verbatim primary-source quote actually
fetched; 65 material claims, 61 deterministically typed and 4 honest
NEEDS_OWNER; both sets hashed separately and together before the first
evaluated answer; a freeze that refuses re-registration; the decision rule
hashed as frozen text; every integrity and billing check PASS; Sprint-6
self-replay reproduces the verdict offline with 0 differences and 0 model
calls.

Limits, each recorded by the agent that produced it rather than by me
afterwards:
- Challenge difficulty is **asserted by category, never measured**. The
  baseline answered all twelve correctly. The set's author wrote in advance
  that this would be a real result and not a reason to hunt harder questions.
- The Sprint-5 replay's 0 differences **proved nothing about the identity
  fix**: 0 colliding routing keys in 50 pairings, so the fix could not apply.
  The report says so in a computed coverage block.
- Question wording is model-authored even though ground truth is not.
- 29 NEEDS_OWNER items remain unadjudicated.

## MODEL-TURN WASTE

- **1 wasted entitlement turn, mine.** I re-ran the Opus probe with a
  corrected criterion when the stored record was already sufficient to
  re-judge offline.
- Zero wasted evaluated turns: no case rerun, no prompt tuned after a result,
  no paid fallback, no fifth call.
- **10 unresolved-noise cases out of 20** — Deep Consensus spent turns
  disputing propositions that were not baseline falsehoods. At 3.85 DC turns
  per case against a baseline of 1, that is the real cost figure.
- Every audit, gate, replay, scorer rebuild and report cost zero turns.

## PARALLELISM EFFECT

Six write-capable agents, strictly partitioned files, zero collisions, zero
lost work, ~5,900 lines across 13 new files.

The effect that mattered was not speed. **Agents that had never seen my
implementation found defects in it, repeatedly** — the scorer audit found
five negation paths the landed fix had missed, and a Sprint-5 contract test's
stated objection described a false-agreement route I had already written. A
second instance of the same model is not an independent mind, but it is an
independent evidence path, and at this defect-find rate it is worth its token
cost.

Three contract mismatches at module boundaries I had specified in prose, all
caught by tests rather than by reading. The one that cost nothing was the one
where the agent made its contract REFUSE bad input rather than tolerate it.

## A PATTERN THAT APPEARED FIVE TIMES IN TWO SPRINTS

A guard or test that searches text for the name of a thing it forbids will
fire on the text that forbids it.

1. `test_20` flagged `import itertools` as importing the module `tools`.
2. The Sprint-5 scorer read "not suited to CPU-bound work" as a claim.
3. `test_17` flagged the frozen case recording `false` for "is the
   convergence score a correctness probability".
4. My own test asserted "pooled" absent from a summary dict and fired on the
   sentence forbidding pooling.
5. My own test asserted "inconclusive" absent from a verdict and fired on
   "so this is PAUSE -- not inconclusive".

**The fix in every case is to assert over STRUCTURE — keys, verdict values,
parsed imports, typed comparisons — never over prose.**

## WHAT SHOULD CHANGE

New action items, all UNAPPROVED because the Owner is absent.

| # | Action | Addresses |
|---|---|---|
| A15 | Golden claims must record EVERY documented spelling of an enum value, or declare the spelling normative in the question | the manufactured catch, defect 12 |
| A16 | Before any evidence sprint, run the scorer against the frozen golden claims and a deliberately-correct synthetic answer; any claim that fails to score CORRECT is a case-data defect, found at zero turns | would have caught the artefact pre-freeze |
| A17 | Treat every assertion over prose in a guard or test as a defect by default; assert over structure | the five-instance pattern |
| A18 | A measurement tool gets the same mutation coverage as the engine it measures | the scorer carried nine defects while the engine carried two |
| A19 | Mechanise A1 — a sizing gate that refuses while a prior retro is unwritten | A1 could not be closed because it is applied by hand |
| A20 | Exercise A10 deliberately, or descope it — approved and never applied | A10 could not be closed |
| A21 | Record both wall-clock and summed-agent-effort in every concurrent estimate, and stop treating the live-run duration as the dominant term | the estimate was 3.4x despite A7/A8 |
| A22 | Investigate the 7 Grok multi-object `cancelled` responses; they correlate with PARTIAL statuses and unparsed cross-checks | provider-side, bytes intact, currently unexplained |
| A23 | Adjudicate the 29 NEEDS_OWNER items, starting with the 2 flagged rows that decide this sprint's verdict | the verdict depends on it |
