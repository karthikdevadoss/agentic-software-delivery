# Agentic Software Delivery System

New session/new machine? Start at **START_HERE.md** (repo root) — the
canonical recovery entry point. Durable "why"/product structure:
docs/COMPANY_VISION.md. Governing principles: docs/CONSTITUTION.md (read
when a duty/scope/priority/truthfulness question isn't obviously answered
by the rules below). Long-term direction (two dashboard audiences,
session/AI-engineering intelligence, multi-agent roadmap, enterprise
benchmark ladder, near-term ordered roadmap): docs/ROADMAP.md — future
increments only, do not build from it without an explicit task. Unresolved
possibilities not yet decided: docs/IDEAS.md.

## Session startup
Before modifying anything:
1. Read docs/PROJECT_STATE.json.
2. Read docs/PROJECT_STATUS.md.
3. Read docs/DECISIONS.md when architectural context is needed.
4. Read docs/LESSONS.md when working on tool-use loops, thinking blocks, path/security logic, or build tooling — skip otherwise.
5. Check docs/ACTION_QUEUE.json (if present) for smaller open action items separate from the current phase.
5a. Before sizing any new task, check docs/RETRO_LOG.md for prior estimation/implementation learnings and docs/BACKLOG.json's `_calibration_process` for the current tolerance band.
6. Run git status --short.
7. Run git log -5 --oneline.
8. Inspect only files relevant to the next task.
9. If a documentation/state claim actually matters for the task, verify it against the real source/Git rather than trusting it — actual repository state wins on conflict; correct the stale doc after verifying.
10. Report current version, current ticket, verified state and exact next action.
11. Do not modify code until explicitly asked.
12. Before ever reporting previously-described work (from PROJECT_STATE.json, a prior session's summary, or the user's own recollection) as missing/lost: git status --short and git log alone are NOT a complete picture. Also check git stash list, git branch -a, and git reflog -20 — real, uncommitted work is routinely (and correctly) stashed or left on an unmerged branch when a higher-priority task interrupts it, and none of that shows up in a plain status/log check. Only report something as genuinely lost after checking all of these and finding no trace.

## Proactive action policy
Within an explicitly approved task/phase, don't just report a small fixable
problem — if it is low-risk, reversible, inside the approved scope, and its
fix can be verified deterministically (e.g. a syntax error, a failing
focused test caused by the current change, a wrong trace/log label, a stale
state entry discovered during this phase), fix it, verify it, and report
the result.

Do not auto-execute when the action changes architecture, expands scope
beyond the approved task, touches production/external systems, writes
secrets, deletes significant data/code, changes security boundaries or
dependencies/platform strategy, needs product/business judgment, or is
irreversible/high-risk. Those become entries in docs/ACTION_QUEUE.json
(status: open) awaiting explicit approval instead.

## Human-AI Engineering Operating Policy
Applies to every AI-assisted task on this project, on top of the general
"do not waste resources" / "efficient verified value, not blind cost
minimization" principle (docs/CONSTITUTION.md §7). Sanitized/generic here
by design — this project's own private operating detail (which models,
which numbers, which incidents) lives outside this public repository.

- **Task contract before substantial work.** A non-trivial task gets a
  clear scope/goal before real work starts (Plan Mode for interactive
  work; an explicit Owner authorization message for an unattended run).
  Mechanical/small fixes inside an already-approved scope don't need a
  new contract each time (see Proactive action policy above).
- **Strong reasoning capacity where it materially matters, not by
  default.** Reach for the strongest available model/effort for
  architecture decisions, difficult debugging, root-cause analysis,
  security decisions, production incidents, complex implementation,
  independent QA/evaluation, and high-risk verification. Use lighter
  models or deterministic tooling (grep/search, file reads, formatting,
  simple edits, routine test execution, status checks, deterministic data
  transforms) for genuinely mechanical work. Never downgrade a difficult
  task to save cost; never spend a strong model's capacity on work
  software or a lighter model performs equally reliably.
- **Parallel agents are a deliberate choice, not a default.** Before
  running multiple model-heavy agents/subagents at once, the real
  question is: will parallelism materially reduce total time-to-VERIFIED-
  outcome enough to justify multiplying token/cost consumption? Deterministic
  shell/test processes and lightweight independent searches may run in
  parallel freely; expensive reasoning/coding agents normally run
  sequentially unless parallel execution has clear, stated value.
