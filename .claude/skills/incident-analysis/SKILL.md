---
name: incident-analysis
description: Root-cause an unexpected failure or surprising result using real evidence (event ledger, run history, logs) — never guess. Use when a run failed unexpectedly, a claim looks wrong, or a result needs explaining before deciding a fix.
---

# Root-Cause From Evidence

**Prescribed duty (single):** given an unexpected failure or surprising
result, find the real, verified root cause from actual evidence — and
stop there. This Skill produces a diagnosis, not a fix; `implement-small-change`
handles the correction once the real cause is known.

## Canonical sources (reference, do not restate)

- Real incident narratives with full root-cause writeups:
  `knowledge/sessions/*.md` (e.g.
  `knowledge/sessions/2026-09-10-trainer-idempotency-fix.md`).
- Durable, reusable technical lessons: `docs/LESSONS.md` — check here
  FIRST; the exact failure may already be a known, documented class of
  bug (see `production-verify`'s list of 11 real escaped defects) rather
  than something new.
- The canonical event trail for any real run: the event ledger
  (`agent/event_ledger.py`, table `delivery_events`) queried by `run_id`
  — never trust a UI screenshot or a paraphrase over the actual recorded
  events.
- CLAUDE.md's "Feedback discipline" section: expected vs. actual,
  classify the gap (implementation bug / test gap / requirement ambiguity
  / architecture / security / model-or-tool-API behavior / context-memory
  problem / observability gap), smallest safe correction, verify, persist
  only what's reusable.

## Inputs

- The run_id (or enough context to find it) and the observed unexpected
  behavior.

## Outputs

- Root cause, stated as a specific, falsifiable claim backed by exact
  evidence (event types/timestamps/payload fields), not a plausible
  story.
- Classification of the gap (per CLAUDE.md's feedback-discipline
  categories above).
- Whether this is a NEW class of defect (needs a new docs/LESSONS.md
  entry + regression test) or an ALREADY-KNOWN class (point to the
  existing lesson/test instead of duplicating it).

## Must NOT

- Must NOT guess a plausible-sounding cause without pulling the actual
  event trail first — see docs/CONSTITUTION.md §5 (fact vs. assumption)
  and this project's own explicit rule ("Do NOT guess" / "Do NOT assume
  why" appears verbatim in multiple real incident tasks).
- Must NOT fix anything itself — hand the diagnosis to
  `implement-small-change` (or a human, for higher-risk cases) rather
  than blending diagnosis and correction into one uncontrolled step.
- Must NOT overwrite or reinterpret a preserved failed run's evidence —
  docs/CONSTITUTION.md §17: never overwrite failures with later successes.
- Must NOT declare "root cause found" from correlation alone when a
  direct causal mechanism hasn't been confirmed (e.g., reproduce the
  exact byte/state/timing where practical, as prior incidents in this
  project did).
