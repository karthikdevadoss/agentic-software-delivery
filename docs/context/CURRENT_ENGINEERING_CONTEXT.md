---
last_updated: 2026-09-16
---

# Current Engineering Context (pointer)

**This file is a pointer, not a snapshot** — always prefer
`docs/PROJECT_STATE.json` and `docs/PROJECT_STATUS.md` themselves over
anything restated here, since those update far more often than this
index does.

## Verified at last check (2026-09-16, during the context-portability migration)

- HEAD: `81e81e0`. Working tree: clean. `git log -5 --oneline` showed
  recent work on: navigation-consistency fix (AEQ-024, commit `4a8f738`),
  a `testing-strategy` Skill (commit `c977087`), an agent-decision eval
  suite reported infrastructure-complete but execution-blocked by
  Anthropic API billing (commit `079f36f`), and trainer homework
  documentation (commits `67bdcac`, `81e81e0`).
- `docs/ACTION_QUEUE.json`: 23 items — mix of `open`, `verified`,
  `deferred`, `in_progress`, and one `ready_for_human_approval`
  (`TRIAGE-CANDIDATE-PROMOTION-PIPELINE`). Read that file directly for
  current item-level detail; do not treat this line count as current
  without re-checking, it drifts quickly.
- `docs/RESOURCE_REGISTRY.md`'s Git-repository entry was found stale
  during this migration (it claimed no remote was configured, while
  `git remote -v` shows `origin` pointing at
  `github.com/karthikdevadoss/agentic-software-delivery.git`) — flagged
  for correction; check whether it has since been fixed.

## Known open trainer work (Session 2/3)

Full detail lives in the private `karthik-ai-context` repository's
`context/TRAINER_AND_WORKSHOP_CONTEXT.md` (trainer/career context is
private). Publicly visible evidence of this work exists in this repo at
`.claude/skills/testing-strategy/SKILL.md` and `agent/evals/`.

## How to use this file

Treat it as a "where to look" pointer for a model with no session memory,
not as ground truth — always re-verify against `docs/PROJECT_STATE.json`,
`docs/PROJECT_STATUS.md`, `git status`, and `git log` before acting, per
CLAUDE.md's Session Startup checklist.
