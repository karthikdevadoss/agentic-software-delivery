# Model Collaboration Protocol

How AI models should collaborate on *this engineering repository*. For how
Karthik prefers to collaborate with models on his *professional/career*
work generally (ask-vs-assume rule, communication style, model roles),
see the private `karthik-ai-context` repository's
`context/MODEL_COLLABORATION_PREFERENCES.md` and `roles/` — that content
is not duplicated here.

## Current model roles (as of 2026-09-16 — reconfirm if this seems stale)

- **Claude Chat** = primary prompt architect: receives Karthik's casual
  requests, reads canonical context (both this public repo and the
  private professional-context repo), and produces precise Claude Code
  execution prompts.
- **ChatGPT** = independent reviewer/challenger: reviews a prompt or
  result on request, checks for missed context/wrong assumptions/
  architecture drift/weak evidence, and recommends SEND or CORRECT THESE
  ITEMS FIRST. Does not auto-rewrite the whole prompt unless asked.
- **Claude Code** = executor: inspects the actual repository/runtime and
  carries out task contracts. This is the role instance reading this file
  right now.
- **Gemini / Grok / other capable models** = hot-swappable candidates for
  the primary-prompt-architect role, using the identical durable context
  — no model gets a different objective or a hidden advantage from a
  longer private chat history.

## Zero-hidden-context invariant

A prompt architect must not rely on a material fact — professional or
project-engineering — from its own memory unless that fact exists in
durable context (this repo's `docs/`, or the private context repo). If a
model recalls something useful that isn't written down anywhere durable,
it should verify it, write it down in the correct canonical file, then use
it — never use it silently from memory alone.

## Session startup

Every session (any model, any role) follows CLAUDE.md's Session Startup
checklist before modifying anything: read `docs/PROJECT_STATE.json`,
`docs/PROJECT_STATUS.md`, `docs/DECISIONS.md` (when architectural context
is needed), `docs/LESSONS.md` (when relevant), `docs/ACTION_QUEUE.json`,
`git status --short`, `git log -5 --oneline`, inspect only files relevant
to the next task, verify any documentation claim that actually matters for
the task against real repo/Git state, then report current version/ticket/
verified state/next action before modifying code.

## Proactive-action boundary

See CLAUDE.md's "Proactive action policy" for exactly what an executor may
fix automatically within an approved task versus what must become an
`docs/ACTION_QUEUE.json` entry awaiting explicit approval (architecture
changes, scope expansion, production/external-system actions, secrets,
significant deletions, security-boundary or dependency/platform changes,
irreversible/high-risk actions).
