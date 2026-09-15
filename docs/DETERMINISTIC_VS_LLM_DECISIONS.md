# Deterministic vs. LLM Decisions

A short index, not a duplicate — the full per-capability reasoning already
lives in `docs/INTELLIGENCE_PLACEMENT_V3.md` (Phase 1's audit). This
document is the compact summary the directive's Phase 25 "Required
Architecture Artifacts" list asks for.

## The rule this project actually enforces

An LLM is called only where genuine semantic interpretation, open-ended
hypothesis generation, or novel proposal-writing is the actual ask — never
for arithmetic, authorization, workflow transitions, risk policy, test
pass/fail, route existence, Git state, hash identity, DB constraints,
retry counters, time arithmetic, cost calculations, deployment state,
production state, or business invariants. Every one of those is decided by
compiled code, a DB constraint, a real HTTP check, or a hash comparison —
see `docs/EVIDENCE_AUTHORITY_MODEL.md`'s precedence list and
`docs/INVARIANT_REGISTRY.md` for the actual enforcement points.

## Where this project genuinely uses an LLM today, and why

| Call site | Purpose (per `agent/reasoning_gateway.py`'s allowlist, where wired) | Why deterministic code can't do this instead | What independently verifies the output |
|---|---|---|---|
| `agent/triage_execution.py::diagnose()`/`diagnose_b()`/`diagnose_c()` | `NOVEL_ROOT_CAUSE_HYPOTHESES` | Root-causing a defect from evidence requires genuine hypothesis generation over an open-ended space, not a lookup | Nothing — deliberately advisory/display-only, traced through every caller in the audit to confirm zero downstream code branches on it |
| `agent/triage_execution.py::generate_candidate_patch()`/`_b()`/`_c()` | `NOVEL_IMPLEMENTATION_PROPOSAL` | Writing an actual code fix is generative by nature | Real isolated `mvnw compile` + the real scenario's `mvnw test` (this session's fix) — never trusted without both passing, and even then only becomes *eligible* for a required human approval, never auto-promoted |
| `agent/backend_planning.py`'s LLM-informed impact analysis | (not yet wired through `reasoning_gateway.py` — see `docs/ARCHITECTURE_V3_DECISIONS.md` D5) | Requires reading RAG-retrieved context and reasoning about which files are actually relevant | `check_groundedness()` — deterministically confirms every file the analysis claims to have used was actually retrieved, never merely plausible-sounding |
| `agent/main.py` (V1 CLI) / `agent/agent_loop.py` (V3 tool-calling loop) | Multi-turn planning/investigation — not a single-shot advisory ask | Deciding *what to investigate next* in an open-ended repository is genuinely exploratory | Read-only tool boundary (`agent/tools.py`) + the separate write/build approval gates downstream — the loop itself has no write/deploy authority |

## What is explicitly NOT LLM-decided, verified by direct inspection this session

- **Workflow transitions** — `agent/web_server.py::Run.set_status()`, a
  Python dict-membership check (this session's fix).
- **Authorization** — `SecurityConfig.java`'s compiled route matrix;
  `agent/execution_tools.py`'s exact 4-key dispatch dict (`approve_edit`/
  `reject_edit` provably absent).
- **Test pass/fail** — real `mvnw`/`pytest`/Playwright exit codes, never a
  model's self-assessment.
- **Route existence** — Starlette's own `Route.matches()`
  (`agent/test_showcase_data.py`, `e2e/link-integrity.spec.js`, this
  session's fixes).
- **Git/candidate identity** — SHA256 hash equality
  (`agent/triage_promotion.py`, `agent/write_tools.py`).
- **Deployment/production state** — real HTTP checks against the live URL,
  timestamp-parsed (`agent/demo_execution.py`).
- **Cost arithmetic** — a versioned fixed pricing table applied to real
  `response.usage` fields (`agent/pricing_config.py`), never model-estimated.

See `docs/INTELLIGENCE_PLACEMENT_V3.md` for the full per-capability
evidence trail behind every row above.
