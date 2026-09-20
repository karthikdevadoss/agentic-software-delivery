# Outside-Sprint Activity Log

Per the Owner's standing rule (2026-09-20): every activity Claude does
carries some category — either it's a sized item inside an active sprint
(`docs/BACKLOG.json` + `docs/RETRO_LOG.md`), or it's logged here under
**Outside Sprint**, with a sub-category. Nothing happens with no
category at all. This file is the lightweight, public index of the
latter — entries here are deliberately non-personal/non-sensitive
(what happened, category, date, one line); any detailed content that
belongs in the private `karthik-ai-context` repo (e.g. personal
communication-style commentary) is referenced, not duplicated here.

Sub-categories used so far: `bookkeeping` (Claude's own private notes-
to-self, e.g. memory files — background housekeeping, not project work),
`research` (research/analysis requested between sprints), `discussion`
(process design conversation that doesn't produce a sized deliverable),
`deliverable` (a real artifact produced ad hoc, outside any sized backlog
item — e.g. a one-off external-facing document).

---

## 2026-09-20

- **research** — Prompting-style coaching, baseline assessment. Real
  research + analysis of the Owner's own real prompts from this
  session's transcript, done by a fresh Opus-model agent. Full content
  in the private repo (`karthik-ai-context/coaching/PROMPTING_STYLE_LOG.md`)
  — personal commentary about the Owner's communication style, not
  project methodology, so it stays there.
- **discussion** — "How ready is the app for full NRG-interview
  coverage" status assessment, given directly in chat (not written to a
  separate file — a point-in-time status report, not a durable finding
  requiring its own record beyond this index entry).
- **discussion** — Scrum-process review (sizing rubric / calibration
  loop / retro format corrections) — the actual findings and fixes from
  this are recorded in `docs/RETRO_LOG.md` and `docs/BACKLOG.json`'s
  `_calibration_process`, since they're process-methodology content, not
  personal — this index entry exists only so the *activity itself*
  (a review happened, outside any sprint) has a category.
- **research** — NRG project real-tech-stack gap analysis (candidates
  only, none confirmed as claims). Full content in the private repo
  (`karthik-ai-context/coaching/NRG_STACK_GAP_ANALYSIS.md`) — personal
  career-fact content, stays there per this project's public/private
  separation rule.
- **discussion** — interactive role/boundary definition for the NRG
  project (Q&A format) and the AI-adoption-work section, both confirmed
  and written into the private career record — personal, stays there.
- **research** — deep research (Fable-model agent, real web research)
  into a realistic, non-idealized profile across NRG/BCBSA/Marsh —
  technology, deployment, production support, architecture. Full content
  in the private repo (`karthik-ai-context/coaching/REALISTIC_PROFILE_DEEP_RESEARCH.md`)
  — personal career-fact content, stays there.
- **discussion** — interactive follow-up: 11 open questions from the
  deep-research doc answered, real detail confirmed across NRG/BCBSA/
  Marsh (billing-as-façade, real messaging hands-on work, BCBSA/Marsh
  role-scope differences). Full content in the private repo's
  `context/CAREER_HISTORY.md`.
- **discussion** — Chase/Northern Trust tech timeline corrected and
  verified against real public Spring Boot release history. Private repo.
- **research** — real database-usage research across the whole career,
  per-project list confirmed. Private repo.
- **discussion** — pre-next-sprint status check ("are you sure we don't
  have to talk more") — surfaced and fixed 2 real gaps (this log being
  stale, the category-tagging system not yet built) and 2 real decisions
  (app/billing-facade rework approved as `ACT-013`, prompting-coaching
  check-in sequencing agreed). No separate file — findings are recorded
  where the fixes actually landed (`docs/BACKLOG.json`, `ACTION_QUEUE.json`).
- **research** — deep research (Opus-model agent, real web research)
  into AI-native testing/verification strategy, grounded in a real audit
  of 7 actual bugs from this session. Full content in this repo's own
  `docs/AI_NATIVE_TESTING_RESEARCH.md` — public, process-methodology
  content, not personal, so it lives in the main docs tree rather than
  this index alone.
- **discussion** — sprint-scope negotiation (4 rounds of correction:
  interview-book deprioritized, app/career work folded back in,
  stabilization prioritized, a missed standing Scrum-research commitment
  caught) — led directly to the new mandatory pre-sprint-proposal
  checklist in `docs/BACKLOG.json`'s `_calibration_process`.
- **deliverable** — built and published a one-page public Artifact
  ("Agentic Software Delivery — Systems & Engineering Overview") for the
  Owner's AI trainer to review, explicitly requested outside any sprint.
  Covers architecture, the AI-native testing discipline, the Scrum-for-AI
  calibration data, real incidents, the documentation system, company
  thesis, honest gaps, and roadmap — then, per follow-up direction,
  expanded with a dedicated section on the AI-engineering practice itself
  (memory/context/skills/session/token/model handling), an interactive
  Claude-`sample`-backed Q&A panel grounded only in the page's own
  content (kept deliberately minimal after an explicit "no bugs" steer —
  single question/single answer, no chat-thread state), and direct
  GitHub links to every primary source document referenced, since the
  Owner confirmed his trainer's own AI (Claude/Grok) will analyze this
  directly rather than a human reading it start to end. Not tracked in
  `docs/BACKLOG.json` — no sizing, no retro entry, per the Owner's
  explicit "not part of any sprint" instruction.