- **Session length itself is a real cost driver — prefer `/clear` or
  `/compact` between genuinely distinct tasks.** Real incident (2026-09-18,
  see docs/interview-scenarios/13-...): a real EUR40 pay-as-you-go credit
  was exhausted in under 7 minutes once a session already carrying ~5-6
  hours of accumulated context switched to unsupervised, no-pause
  autonomous operation — every turn was re-sending ~550-590K cache-read
  tokens as pure overhead before any new work happened, at 5-15 turns/
  minute. No single action was expensive; *already-large context* × *high
  turn frequency* × *zero pause* was. Starting a genuinely new task in a
  long-running session without compacting first is a cost smell worth
  noticing, not a neutral convenience.
- **Cost/usage accounting, honestly labeled.** For every concrete AI-
  assisted task, preserve what's real where observable: model, effort,
  timing, calls, tokens, cost, retries, and verified/not-verified outcome.
  Never present an estimate as an actual figure. Use honest provenance —
  a real measured/captured value, a value calculated from real captured
  data via a versioned source (e.g. pricing), an observed but
  incompletely-attributable value, or genuinely unknown — never silently
  turn "unknown" into a fabricated zero or a false "actual." The goal
  metric is cost per VERIFIED outcome (and time, retries, human
  intervention per verified outcome), not the cheapest individual model
  call.
- **Never change a paid spend/usage limit without the Owner's explicit,
  separate approval.** Even when a task is otherwise pre-authorized
  end-to-end.
- **New dashboards/trackers/frameworks require a real decision they
  answer.** Don't build a new tracking surface, config layer, or
  abstraction "for completeness" — extend or reuse what already exists
  unless a genuine, current need can't be met that way.
- **Validation/hardening mode is a real, declarable project state.** When
  the Owner declares it, new feature work stops; effort goes to testing,
  verifying, fixing, and hardening what already exists until the Owner
  explicitly reopens feature work. Check docs/PROJECT_STATE.json's
  `next_phase`/`next_action` for whether this is currently in effect.

## Backlog and sizing discipline (Phase 1, 2026-09-18)
Adapted from Scrum's core idea for a team of one AI executor and one human
Product Owner/Tech Lead -- not a literal copy of human-team ceremonies (no
Daily Scrum, no fixed sprint clock, no team-culture coaching: those exist
to coordinate *multiple* people, which does not apply here). See
docs/BACKLOG.json for the full rationale and docs/interview-scenarios/ for
the incident that motivated it.

- **No non-trivial task starts without a sized backlog entry.** Before
  beginning real work (not a trivial in-scope fix already covered by the
  Proactive action policy above), add or update an item in
  docs/BACKLOG.json with a description and a **size**: SMALL / MEDIUM /
  LARGE / XLARGE (the current official Scrum Guide term -- "estimate" was
  removed in the 2020 revision). Sizing is Claude's own responsibility,
  done before the work, using the rubric in docs/BACKLOG.json's
  `_sizing_rubric` -- never skipped, never assigned after the fact to
  match how it went.
- **A "sprint" here is one sized item, start to finish** -- not a fixed
  clock. There is exactly one executor working sequentially, so there is
  no multi-person sync problem a fixed timebox exists to solve.
- **Ad-hoc work still gets sized**, just at the moment it's requested
  rather than planned days ahead -- "ad-hoc" changes when something is
  planned, never whether it's sized.
- **Plan changes are the Owner's prerogative, always** -- if a backlog
  item is abandoned or paused mid-way, mark it `descoped` with a reason;
  never let it silently vanish or count as a bad size prediction later.
- **Size vs. actual comparison exists (agent/backlog.py) but retro is not
  yet automated** -- this is a deliberate Phase 1 scope limit: prove the
  simple version adds real value before building a scheduled retro
  subagent, to avoid the measurement system itself becoming the waste it
  exists to prevent.

