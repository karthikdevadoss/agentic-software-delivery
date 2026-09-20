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
  **Exception (Owner directive, 2026-09-20): post-retro improvement work
  does not need to be sized.** Action items that come directly out of a
  retro's own diagnosis (fixing a named estimation/implementation
  mistake, building a tool the retro's own root-cause analysis called
  for) may be picked up and done directly -- this is a deliberate
  carve-out from the general rule, not a loosening of it elsewhere.
  Category tagging in docs/OUTSIDE_SPRINT_LOG.md still applies if the
  work happens outside an active sprint.
- **A "sprint" here is one or more sized items approved together for one
  work session, start to finish** -- not a fixed clock (corrected
  2026-09-20: real practice diverged from this doc's original "one sized
  item" definition the first time a multi-item sprint actually ran --
  the Owner approved a 7-item batch as one sprint, bounded by a real
  elapsed-time target like "2 hours," not by finishing exactly one item).
  A single-item sprint is still the common case for a large XLARGE epic;
  a batch of smaller items sharing one approval/work session is equally
  valid and is what "sprint" means going forward. There is exactly one
  executor working sequentially, so there is no multi-person sync
  problem a fixed timebox exists to solve.
- **Ad-hoc work still gets sized**, just at the moment it's requested
  rather than planned days ahead -- "ad-hoc" changes when something is
  planned, never whether it's sized.
- **Plan changes are the Owner's prerogative, always** -- if a backlog
  item is abandoned or paused mid-way, mark it `descoped` with a reason;
  never let it silently vanish or count as a bad size prediction later.
