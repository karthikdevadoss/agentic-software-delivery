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
- [2026-09-10 — Trainer demo: three real bugs found back-to-back via public use](sessions/2026-09-10-trainer-idempotency-fix.md) — (1) a correct "already implemented, nothing to do" no-op was labeled FAILED, fixed with a new NO_CHANGE_NEEDED terminal state; (2) introducing that state broke SSE stream termination (one authoritative TERMINAL_RUN_STATES set fixed it); (3) a Cloudflare Quick Tunnel silently dropped an entire SSE stream with zero client-visible signal, fixed by making HTTP polling an always-on safety net rather than a failure-triggered fallback. Each fixed with a regression test built from the real incident data. Also surfaces a real, repeatable, still-open Windows subprocess encoding defect causing false deploy failures.
