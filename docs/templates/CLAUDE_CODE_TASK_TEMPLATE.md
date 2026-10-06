# Claude Code task contract template

BL-125/BL-127/BL-128 (Sprint 27, SI audit BK-27/BK-29/BK-30). This is the
reusable shape for a prompt that launches an unattended Claude Code session
(e.g. `claude -p --dangerously-skip-permissions < prompt.md`) against this
repository. It generalises the real contract `docs/indra/SPRINT_27_5H_PROMPT.md`
was given and launched from (`docs/indra/_sprint27_launch.cmd`), which is
itself the worked example this template is built from.

Validate a filled-in contract with `python agent/check_task_template.py
<path-to-prompt.md>` before launching it — see "Enforcement" below.

Copy the sections below into a new file under `docs/indra/` (or this
project's equivalent dispatch location) and fill in every `<...>`.
Sections marked **REQUIRED** must be present and non-empty; a contract
missing one of them is not ready to launch.

---

## Role / session identity **REQUIRED**

- Role: `<name, e.g. Indra>` (implementer | planner | reviewer — pick one)
- Model: `<e.g. Sonnet>`
- Wall clock budget: `<e.g. ~5 hours>`
- Repo: `<absolute path>`
- Branch: `<branch to create/use>`, based on `<base ref, e.g. origin/master>`

## Bounded production calls **REQUIRED**

State the real, numeric ceiling on any call this task makes against a
live/production system (API requests, deploys, model calls that cost money).
If the task makes none, say so explicitly — "zero production calls" is a
valid and preferred answer, not an omission.

- `<system>`: max `<N>` calls / <window>. Enforced by: `<real mechanism,
  e.g. the endpoint's own cap, or "not enforced — manual discipline only">`.

## Hard stop / exit rules **REQUIRED**

- Wall-clock or completion stop condition.
- What happens when a task item is blocked (the default for this project:
  skip immediately, log the blocker, move to the next independent item —
  never idle-wait, never poll the Owner).
- What is forbidden this session (production deploy without approval,
  force-push, secrets in commits, specific named out-of-scope items).

## Mission **REQUIRED**

One paragraph: why this task exists right now, in plain language.

## Verified facts only, never asserted (BL-128) **REQUIRED**

> The rule, stated once so every task contract carries it: **a prompt may
> not assert a fact about the Owner or about this system that it has not
> verified.** A hypothesis is labelled a hypothesis. State, for every
> non-obvious factual claim this contract relies on, which of these it is:

- **Facts verified before this contract was written** (name the file/command
  that verified each): `<list, or "none">`
- **Facts assumed/hypothesised, explicitly labelled as such, to be checked
  by the implementer before being relied on**: `<list, or "none">`

A contract that states a hypothesis as settled fact reproduces the real
defect this rule exists to prevent (SI audit BK-30: a contract's own stated
cause was only half right and had been written as settled).

## Task queue **REQUIRED**

One entry per task. Every field below is required per task, not just once
for the whole contract — BL-127's enforcement checks each one individually.

### `<task id>` — `<short title>` (`<time estimate>`)
- **What:** `<the change>`
- **Why:** `<reason>`
- **Page purpose** (required whenever the task builds or changes a
  user-facing page/surface; write `N/A -- not a page change` otherwise):
  `<what this page is FOR, in one sentence, before any build starts>`
- **Quality acceptance** (required for every task, not only page changes):
  `<what "good", not just "present", looks like for this task — e.g. "the
  numbers shown equal the latest real eval_runner.py output", not merely
  "the page renders">`
- **Done when:** `<observable, checkable condition>`
- **Skip if:** `<the specific blocked condition that makes skipping correct>`

## Out of scope **REQUIRED**

Explicit list of what this task must NOT do, even if it would be easy or
tempting mid-session (production deploys, other teams'/agents' work,
Owner-only decisions, named forbidden actions).

## Committed report **REQUIRED**

- Path the end-of-session report must be written to.
- Minimum contents: start/end time, branch + tip SHA, a table of task ID →
  done/skipped/blocker → commit SHA(s) → tests, full suite count if run,
  push status, next-estimate stub for anything unfinished.

---

## Enforcement

`agent/check_task_template.py` is a deterministic, zero-LLM gate (same
tier as the STATIC file-mode gate, CLAUDE.md's "AI-characteristic defect
discipline"): it reads a contract markdown file and fails closed, naming
which `**REQUIRED**` section is missing, rather than trusting that a human
or an agent remembered to fill every field in. It does not and cannot check
*truthfulness* of what's written (that is what the five evidence rules and
DISHONEST status are for) -- only that the required structure exists before
a task is considered launch-ready. Run it before dispatching any new task
contract built from this template:

```
python agent/check_task_template.py docs/indra/<your-contract>.md
```

Historical note: `docs/indra/SPRINT_27_5H_PROMPT.md` predates this
template and validator (it was the worked example this template was built
from, not built against it) and is not expected to pass the validator
retroactively -- it is not rewritten here. Contracts written from Sprint 27
onward should pass it before launch.