### Phase 2: the estimation-calibration loop (added 2026-09-18/20, Owner directive)
Every sprint (one sized item, start to finish) runs a closed loop:
estimate (with a real numeric hour estimate + confidence, not just the
SMALL/MEDIUM/LARGE/XLARGE label -- see docs/BACKLOG.json's
`_sizing_rubric`) -> implement -> retro at the end, comparing time
required vs. time taken -> any gap outside tolerance
(actual/estimate-midpoint within +-30% to start, tightened over time --
see docs/BACKLOG.json's `_calibration_process`) is diagnosed as exactly
one of two causes: ESTIMATION WRONG or IMPLEMENTATION ISSUES (both may
apply to the same item, named as two separate findings, never blended)
-> action items written (never sized) -> **explicit Owner approval
required before acting on them** (a deliberate exception to this
project's general autonomy-first default) -> action items done first ->
only then size the next NEW task with the updated knowledge (never
retroactively re-size an already-completed old task). A mid-sprint
realization Claude makes on its own never triggers a re-estimate --
finish the sprint as planned, it surfaces in that sprint's normal retro
as an ESTIMATION WRONG finding. Only the Owner himself changing scope
mid-sprint triggers an immediate re-estimate. Every retro's full data
(comparison table, verdicts, evidence, discussion, action items) is
stored permanently in docs/RETRO_LOG.md -- never left only in chat.

## Feedback discipline
For every meaningful run: compare expected vs. actual, classify any gap
(implementation bug / test gap / requirement ambiguity / architecture /
security / model-or-tool-API behavior / context-memory problem /
observability gap), decide the smallest safe correction, verify it, and
persist only what's reusable — a lesson in LESSONS.md, an item in
ACTION_QUEUE.json, or an updated fact in PROJECT_STATE.json. Don't persist
trivial observations.

## Stability / Execution Discipline
- One execution task / primary outcome at a time.
- If a user-visible critical workflow fails, STOP feature expansion.
- Diagnose from evidence before changing code.
- Fix the proven root cause only.
- Add a regression for every meaningful escaped deterministic defect.
- Re-run focused tests, then regression suite, then appropriate runtime check.
- Never present stale documentation as current runtime truth.
- Never confuse transport timeout/status uncertainty with verified failure.
- An external CLI/process's own output-decoding failure is never itself an
  application/deployment failure — a final status must be backed by actual
  evidence (e.g. independent production verification), not by the absence
  of a signal that failed to decode.
- Never leave the operator unable to tell whether the system is working,
  waiting, blocked, degraded, failed or complete.
- When a new run/state/status is introduced, audit every consumer of that
  state (execution, persistence, streaming/polling, Sessions/Dashboard/UI/tests).
- Do not move to another feature while unresolved P0/P1 stabilization defects
  remain.

## Durable-state rules
- Repository files and Git are authoritative; conversation history is supplementary.
- Never guess what an earlier session did. Verify filesystem and Git.
- Workflow:
  implement → inspect diff → compile/test/run → verify → update state → commit.
- Keep PROJECT_STATE.json synchronized after meaningful verified work.
- Update PROJECT_STATUS.md for meaningful project progress.
- Record important architecture decisions and WHY in DECISIONS.md.
- Record durable, reusable technical gotchas (not decisions, not status) in LESSONS.md.
- For fast-moving external tech (Claude/Anthropic API, MCP, model names, tool-use behavior), verify against current official docs when available rather than trusting older notes — record version-sensitive decisions with enough context to revisit later.
- Never expose, print, stage or commit agent/.env or API keys.
- Never weaken tests/verification just to make something pass.
- Before stopping or when context is becoming constrained: finish or safely halt the current coherent unit, verify it, update PROJECT_STATE.json and docs/ACTION_QUEUE.json (if it exists), commit, and leave one explicit next_action — a fresh session must be able to resume from repository state alone.
- If a higher-priority task interrupts substantial uncommitted work, stashing it (git stash -u, to also capture new untracked files) to switch cleanly is correct — but the stash itself is not durable/findable on its own. Immediately record a one-line pointer to it (the stash message, the branch it was on, what it contains) in docs/ACTION_QUEUE.json or PROJECT_STATE.json's next_action, before starting the interrupting task. A fresh session after a context-compaction boundary has no memory of having stashed anything; only a durable, indexed pointer — not the stash existing somewhere findable via git archaeology — makes it resumable.
- A local `git commit` is not durably saved — durability requires a verified
  remote push (see docs/RECOVERY.md, docs/RESOURCE_REGISTRY.md's Git entry).
  Do not describe work as "saved" or "backed up" from local commits alone.
- No important company/project knowledge may exist only in this laptop,
  ChatGPT, Claude, browser state, terminal output, or process memory — see
  docs/CONSTITUTION.md §17. Before completing a meaningful task, check
  whether it created or changed: company/product vision, an accepted
  decision, the roadmap, an important unresolved idea, an architecture
  rule, an engineering lesson, a resource/URL, verified project state, or
  a recovery requirement. If yes, update *only* the one appropriate
  canonical document (COMPANY_VISION/DECISIONS/ROADMAP/IDEAS/
  CONSTITUTION/LESSONS/RESOURCE_REGISTRY/PROJECT_STATE/RECOVERY) — never
  duplicate the same fact across several files. If no, don't edit
  documentation merely to create activity.

Useful commands:
Planner:
python agent/main.py requirements/sample_requirement.txt

Spring compile:
cd app
.\mvnw.cmd compile

Spring app:
cd app
.\mvnw.cmd spring-boot:run

UI:
http://localhost:8080
