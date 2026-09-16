# Project Context Index (model-neutral entry point)

This directory exists so that **any** LLM acting as primary prompt
architect — not only whichever one has the longest chat history with
Karthik — can pick up this project cold. It points to canonical detail
rather than duplicating it; when in doubt, the file linked below is the
source of truth, not this index.

Read `START_HERE.md` (repo root) first for the full session-startup
sequence (CLAUDE.md's Session Startup checklist). This index is a
narrower companion for a model that only needs project *purpose and
collaboration protocol*, not full engineering state.

| Question | Canonical file |
|---|---|
| Why does this project exist, what's the end goal? | `PROJECT_PURPOSE_AND_GOALS.md` (this dir) → `docs/COMPANY_VISION.md` |
| What are the non-negotiable engineering rules? | `OWNER_ENGINEERING_PRINCIPLES.md` (this dir) → `docs/CONSTITUTION.md` |
| How should an AI model collaborate on this repo? | `MODEL_COLLABORATION_PROTOCOL.md` (this dir) |
| What's true right now (version, phase, blockers)? | `CURRENT_ENGINEERING_CONTEXT.md` (this dir) → `docs/PROJECT_STATE.json`, `docs/PROJECT_STATUS.md` |
| What architecture decisions were made and why? | `docs/DECISIONS.md` |
| What reusable technical lessons exist? | `docs/LESSONS.md` |
| What's the roadmap / unresolved ideas? | `docs/ROADMAP.md`, `docs/IDEAS.md` |
| What small action items are open? | `docs/ACTION_QUEUE.json` |
| What real resources/URLs exist? | `docs/RESOURCE_REGISTRY.md` |

## Private professional context

Karthik's private career/job-search/resume/interview/trainer context lives
in a **separate, private** repository, `karthikdevadoss/karthik-ai-context`
— deliberately not in this public repo. This public entry layer does not
link its contents because that repository is private by design; if you
are a prompt architect with access to it, start there at
`CONTEXT_BOOTSTRAP.md` for professional context, and use this directory
for public engineering-project context. See that repository's
`CONTEXT_PRECEDENCE.md` for how the two interact.

**Standing cross-model write-back rule:** that repository's
`AGENT_PROTOCOL.md` is the single binding statement of "no agent may end a
session holding durable knowledge that isn't committed to canonical repo
files" — applies to any agent, any model, across both repositories. Not
duplicated here; read it there.

## Note on scope

This entry layer intentionally does not restate engineering detail already
canonical elsewhere in `docs/` — see CLAUDE.md's durable-state rules: one
canonical home per fact, no duplication.
