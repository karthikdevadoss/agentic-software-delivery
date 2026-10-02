# Sprint 1 — factual failure findings

Compiled 2026-10-01 at the start of Sprint 2, **from audit evidence only**.
Where the evidence does not establish a detail it says `UNKNOWN`. Nothing
here is inferred.

Source of all claims below: `deep_consensus/audit_log.jsonl`, 14 records,
of which 2 have `provider_mode == "real_real"`.

---

## 1. The CREATE INDEX locking error

### Ground truth (fixture for the Sprint 2 regression)

> Plain `CREATE INDEX` permits **concurrent reads** but **blocks writes**
> against the target table while index creation proceeds.

**Verified against authoritative documentation**, not recalled —
<https://www.postgresql.org/docs/current/sql-createindex.html>, accessed
2026-10-01, which states in its own words:

> "Normally PostgreSQL locks the table to be indexed against writes and
> performs the entire index build with a single scan of the table. Other
> transactions can still read the table, but if they try to insert, update,
> or delete rows in the table they will block until the index build is
> finished."

and, contrasting with `CONCURRENTLY`:

> "a standard index build locks out writes (but not reads) on the table until
> it's done."

**The lock mode is SHARE** — restored 2026-10-01 (Sprint 3 Phase 0) after
checking the right page. PostgreSQL's explicit-locking documentation,
<https://www.postgresql.org/docs/current/explicit-locking.html>, accessed
2026-10-01, lists under the SHARE lock mode:

> "Acquired by `CREATE INDEX` (without `CONCURRENTLY`)."

and describes that mode as one that "protects a table against concurrent
data changes" — consistent with the behavioural statement above.

**A correction to my own correction, recorded because the mistake is
instructive.** Sprint 2 *removed* the name "SHARE" from this document on the
grounds that it was unsupported. That was wrong, and wrong in a specific
way: I had checked the `CREATE INDEX` reference page, which genuinely does
not name a lock mode, and concluded the name was unsupported. The correct
conclusion was narrower — *unsupported by the page I had read*. The lock
mode is documented, on the explicit-locking page, which I had not consulted.

"I could not find it" and "it is not established" are different claims, and
collapsing the first into the second deleted a true fact. Being
over-cautious looked like rigour and was actually just a different way of
getting it wrong.

### What Sprint 1 actually published

**Run `dcr_361112bc329048a8`**, timestamp `2026-10-01T15:53:39.034977+00:00`,
`status: PARTIAL`, `convergence_score: 0.0`.

Its `governed_answer` contains, verbatim:

> "…a plain CREATE INDEX takes an **ACCESS EXCLUSIVE** lock that **blocks
> all reads and writes** for the duration of the build…"

That is **wrong on both counts** against the primary sources above: the lock
mode is `SHARE`, not `ACCESS EXCLUSIVE`, and reads are **not** blocked by a
plain `CREATE INDEX`.

### Which run, and before or after the truncation fix

| Question | Answer | Evidence |
|---|---|---|
| Which run produced it? | `dcr_361112bc329048a8` (the **first** real run) | only that record matches `/ACCESS EXCLUSIVE/i` in `governed_answer` |
| Before or after the truncation fix? | **BEFORE** | two independent markers in the record: (a) it has **no** `review_rounds` key, which was added by the same post-live fix commit; (b) its final round contains slot A with `parse_status: provider_format_error` — the truncation incident itself |
| Did it survive the fix? | **No** | run `dcr_570b0babbe6744d1` (after the fix, `2026-10-01T15:58:33.926724+00:00`) does **not** contain `ACCESS EXCLUSIVE` or `blocks all reads` |

### What the reviewer actually marked CONTRADICTED

**Not the locking claim.** In run `dcr_361112bc329048a8`, round 1, the only
CONTRADICTED claim was raised by slot B (`claude-haiku-4-5-20251001`) about
slot A:

> "Invalid indexes left behind after CONCURRENTLY failure is the single
> biggest risk overlooked"

For completeness, the other real run's only CONTRADICTED claim was raised by
slot A (`claude-sonnet-5`) about slot B:

> "An invalid index can cause queries to fail if the planner tries to use it"

### The finding that matters

**No reviewer ever challenged the ACCESS EXCLUSIVE claim.** It was not
marked CONTRADICTED, not marked UNCERTAIN, and did not trigger a REVISE. A
materially false factual claim passed through a full sealed-answer
cross-review between two models **completely unchallenged**, and was
published in the governed answer.

This is the same-family correlated-blind-spot risk that Sprint 1 recorded as
*Known limitation 1* — now demonstrated with evidence rather than asserted.
Both reviewers were Anthropic models.

**Honest scope of the Sprint 2 fix.** Sprint 2's contradicted-claim override
prevents a claim that **was** marked CONTRADICTED from silently surviving
into a CONVERGED answer. It would **not** have caught this failure, because
nothing marked this claim at all. Undetected falsehood and detected-then-
ignored contradiction are different defects. Sprint 2 fixes the second. The
first is only addressable by genuine cross-family review (and ultimately
external verification), which is why the second provider family is the
sprint's first priority.

---

## 2. Why Gemini was not used in Sprint 1

**Both** — key absent **and** SDK absent. Verified 2026-10-01:

- Environment (after loading `agent/.env`): `GEMINI_API_KEY` **ABSENT**,
  `GOOGLE_API_KEY` **ABSENT**, `GOOGLE_GENAI_API_KEY` **ABSENT**.
- SDK: `google.genai` **not installed**, `google.generativeai` **not
  installed**. `pip list` shows no `google-genai` / `google-generativeai`.

Only `ANTHROPIC_API_KEY` was present, and only `anthropic` (1.4.0) was
installed. `OPENAI_API_KEY` was also absent and `openai` also not installed.
Sprint 1's rule was to use the first real provider whose SDK and credential
already existed, which left Anthropic as the only option — hence two
Anthropic models rather than two families.

**This is unchanged at the start of Sprint 2**, so Sprint 2 reports
`BLOCKED_REAL_PROVIDER_CREDENTIAL` for slot B.

---

## 3. Preserved Sprint 1 evidence

| Artefact | Status | Path |
|---|---|---|
| Sprint 1 APPROVED_PROMPT | **ABSENT** — the Sprint 1 prompt was never written to a file during Sprint 1; it existed only in the session. Not recreated, per instruction not to recreate history. | — |
| Sprint 1 final report | **ABSENT** as a file — it was printed to the session only. The same facts are recoverable from `docs/DEEP_CONSENSUS_SPRINT1.md` and the commits, which are not the report itself. | — |
| Real-run audit excerpts | PRESENT | `real-run-audit-excerpts.json` (this directory) |
| Full audit log | PRESENT (git-ignored working file) | `deep_consensus/audit_log.jsonl` |
| MCP Inspector output | PRESENT (4 files) | `inspector-01..04*.json` |
| Inspector CLI crash evidence | PRESENT | `inspector-03-invalid-call.json`, `inspector-04-internal-stage-refused.json` — both end with the libuv `Assertion failed: !(handle->flags & UV_HANDLE_CLOSING)` teardown line after correct output |
| Raw HTTP probe output | PRESENT | `raw-http-probe.json`, `raw-http-probe-mock.json` |
| Real provider smoke runs | PRESENT (before and after the truncation fix) | `real-provider-smoke.txt`, `real-provider-smoke-after-fix.txt` |
| Lock/error evidence from Sprint 1 | **ABSENT** — no lock contention or runtime error occurred in Sprint 1 beyond the truncation misclassification and the Inspector teardown crash, both already evidenced above | — |
