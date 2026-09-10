# Knowledge Index

Session-level engineering knowledge records — narrative accounts of major
build periods, written for future reuse (interview prep, onboarding a new
session, the future Interview/Knowledge Book). These are NOT a
replacement for the durable project-state files; they reference those
files and Git commits rather than duplicating them.

Source of truth stays layered as always:
1. Runtime/Git/test evidence
2. docs/PROJECT_STATE.json, docs/DECISIONS.md, docs/LESSONS.md
3. These session records (narrative, "why it happened this way")

## Sessions

- [2026-09-09 — Agentic Delivery Platform: Control UI, Dashboard, and the security lessons behind them](sessions/2026-09-09-agentic-platform-build.md) — V3 tool-using agent → MCP → incremental RAG → safe propose/approve/apply → live browser human approval → Evidence Dashboard. Covers 3 real security-gap findings-and-fixes and 2 real UI defects found through actual use.
- [2026-09-10 — Trainer demo: already-satisfied requirement misreported as FAILED, then a follow-on SSE terminal-state bug](sessions/2026-09-10-trainer-idempotency-fix.md) — two real bugs found via public trainer use, back to back. First: a correct "nothing to do, already implemented" no-op was labeled FAILED (fixed with a new NO_CHANGE_NEEDED terminal state). Second: introducing that new state broke SSE stream termination (stuck at STARTING forever) because the delivery layer had its own separate, now-stale terminal-state list — fixed with one authoritative TERMINAL_RUN_STATES set. Both fixed with regression tests built from the real incident data.
