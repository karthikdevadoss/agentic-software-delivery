
---

# RETRO — Deep Consensus Sprint 6 (2026-10-02)

Written before any next-sprint sizing, per the approved A1. Sprint 7 has not
been started.

## Section 0 — the comparison table (the Owner's required format)

| Item | Size given | Actual | Verdict | Evidence |
|---|---|---|---|---|
| BL-DC6 — close actions, safety audits, pre-registered evidence, one decisive run | **XLARGE, 300–360 min, midpoint 330, confidence LOW, CONCURRENT, 6 agents, 40 min reconciliation** | **97 min** wall-clock (first Sprint-6 commit → run complete + Phase 4) | **ESTIMATION WRONG — over-estimate**, ratio **0.295** | band [0.7, 1.3] from `docs/BACKLOG.json` `_calibration_process.tolerance`; computed, not judged |

**Parallel work, both figures, as the calibration process requires.**
Wall-clock 97 min is what the Owner waited. Summed agent effort was far
higher — six concurrent write-capable agents reporting roughly 1.14 million
subagent tokens — and the two answer different questions. Neither substitutes
for the other.

**Calibration history: oscillation, not convergence, for a fourth sprint.**
Sprint 8 ratio 0.30, Sprint 9 ratios 1.9 and 3.3, Sprint 5 ratio 0.224, now
0.295. The `residual_bias_factor` fix was already tested and rejected in
Sprint 9 and is not re-proposed.

**A7 and A8 were applied for the first time and did not fix the estimate.**
Stating which execution model was priced (CONCURRENT) and pricing
reconciliation at 40 minutes were both correct and both insufficient: the
estimate was still 3.4x the actual. The missing term is not parallelism — it
is that the dominant cost I feared (a 20-case live run) took ~50 minutes
while the work I under-priced (two audits that found eleven defects) was
absorbed by agents running concurrently with each other AND with my own work.

## WHAT WAS EXPECTED

That the audits would confirm the Sprint-5 fixes were complete and find
little else. That the mutation gate would pass first time. That the hard part
would be building 20 primary-source cases. That the decisive run would
finally answer whether governed review reduces published falsehood.

## WHAT HAPPENED

Three of those four were wrong, and the fourth produced a non-answer for the
third consecutive evidence sprint.

**The audits found eleven real defects, none of them the ones they were
chartered to verify.** Nine scorer, two identity. Two would publish a FALSE
AGREEMENT. One reproduced the Sprint-5 headline defect through a path the
Sprint-5 fix never touched.

**The mutation gate blocked twice**, both times usefully — once on a real
coverage question, once on a badly designed mutant of my own.

**The entitlement check failed in a way the frozen rule did not
anticipate.** Requesting `claude-opus-5` returned an answer from
`claude-haiku-4-5-20251001`.

**The decisive run completed and its mechanical verdict rests on an
artefact.** 20/20 cases, 99 turns, zero provider limits, zero billing
violations, zero introduced falsehoods. The challenge set produced ZERO
baseline falsehoods in 12 cases. The only two recorded baseline falsehoods
are a spelling artefact in one blind case.

## DEFECTS FOUND

| # | Where | Severity |
|---|---|---|
| 1 | `published_as_settled` stripped 3 of 4 annotated blocks; `NOT CROSS-CHECKED` counted as published fact | reproduced the Sprint-5 headline defect |
| 2 | Short accepted values matched inside words — "no" in *now/normal/not*, "io" in *production*, "17" in *2017* | an answer advocating the forbidden practice scored CORRECT_COMPLETE |
| 3 | `expected_values` credited an answer asserting the opposite ("blocked" inside "not blocked") | published falsehood recorded as correct |
| 4 | Cross-clause negation leak in `_marker_published` | a genuine catch booked as a completeness gain |
| 5 | Unanchored heading `find()` deleted the rest of an answer | manufactured COMPLETE_TO_INCOMPLETE |
| 6 | `disputed_text` omitted two warning buckets | specific exposure downgraded |
| 7 | Polarity applied to the wrong question in exposure detection | exposure missed |
| 8 | Marker matched a longer word ("it is safe" in "it is safer") | correct security answer charged with a falsehood |
| 9 | Subject-collision Stage-4 routing | **published false agreement** |
| 10 | `_closest_subject` picked a winner among equally plausible subjects | **published false agreement** |
| 11 | Entitlement accepted an answer from a different, weaker model as proof | would have made the whole measurement flattering |
| 12 | My own suspect-detector flagged `ACCESS EXCLUSIVE` vs `EXCLUSIVE` and `SHARE UPDATE EXCLUSIVE` vs `UPDATE EXCLUSIVE` as spelling differences | would have excused a real falsehood |
| 13 | My own suspect-detector linked catches by their own comparison verdict (AGREE by construction) so flagged zero catches | the figure the decision rule reads went unflagged |

## THE CENTRAL FINDING

**Every headline this project has produced has been decided by a defect in
its own measurement rather than by the product.**

- Sprint 5's headline was a manufactured REGRESSION: a substring read "not
  suited to CPU-bound work" as publishing "suited to cpu-bound".
