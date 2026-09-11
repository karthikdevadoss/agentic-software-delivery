---
name: requirement-contract
description: Turn a raw Workbench requirement into an Acceptance Contract (requirement_id, target application, expected observable effect, required gates, allowed terminal outcomes) BEFORE any implementation work starts. Use when a requirement is received and success criteria have not yet been made explicit.
---

# Requirement → Acceptance Contract

**Prescribed duty (single):** given a raw requirement, produce one
`agent/acceptance_contract.py::AcceptanceContract` describing what "done"
means — nothing else. This Skill does not implement, test, or verify
anything; it defines success *before* coding, per
docs/ARCHITECTURE_V2.md §5.

## Canonical sources (reference, do not restate)

- Schema + validation logic: `agent/acceptance_contract.py`
- Deterministic gate names it may reference: see
  `KNOWN_DETERMINISTIC_GATES` in that same file — never invent a gate
  name that isn't real code somewhere.
- Real risk/complexity classification: `agent/risk_policy.py::classify`
  (deterministic — call it, never re-derive risk by judgment).
- Real terminal outcomes the runtime can produce:
  `agent/web_server.py::TERMINAL_RUN_STATES`.

## Inputs

- The raw requirement text.
- The target application's known identity (for this project, currently
  the Customer app at the URL in `agent/web_server.py::PUBLIC_CUSTOMER_APP_URL`
  — never invent a different target).

## Outputs

- One `AcceptanceContract` instance (or its `to_dict()` JSON form) with:
  - `requirement_id`, `requirement_text`, `target_application`
  - `expected_observable_effect` — MUST be something independently
    checkable in real production output (HTML, API response, file
    content). A contract whose effect can't be independently verified
    reproduces the exact false-success incident in docs/LESSONS.md
    (`trainer-7769757e`) — refuse to produce one.
  - `required_gates` — only names from `KNOWN_DETERMINISTIC_GATES`.
  - `risk` — from `risk_policy.classify()`, never guessed.
- Run `contract.validate()` and report any problems before handing the
  contract onward — do not silently pass along a contract with unresolved
  validation problems.

## Evidence required to consider this Skill's duty complete

- The contract's `validate()` returns `[]`.
- `expected_observable_effect` names a concrete, fetchable/checkable
  artifact, not a vague description ("the page looks right" is not
  acceptable; "the response HTML contains `<button id=\"create-btn\">Create Customer</button>`"
  is).

## Must NOT

- Must NOT implement the change.
- Must NOT run tests or deployments.
- Must NOT invent a deterministic gate that doesn't exist in code.
- Must NOT lower `expected_observable_effect` to something vague just to
  make a contract "pass" validation faster.
- Must NOT expand scope beyond the single requirement given.
