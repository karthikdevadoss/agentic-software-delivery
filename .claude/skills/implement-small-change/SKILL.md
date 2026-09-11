---
name: implement-small-change
description: Implement a small, bounded, already-scoped source change against an existing Acceptance Contract for the Customer app — investigate the repo, propose, apply, and compile. Use when an Acceptance Contract already exists and someone needs to actually make the change happen.
---

# Implement a Small Change

**Prescribed duty (single):** given an existing `AcceptanceContract`, make
the smallest correct source change that satisfies
`expected_observable_effect`, using the project's already-existing
propose → approve → apply → compile pipeline. This Skill is the
"agentic judgment" half of the split described in
docs/ARCHITECTURE_V2.md §4 (Deterministic vs. Agentic Classification) —
it does NOT decide whether to run (that's `agent/risk_policy.py`), and it
does NOT certify success (that's the `qa-evaluator` subagent + the
`production-verify`/`test-change` Skills).

## Canonical sources (reference, do not restate)

- The real tool surface this Skill drives:
  `agent/execution_tools.py::EXECUTION_TOOL_SCHEMAS` (propose_source_change,
  apply_approved_source_change, run_controlled_compile, run_controlled_tests).
- Security boundary it must never try to route around:
  `agent/tools.py`/`agent/write_tools.py` (path traversal, symlink,
  secret-filename, write-scope restriction — enforced in code, not by
  this Skill's own discipline).
- Repository-workspace precondition:
  `agent/web_server.py::_check_repository_workspace_ready` — verify this
  is ready (or trust the orchestrator already checked it) BEFORE
  proposing any change. See docs/LESSONS.md's `trainer-6aedf022` incident
  — a real cloud run once reached COMMITTING with no usable git
  repository at all, after real API cost had already been spent.
- Session-startup and stability discipline: CLAUDE.md's "Session
  startup"/"Proactive action policy"/"Stability / Execution Discipline"
  sections — this Skill operates inside that discipline, not instead of it.

## Inputs

- One valid `AcceptanceContract` (from the `requirement-contract` Skill).

## Outputs

- A real, applied source change (via `apply_approved_source_change`),
  scoped to exactly the file(s) the requirement needs.
- A real compile result (`run_controlled_compile`).
- A plain evidence summary: files changed, why, compile result — handed
  to the `test-change`/`production-verify` Skills and ultimately the
  `qa-evaluator`, never self-certified as "done" here.

## Must NOT

- Must NOT touch any file outside `expected_observable_effect`'s
  affected scope without stating why and re-checking against the
  contract.
- Must NOT claim success — this Skill's output is "a change was applied
  and compiled," never "the requirement is satisfied" or "PRODUCTION
  VERIFIED." Only the `qa-evaluator` (§7 of docs/ARCHITECTURE_V2.md)
  makes that call, from independent evidence.
- Must NOT bypass or "helpfully explain around" a security-boundary
  rejection (traversal/symlink/secret-name/scope) — treat every such
  rejection as final, report it, do not retry with a workaround.
- Must NOT invent a requirement beyond the one in the contract.
- Must NOT run tests or make the commit/deploy decision — those are the
  `test-change` and `production-verify` Skills' duties.
