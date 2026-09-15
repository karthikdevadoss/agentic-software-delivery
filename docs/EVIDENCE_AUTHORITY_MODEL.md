# Evidence Authority Model

Phase 19 of the Base Architecture V3 directive. Defines the real
precedence this project already applies (in some places implicitly) when
two sources of "truth" disagree, and makes it explicit so future sessions
apply it consistently rather than reinventing it per-incident.

## Precedence (highest authority first)

1. **Mathematical/computational facts.** A SHA256 hash equality check
   (`agent/triage_promotion.py`, `agent/write_tools.py`), a Starlette
   `Route.matches()` result (`agent/test_showcase_data.py`). Nothing
   overrides these — they are definitions, not observations.
2. **Direct runtime/production observation.** A real HTTP GET against the
   live public URL (`agent/demo_execution.py::wait_for_new_deployment()`'s
   primary evidence), a real `pg_stat_activity` query (the AEQ-010
   incident root-cause). This is what this session used to independently
   re-verify every subagent-reported fix — never trusted the report alone.
3. **Compiler/static-analysis facts.** A real `mvnw compile`/`mvnw test`
   exit code (`agent/build_tools.py`, `agent/verify_change.py`). Cannot be
   talked around by prompt text; either the code compiles or it doesn't.
4. **Structured sensor evidence from a real test run.** `agent/test_*.py`
   suite results, `e2e/*.spec.js` Playwright results, CI job status
   (polled by exact run ID via the public GitHub Actions API this
   session, not assumed from a local push succeeding).
5. **Durable event-ledger records.** `agent/event_ledger.py`'s Postgres
   rows — real, but a *record of* an observation, one step removed from
   observing it directly right now.
6. **Approved deterministic policy output.** `agent/risk_policy.py`'s
   classification, `agent/change_risk.py`'s risk/blast-radius label —
   authoritative for what it decides, but itself downstream of rules a
   human wrote, not a direct observation.
7. **Documentation** (`docs/PROJECT_STATE.json`, `docs/PROJECT_STATUS.md`,
   etc.). Useful as a map of where to look, explicitly **not** trusted
   over live code per `CLAUDE.md`'s own rule ("actual repository state
   wins on conflict") — this session found and corrected several places
   where a doc's claim needed re-verifying against real code before being
   used (e.g. the Phase 1 audit's own methodology statement).
8. **Semantic retrieval** (`agent/rag_index.py`/`agent/backend_rag_index.py`
   embeddings). Explicitly non-authoritative everywhere it's used —
   `backend_planning.py::check_groundedness()` independently verifies every
   file an LLM's analysis claims to have used was actually retrieved,
   never trusting the retrieval-informed claim on its own.
9. **LLM inference.** Always `authority: "ADVISORY"`
   (`agent/reasoning_gateway.py`) — the lowest tier, by design. Every real
   call site in this codebase already independently verifies or gates
   what the model returns before it has any effect (compile+test for
   Triage candidates, display-only for diagnosis, groundedness-checked for
   RAG-informed analysis).

## Conflict rule

Lower-authority evidence must never silently override higher-authority
fact. When two sources genuinely disagree, the response is: **surface the
conflict, investigate with the highest-authority evidence available, and
report `UNKNOWN` rather than guess** — this is not a new rule invented for
this document, it is the pattern this project already used for real
incidents:

- The overnight hardening session found `docs/PROJECT_STATE.json`'s own
  `next_phase`/`next_action` had gone stale relative to 6 subsequent
  commits (documentation, tier 7, silently contradicting reality) —
  corrected by re-deriving from real git history (tier 1/2), not by
  trusting the stale doc.
- `agent/demo_execution.py`'s `_decide_deployment_outcome()` treats
  Railway CLI status (tier 6-adjacent, a third-party tool's own report) as
  corroborating only, never primary, exactly because a live incident
  proved CLI status and real production state can genuinely disagree.
- This session's own concurrency incident (see
  `docs/ARCHITECTURE_V3_DECISIONS.md` D7): a subagent's self-reported
  "completed" status (tier 9-adjacent — an agent's own claim about its
  own work) was never trusted without independently re-running the real
  test suites and re-checking `git log`/`git status` (tier 1/2) — which is
  exactly how the concurrency issue and the file-overwrite mistake were
  both caught.

## What this changes going forward

Nothing structural yet — every example above already existed before this
document named the pattern. The value of writing it down is that a future
session (or a genuine second domain reusing this platform, per
`docs/REUSABLE_PLATFORM_BOUNDARIES.md`) has one place naming the
precedence explicitly, instead of it living only as implicit practice
scattered across incident write-ups.
