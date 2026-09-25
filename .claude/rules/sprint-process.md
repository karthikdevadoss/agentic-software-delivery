---
paths:
  - "docs/BACKLOG.json"
  - "docs/ACTION_QUEUE.json"
  - "docs/RETRO_LOG.md"
  - "docs/OUTSIDE_SPRINT_LOG.md"
  - "agent/backlog.py"
  - "agent/check_id_available.py"
  - "agent/detect_scope_conflicts.py"
  - "agent/verify_sprint_merged.py"
  - "agent/verify_tracking_updated.py"
---

# Sprint / backlog / retro process

Moved verbatim out of CLAUDE.md on 2026-09-25 (Phase 3, context efficiency):
the three sizing/calibration/category sections, plus the four sprint-mechanics
bullets from "AI-characteristic defect discipline" that are about running a
sprint rather than about writing code. Not one word was changed and nothing
was dropped -- this loads whenever a sprint/backlog/retro file is actually
read, instead of on every session start.

These rules are unchanged in force. If you are sizing, sprinting, merging a
sprint, closing a tracked item, or writing a retro, they apply exactly as they
did when they lived in CLAUDE.md.

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


## Sprint mechanics (moved from "AI-characteristic defect discipline")

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
