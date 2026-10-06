# Test oracle classification (BL-116, Sprint 27, SI audit BK-18)

Every test proves *something*, but not every test proves the same *kind*
of thing. A suite can be 100% green and still have zero tests that ask
whether an output is actually good — that was this project's own
Standing Interview finding (`docs/audits/SI_AUDIT_2026-09-29.md` Part 4c,
the worked example this classification generalises from a hand-read 134
cases to the whole Python suite).

## The five categories

| Category | What it proves |
|---|---|
| `PLUMBING` | The mechanism is wired and data flows -- a call happened, a field is present, a status/threshold was met. Says nothing about whether the content is *right*. |
| `SAFETY_INVARIANT` | Something forbidden never reaches the user -- a leak, an unauthorized action, a security-sensitive case that must never pass. |
| `CORRECTNESS_LABELLED` | A case with a known right answer -- actual output compared against a specific, non-trivial expected value. |
| `QUALITY_USEFULNESS` | Is this a *good* answer, not merely a not-forbidden one? Requires a labelled rubric or a model/human judge; no automatic heuristic can honestly claim this. |
| `HUMAN_REVIEWED` | A human (the Owner) actually judged the output, and that judgment is what the test checks against. |

A sixth label, `UNCLASSIFIED`, is used whenever the heuristic below cannot
place a test with reasonable confidence. An honest `UNCLASSIFIED` is
worth more than a confident wrong guess — see CLAUDE.md's five evidence
rules.

## Methodology, and its honesty limit

`agent/classify_test_oracles.py` parses every `agent/test_*.py` file's
real AST and looks at which `self.assert*()` method each test function
calls and on what shape of argument — never the test's own name string.
Roughly:

- An exclusionary assertion (`assertNotIn`, `assertRaises`, `assertFalse`,
  `assertIsNone`) → `SAFETY_INVARIANT` (checked first; safety takes
  priority when a test mixes assertion types, matching the SI audit's own
  precedence).
- `assertEqual`/`assertDictEqual`/etc. against a specific **non-trivial**
  expected value (not bare `True`/`False`/`None`/`0`/empty) →
  `CORRECTNESS_LABELLED`.
- `assertTrue`/`assertIn`/`assertIsNotNone`/a threshold comparison →
  `PLUMBING`.
- A reference to a stored human/Owner review decision (`si_review`,
  `owner_review`, `dissatisfied_row`) → `HUMAN_REVIEWED`.
- Nothing matched → `UNCLASSIFIED`.

**This is a heuristic, not semantic understanding.** It is a real signal
genuinely stronger than name-pattern matching (it reads what the test
actually asserts), but it cannot tell, for example, that an `assertEqual`
against a hardcoded `200` is plumbing-flavoured rather than a "known
right answer" in the SI audit's richer sense, if that `200` isn't caught
by the triviality filter. Treat the manifest as a first-pass signal to
sample and spot-check, not a human-verified ground truth the way the SI
audit's 134 hand-read cases are.

## What is done

All 73 `agent/test_*.py` files, ~1,237 test functions, machine-classified
and written to `agent/test_oracle_manifest.json` (regenerate with
`python agent/classify_test_oracles.py`; `--summary` prints counts only).
As of this writing: `CORRECTNESS_LABELLED` ~463, `SAFETY_INVARIANT` ~389,
`PLUMBING` ~285, `UNCLASSIFIED` ~99, `HUMAN_REVIEWED` 1,
`QUALITY_USEFULNESS` 0 — the same shape of gap the SI audit found for
Standing Interview specifically: plenty of safety and plumbing coverage,
almost none asking "is this good," which matches this project's own
repeated finding that answer quality has no automatic oracle yet.

## What is not done yet

- **Java tests** (`app/src/test/**`, `services/*/src/test/**`) are not
  classified. The same AST-based approach does not apply (different
  language, different assertion library/framework per module); a Java
  classifier would need its own script, not an extension of this one.
- **Playwright specs** (`e2e/*.spec.js`) are not classified. JS AST
  parsing would need a JS-side tool (e.g. a small `acorn`/`esprima` pass),
  which this session did not build.
- **No human spot-check of the heuristic's output has been done yet**
  beyond a small random sample reviewed during this task. A real
  confidence number for the heuristic (what fraction of its labels would
  survive a human re-read, the way the SI audit did for its 134 cases)
  does not exist and should not be assumed.

## Maintaining the table

Re-run `python agent/classify_test_oracles.py` whenever `agent/test_*.py`
changes meaningfully; it is deterministic and fast (a few seconds), and it
regenerates the full manifest rather than diffing — there is no drift to
reconcile by hand.