- **Size vs. actual comparison (agent/backlog.py) pulls real cost/tokens/
  wall-clock from the event ledger via a backlog item's `session_ids`** --
  every item worked in a session must have that session's real session_id
  recorded (Claude Code's own SessionEnd hook, agent/claude_code_hook.py,
  captures the real usage automatically once the session ends; a backlog
  item created without its session_id wired in cannot be retroactively
  cost-compared later even though the ledger data exists). Retro itself
  is real and manual (Phase 2, docs/RETRO_LOG.md) -- proven to add value
  across BL-007 and a real 7-item sprint before any scheduled/automated
  retro subagent is considered, per the Owner's own 'don't build the
  waste-risk before proving the simple version' call.

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
-> action items written (never sized), in exactly THREE fixed sections
every time (Owner's permanent structure, 2026-09-20): (1) estimation-
mistake improvements, (2) implementation-mistake improvements, (3) items
that are neither but still needed -- each with a proper reason, and at
least one item addressing the SPRINT AS A WHOLE, not only individual
tasks -> **explicit Owner approval required before acting on them** (a
deliberate exception to this project's general autonomy-first default)
-> action items done first -> only then size the next NEW task with the
updated knowledge (never retroactively re-size an already-completed old
task). A mid-sprint realization Claude makes on its own never triggers a
re-estimate -- finish the sprint as planned, it surfaces in that
sprint's normal retro as an ESTIMATION WRONG finding. Only the Owner
himself changing scope mid-sprint triggers an immediate re-estimate.
Every retro ALWAYS reports the overall sprint estimate vs. actual (not
just per-item numbers), and its full data (comparison table, verdicts,
evidence, discussion, action items) is stored permanently in
docs/RETRO_LOG.md -- never left only in chat.

### Phase 3: every activity carries a category (added 2026-09-20, Owner directive)
Every backlog item gets a `category`: `delivery` (real product/feature
work) or `scrum_process` (sizing/retro/rubric/process-infrastructure
work). No item may lack one, same discipline as size/estimate -- see
docs/BACKLOG.json's `_category_values` and `_calibration_process`.
Real work that never becomes a sized backlog item (ad-hoc discussion/
research the Owner gives between sprints) still needs SOME category --
tracked in docs/OUTSIDE_SPRINT_LOG.md with its own sub-categories
(bookkeeping/research/discussion), never left untracked. Purpose: let a
future report compare the real cost of running this Scrum system itself
against the real cost of delivery work, to judge whether the overhead is
worth it.

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

## AI-characteristic defect discipline
Traditional QA is designed around how humans get things wrong. These rules
are designed around how *this* agent actually got things wrong (see the
2026-09-20 audit, docs/AI_NATIVE_TESTING_RESEARCH.md). Research basis: LLM
self-correction degrades without external feedback; same-family models
share correlated blind spots; coverage does not predict fault detection on
buggy code.

- **Never write against a remembered API.** Before calling any external
  library/framework API this repository does not already use somewhere,
  resolve the real symbol against the *actually installed artifact* and
  record the real output: Python -- `inspect.signature` / `dir()` / the
  real file under site-packages; Java -- the resolved dependency's real
  class or version-exact docs matching `pom.xml`, never generic docs.
  Grounding, not prompting, is what fixes phantom symbols/signatures. When
  what's uncertain is an API's *semantics* (routing, load balancing,
  transaction/filter ordering), a correct signature proves nothing -- it
  requires a real runtime exercise before it counts as verified.
- **A new `@Bean` of a framework-owned, auto-configured type is
  HIGH/CROSS_MODULE** (`RestClient.Builder`, `RestTemplate`,
  `WebClient.Builder`, `ObjectMapper`, `TaskExecutor`, `SecurityFilterChain`,
  any `*Customizer`), regardless of which directory it lives in, and
  requires a real full-context boot of every service sharing that context
  -- not a slice test. `@ConditionalOnMissingBean` matches by TYPE, so an
  unqualified consumer elsewhere silently takes your bean.
- **First-of-its-kind multi-process work must be verified multi-process.**
  The backlog rubric already defaults a first integration of a given kind
  to LARGE; verification must match. A mocked integration test never
  satisfies an integration acceptance criterion. Real registry + 2+ real
  instances + one real end-to-end request with a real token, asserted at
  the far end.
- **Cross-service calls require propagation and negative assertions.** For
  every new outbound service-to-service call: (a) assert the *outbound
  request* actually carries required headers (Authorization, correlation
  id) -- assert on the recorded request, never the response; (b) assert
  the downstream rejects the call when the credential is absent. A 200
  happy-path assertion cannot fail on a propagation bug.
- **SKIPPED is not PASSED.** Every verification report states pass/fail/
  skip counts. A HIGH or CRITICAL change whose mandatory suite was skipped
  (Docker absent, profile absent, tag excluded) is `UNVERIFIED` -- never
  `PASSED` -- and must name which gate did not execute and where it will.
- **A new test is not trusted until it has been observed failing.** Every
  new regression/acceptance test is run once against the unfixed code or a
  deliberately seeded mutation, observed to FAIL for the intended reason,
  and that real failure output recorded next to the pass. A passing new
  test proves nothing on its own.
- **Non-source artifact properties get a deterministic gate, never a
  judgment.** File mode bits, shebangs, line endings, encoding: a zero-LLM
  script in the STATIC tier. Minimum: every file with a `#!` shebang or
  under `scripts/` is mode 100755 in `git ls-files --stage`.
- **Any rule this project states as a number must be computed, not
  judged.** Tolerance ratios, size-vs-actual, coverage/mutation
  thresholds, cost-per-verified-outcome: the verdict is the real output of
  the real script (e.g. `agent/backlog.py`), quoted. The agent may
  interpret a computed table; it may not produce the classification. A
  narrative classification of a numeric rule is invalid by construction.
- **Write-capable subagents run in an isolated git worktree.** Pass
  `isolation: "worktree"` on every Agent call whose agent can Write/Edit.
  Read-only agents (Explore, qa-evaluator) may share the working directory
  because they cannot mutate it. Never run a write-capable background
  agent in the directory the main session is editing.
- **Independent evaluation is mandatory before "done" when any of these
  hold** -- invoke the `qa-evaluator` subagent:
  1. change classification is HIGH/CRITICAL, or blast radius is
     CROSS_MODULE/SYSTEM;
  2. acceptance criteria include the SECURITY or PRODUCTION category;
  3. the work was performed by a background/autonomous subagent -- i.e.
     the only account of what happened is another agent's self-report;
  4. any mandatory gate was skipped, degraded, or could not run locally;
  5. the backlog item is sized LARGE or XLARGE.
  May be skipped for SMALL/MEDIUM LOW-risk items where the implementer ran
  the real deterministic gate and the evidence JSON exists -- there the
  evidence is already independent of the claim, because an exit code is
  not an opinion.
  **Honest limit, stated so it is not oversold:** a second instance of the
  same model is not an independent mind, it is an independent *evidence
  path*. Expect it to catch unverified claims, skipped gates, and absent
  observable effects; do not expect it to catch subtle logic errors the
  implementer made, because same-family models share blind spots. Genuine
  model-diversity review would require a different model family or the
  Owner; neither is currently in the loop, and that is a known residual
  risk, not a solved problem.
- **The implementer never gets the last word on its own production
  success.** This already exists as a rule inside qa-evaluator; it belongs
  here too, because tonight it existed and was never invoked.
- **A diagnostic/verification tool must be proven to detect the known-bad
  case before its "clean" result is trusted, same as a test.** Real
  incident (Sprint 4, BL-032): a root-cause read structured evidence
  fields that had already been truncated to 2000 characters upstream
  (`output_tail = raw_output[-2000:]`) and reached a wrong conclusion --
  the evidence was real, the reading of it was careful, the *source* was
  already lossy. Extends the existing "a new test is not trusted until
  observed failing" rule to diagnostic scripts and evidence fields, not
  just regression tests: before trusting a truncated/summarized field as
  the basis for a root-cause claim, confirm by re-running with full,
  untruncated output at least once.
- **Never let a sprint's merge phase count as done because a task tracker
  says so.** Real incident (Sprint 4): two worktree branches were fully
  finished and marked `done` in `docs/BACKLOG.json`, but the parent
  session never actually ran `git merge` for them -- caught by accident,
  not by checking. Before writing a sprint's retro, run
  `python agent/verify_sprint_merged.py <branch1> <branch2> ...` for
  every worktree branch dispatched that sprint -- it exits non-zero and
  names exactly which branch(es) are not real ancestors of `HEAD`
  otherwise. A `git log --graph` glance is not a substitute; run the
  script.
- **A commit that claims to resolve a tracked item must be checked, not
  trusted.** Real incident, four separate times in one sprint (Sprint 4):
  real work shipped without `docs/ACTION_QUEUE.json`/`docs/BACKLOG.json`
  reflecting it -- including once where the tracking file WAS touched in
  the same commit, just not with the actual status flip for the item
  being claimed. Run `python agent/verify_tracking_updated.py <since-ref>`
  before closing a sprint -- it checks both that the tracking doc was
  touched AND that the referenced item's real, current status (at `HEAD`,
  not at the commit) actually shows it resolved.
- **Reserve an `ACT-`/`BL-` id before handing it to a fork, never let a
  fork mint its own.** Real incident (Sprint 4): two concurrent forks
  each independently assigned `ACT-015` to two different, unrelated
  findings, because both read the same sprint-start snapshot of
  `docs/ACTION_QUEUE.json`. Independently confirmed by external research
  (a real study of 142k+ agent-authored PRs) as a known real failure
  class with the same recommended fix. Before dispatching a fork whose
  task might create a new tracked item, run
  `python agent/check_id_available.py <prefix>` (or a specific id) and
  give the fork that exact id in its dispatch prompt -- don't let it
  choose.
- **Check declared/likely file scope across concurrently-dispatched forks
  before merging, advisory not exclusive.** `python agent/
  detect_scope_conflicts.py <base-ref> <branch1> <branch2> [...]` reports
  real file-level overlaps between branches (computed from real `git
  diff`, not from task descriptions) -- an overlap means the merge needs
  real attention (order, conflict resolution), not that either fork's
  work is wrong. Deliberately advisory: a real incident this same sprint
  (`BL-030`) found and fixed a genuine bug in code adjacent to, not
  inside, its declared scope -- a hard exclusive-lock model would have
  blocked that.
- **Two known-real problems from this same audit remain genuinely
  unsolved, stated honestly rather than papered over with a rule that
  looks like a fix:** (1) forked subagents sometimes stall mid-task after
  launching a real long-running local command and never act on its real
  completion -- root cause unconfirmed, plausibly a platform-level
  turn/notification-loop issue outside this project's own code. Mitigate
  by having a fork announce before running anything that will take
  several minutes, and by the parent session proactively checking in on
  such forks rather than passively trusting a "completed" notification
  -- but this is a bandage on the symptom, not a fix for the cause. (2) no
  concrete trigger defines when "the same problem reported a second time"
  is similar enough to count as a real recurrence demanding a process
  change rather than another one-off patch -- flagged as a real open
  question, not resolved by naming it.

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
