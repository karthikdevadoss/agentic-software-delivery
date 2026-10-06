# Fail-first evidence registry (BL-119, Sprint 27, SI audit BK-13)

This project's own rule (CLAUDE.md, "AI-characteristic defect discipline"):
*"A new test is not trusted until it has been observed failing."* That rule
has always been real, but its evidence lived only in prose and commit
messages — there was no durable, queryable record of which tests actually
had this done to them. This is the mechanical version.

## How it works

- `agent/fail_first_evidence.json` — a manually-maintained registry. An
  entry is added **at the moment a real fail-first observation happens**
  (reverting the fix, running the test, seeing it fail for the right
  reason, restoring the fix) — never backfilled from a guess about what
  probably happened historically. Same discipline as
  `docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml`.
- `agent/check_fail_first_evidence.py` — cross-references the registry
  against `agent/test_oracle_manifest.json` (BL-116's full real test
  enumeration) and reports, per test, `HAS_RECORD` or `NO_RECORD`. Run
  `python agent/check_fail_first_evidence.py` for the summary count,
  `--list-missing` for the first 20 unrecorded test ids.

## Honest current state

As of this writing: **3 of ~1,240** real tests have a recorded fail-first
observation (0.24%). This is not a defect in the tool — it's the honest
starting point. The other 99.76% were written without this record existing
at all; `NO_RECORD` does not mean "this test is wrong," it means "no
mechanical proof exists that it was ever seen to fail for the right
reason." Treat the percentage as a baseline to grow from sprint to sprint,
not a score to close in one pass.

## Why this is a report, not a CI gate

This is deliberately **not** wired to fail CI. A gate that failed the
build on `NO_RECORD` would turn red on ~1,237 pre-existing tests overnight
for a condition that predates the tool itself — exactly the kind of
"coverage theater" this project's own evidence rules warn against (a
gate that fires on everything stops meaning anything). It is a report:
run it, read the coverage trend over time, and add real entries as real
fail-first observations happen going forward.

## Known limitation, stated honestly

There is no way to mechanically recover whether an existing test was
observed failing back when it was written — that evidence is either
already written down somewhere (rare) or genuinely lost. This registry
starts from zero real history and grows only from here. A future session
could mine commit messages for phrases like "observed failing" and
backfill candidate entries for human confirmation, but that was not
attempted here (confidence: this would produce plausible-looking but
unverified entries, which is worse than an honest gap — see CLAUDE.md's
five evidence rules, rule 3: related evidence is not proof).
