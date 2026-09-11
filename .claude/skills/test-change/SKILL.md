---
name: test-change
description: Decide and record the truthful testing terminal state (PASSED, NOT APPLICABLE with a verified reason, or FAILED) for an applied change, and enforce that commit only happens after an allowed terminal state is reached. Use after a change has been applied and compiled, before it is committed.
---

# Test the Change — Truthfully

**Prescribed duty (single):** determine and record one of the three real
testing terminal states for the applied change, and gate commit on it.
This Skill exists specifically because "no testing happened" was once
silently treated as "tests passed" in this project's real production
pipeline (see docs/LESSONS.md, run `trainer-7769757e`'s Testing-state
defect) — never repeat that class of mistake.

## Canonical sources (reference, do not restate)

- The real deterministic fact-check for applicability:
  `agent/web_server.py::_tests_applicable` (checks whether
  `app/src/test/java` has ANY real test file — never a guess).
- The real test tool: `run_controlled_tests` in
  `agent/execution_tools.py`/`agent/build_tools.py`.
- The real commit gate logic (already implemented, do not reimplement):
  `agent/web_server.py`'s trainer thread — commit is blocked unless
  `apply_ok and compile_ok and test_ok`, where `test_ok` is only True
  for a genuine PASS or a genuine, fact-checked NOT-APPLICABLE.
- The frontend rendering of this exact state:
  `agent/web/workbench.js::testingChecklistState` — the UI-side lesson
  that a mismatched stage-string key can make a real terminal decision
  look ambiguously pending; this Skill's OUTPUT must use one of the
  exact stage strings that function recognizes: `"TESTING"` (pass path)
  or `"TESTING — NOT APPLICABLE"` (with a `reason`).

## Inputs

- The applied change's file path(s) and diff.
- Whether `run_controlled_tests` was actually invoked and its result, if so.

## Outputs — exactly one of

1. **`TESTING — PASSED`**: `run_controlled_tests` was actually invoked and
   every result was successful.
2. **`TESTING — NOT APPLICABLE`** with a real, fact-checked `reason`
   (e.g., "app/src/test/java has zero test files" — verified via
   `_tests_applicable()`, never assumed from "the change looked simple").
3. **`TESTING — FAILED`**: any invoked test failed. Commit must not proceed.

## Evidence required

- If claiming NOT APPLICABLE: the actual boolean result of
  `_tests_applicable()` at the time of the decision, not a guess.
- If claiming PASSED: the real tool_result payload from
  `run_controlled_tests`.

## Must NOT

- Must NOT default to "passed" or "not applicable" when neither has been
  actually checked — that ambiguity is exactly what escaped before.
- Must NOT allow commit to proceed on anything other than PASSED or a
  fact-checked NOT APPLICABLE.
- Must NOT invent a fourth testing state not recognized by
  `agent/web/workbench.js::testingChecklistState` — the UI has no way to
  render an unrecognized state truthfully.
- Must NOT weaken this gate to make a run "complete" faster — see
  docs/CONSTITUTION.md §3 (never bend truth/evidence to force a result).