- Sprint 6's headline is a manufactured CATCH: the baseline answered
  `PROPAGATION_REQUIRED` where the frozen golden claim pinned `REQUIRED`.
  Same answer, different documented spelling.

The two errors point in opposite directions, which rules out a simple bias
and indicts the method instead. It is a stronger argument for the
pre-registration discipline than anything the product itself has shown — and
it is the reason the Sprint-6 report publishes both verdicts rather than
choosing.

## EVIDENCE QUALITY

Best of any sprint so far, and still unable to answer the question.

Strong: 20 cases, every ground truth a verbatim primary-source quote actually
fetched; 65 material claims, 61 deterministically typed and 4 honest
NEEDS_OWNER; both sets hashed separately and together before the first
evaluated answer; a freeze that refuses re-registration; the decision rule
hashed as frozen text; every integrity and billing check PASS; Sprint-6
self-replay reproduces the verdict offline with 0 differences and 0 model
calls.

Limits, each recorded by the agent that produced it rather than by me
afterwards:
- Challenge difficulty is **asserted by category, never measured**. The
  baseline answered all twelve correctly. The set's author wrote in advance
  that this would be a real result and not a reason to hunt harder questions.
- The Sprint-5 replay's 0 differences **proved nothing about the identity
  fix**: 0 colliding routing keys in 50 pairings, so the fix could not apply.
  The report says so in a computed coverage block.
- Question wording is model-authored even though ground truth is not.
- 29 NEEDS_OWNER items remain unadjudicated.

## MODEL-TURN WASTE

- **1 wasted entitlement turn, mine.** I re-ran the Opus probe with a
  corrected criterion when the stored record was already sufficient to
  re-judge offline.
- Zero wasted evaluated turns: no case rerun, no prompt tuned after a result,
  no paid fallback, no fifth call.
- **10 unresolved-noise cases out of 20** — Deep Consensus spent turns
  disputing propositions that were not baseline falsehoods. At 3.85 DC turns
  per case against a baseline of 1, that is the real cost figure.
- Every audit, gate, replay, scorer rebuild and report cost zero turns.

## PARALLELISM EFFECT

Six write-capable agents, strictly partitioned files, zero collisions, zero
lost work, ~5,900 lines across 13 new files.

The effect that mattered was not speed. **Agents that had never seen my
implementation found defects in it, repeatedly** — the scorer audit found
five negation paths the landed fix had missed, and a Sprint-5 contract test's
stated objection described a false-agreement route I had already written. A
second instance of the same model is not an independent mind, but it is an
independent evidence path, and at this defect-find rate it is worth its token
cost.

Three contract mismatches at module boundaries I had specified in prose, all
caught by tests rather than by reading. The one that cost nothing was the one
where the agent made its contract REFUSE bad input rather than tolerate it.

## A PATTERN THAT APPEARED FIVE TIMES IN TWO SPRINTS

A guard or test that searches text for the name of a thing it forbids will
fire on the text that forbids it.

1. `test_20` flagged `import itertools` as importing the module `tools`.
2. The Sprint-5 scorer read "not suited to CPU-bound work" as a claim.
3. `test_17` flagged the frozen case recording `false` for "is the
   convergence score a correctness probability".
4. My own test asserted "pooled" absent from a summary dict and fired on the
   sentence forbidding pooling.
5. My own test asserted "inconclusive" absent from a verdict and fired on
   "so this is PAUSE -- not inconclusive".

**The fix in every case is to assert over STRUCTURE — keys, verdict values,
parsed imports, typed comparisons — never over prose.**

## WHAT SHOULD CHANGE

New action items, all UNAPPROVED because the Owner is absent.

| # | Action | Addresses |
|---|---|---|
| A15 | Golden claims must record EVERY documented spelling of an enum value, or declare the spelling normative in the question | the manufactured catch, defect 12 |
| A16 | Before any evidence sprint, run the scorer against the frozen golden claims and a deliberately-correct synthetic answer; any claim that fails to score CORRECT is a case-data defect, found at zero turns | would have caught the artefact pre-freeze |
| A17 | Treat every assertion over prose in a guard or test as a defect by default; assert over structure | the five-instance pattern |
| A18 | A measurement tool gets the same mutation coverage as the engine it measures | the scorer carried nine defects while the engine carried two |
| A19 | Mechanise A1 — a sizing gate that refuses while a prior retro is unwritten | A1 could not be closed because it is applied by hand |
| A20 | Exercise A10 deliberately, or descope it — approved and never applied | A10 could not be closed |
| A21 | Record both wall-clock and summed-agent-effort in every concurrent estimate, and stop treating the live-run duration as the dominant term | the estimate was 3.4x despite A7/A8 |
| A22 | Investigate the 7 Grok multi-object `cancelled` responses; they correlate with PARTIAL statuses and unparsed cross-checks | provider-side, bytes intact, currently unexplained |
| A23 | Adjudicate the 29 NEEDS_OWNER items, starting with the 2 flagged rows that decide this sprint's verdict | the verdict depends on it |
