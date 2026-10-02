
---

# RETRO — Deep Consensus Sprint 5 (2026-10-02)

**Written before the next sprint's sizing, which is the first time that has
happened for a Deep Consensus sprint.** Sprints 3 and 4 were executed with no
estimate and no retro; that was the headline finding of the overdue
Sprints 3+4 retro written earlier today. Sprint 5 was sized first (BL-DC5)
and is retro'd before anything else starts.

## Section 0 — the comparison table (the Owner's required format)

| Item | Size given | Actual | Verdict | Evidence |
|---|---|---|---|---|
| BL-DC5 — typed claims, one-sided cross-check, 8-case rerun | **XLARGE, 360–540 min, midpoint 450, confidence MEDIUM** | **101 min** wall-clock (first Sprint 5 commit → live run complete) | **ESTIMATION WRONG — over-estimate**, ratio **0.224** | band [0.7, 1.3] from `docs/BACKLOG.json` `_calibration_process.tolerance`; computed, not judged |
| Same, including the pre-commit parallel-agent build phase | same | **~140 min** (floor; not precisely measurable from git) | **ESTIMATION WRONG — over-estimate**, ratio **0.311** | agents reported 761 s, 765 s, 1231 s; the fourth predates the measurable window |

**Both figures answer different questions and both are reported, as the
calibration process requires for parallel work.** Wall-clock is what the
Owner waited. The summed individual durations are higher than wall-clock
because four write-capable agents ran concurrently; a summed figure would
describe effort, not elapsed time, and neither is a substitute for the other.

**The 101-minute figure is a floor, stated as one.** Work began before the
first Sprint 5 commit — `typed_values.py` and its 29-test suite were already
built by parallel agents — and git cannot date that. I have not invented a
precise start time to make the table look complete.

**Calibration history, for context rather than comfort:** Sprint 8 ratio
0.30 (under-estimate of effort / over-estimate of time), Sprint 9 ratios 1.9
and 3.3 (the project's first over-runs), now 0.22–0.31 again. That is
**oscillation, not convergence**, and it is the third sprint in a row where
the band did not hold. The `residual_bias_factor` fix was already tested and
rejected in Sprint 9; this retro does not re-propose it.

## The Owner's four improvement axes

**1. Value of work done.** Real but narrow. The engine improved on every
axis measurable from inside it: 18 of 18 eligible one-sided claims examined
where Sprint 4 examined 0 of 29, UNCOMPARED now blocks CONVERGED, 4 of 8
statuses became correctly confident, zero regressions. The product question
— does this reduce published falsehood — is still unanswered, for the second
sprint running.

**2. Wastage reduced vs the previous state.** **No, slightly worse, and
named rather than averaged away.** Deep Consensus turns went 30 → 31 (3.750
→ 3.875 per case) and the single 2-call early stop disappeared. The typed
comparator removed Sprint 4's false disagreements and replaced them with
honestly-undecidable TEXT pairs plus new cross-check turns. `S4-DB-1` went
from 2 calls to 3 — a better run that costs more. That is a defensible
trade, but the waste figure moved the wrong way and claiming otherwise would
be spin.

**3. Closer to the goal / milestone.** On mechanism, yes. On evidence, no —
and this sprint established WHY, which is progress of a kind: the eight
available cases cannot answer the question because the frozen baseline is
already correct on all eight. Two sprints have now produced that same
non-answer. The bottleneck is case selection, not the engine.

**4. Clarity of purpose and vision.** Improved. The sprint produced a
sharper statement of what the product must prove and a specific, hard,
named obstacle to proving it (choosing cases where a strong model fails,
without choosing them by watching it fail).

## Section 1 — learnings from wrong ESTIMATION

**1.1 The estimate priced sequential execution and the work ran in
parallel.** Four write-capable agents produced roughly 2,900 lines
concurrently. Nothing in the XLARGE rationale accounted for that, so a
correctly-reasoned sequential estimate was ~3–4× the parallel actual. The
rubric has no parallelism input at all; until it does, any sprint executed
with concurrent agents will over-estimate by construction.

**1.2 Parallelism has an integration cost the estimate also missed, in the
opposite direction.** Two separate **contract divergences** followed from
running agents concurrently against a written spec — a bare `parse("yes")`
typed BOOLEAN by the engine and TEXT by the test, and the TEXT-pair routing
question — each needing a decision, a message to a running agent, and a test
edit. Parallelism is not purely a throughput multiplier; it generates
reconciliation work that scales with the number of agents.

**1.3 The estimate did not price defects in the sprint's OWN new code.** The
risk drivers named integration with the existing engine, the live rerun and
the gates. Four defects were found during integration and three were in code
written this sprint. Time spent debugging freshly-written code is a
different category from integration time, and only the second was estimated.

## Section 2 — learnings from IMPLEMENTATION issues

**2.1 A test's stated REASONING caught a defect its assertion alone would
not have.** `test_identical_text_on_both_sides_is_still_text_undecided`
argued that an identity fast path "would reintroduce exactly one
false-agreement route: normalisation collapsing two values that were never
the same." I had already written that exact route — `normalize_text` turns
punctuation into spaces, so `"x > y"` and `"x < y"` agreed. The test was
written by an agent that had never seen my implementation. **Reading a
disagreeing test's argument, not just resolving its assertion, is the
technique.** It paid out twice this sprint.

**2.2 Two of three defects in new code were in COST-motivated changes to a
correctness component.** The identity exception existed to stop a 4-call
blow-up; the VERSION-precedence override existed to stop losing a true
pairing. Both were cost fixes and both opened a correctness hole. A change
made to save turns deserves at least the scrutiny of one made to fix
correctness, because the motivation feels harmless and the review reflex is
weaker.

**2.3 The measurement tool had the same defect class as the thing it
measures, and it produced a false headline.** The scorer's wrong-answer
marker test was a plain substring match and read "they are **not** suited to
CPU-bound work" as publishing "suited to cpu-bound". On that single false
positive the run's first product verdict was that Deep Consensus had
introduced a material false claim. It had not. **Fixing negation blindness in
the comparator did not fix it in the scorer** — and a measurement is only as
trustworthy as its own worst bug. The project rule this vindicates already
existed: a diagnostic must be proven to detect the known-bad case before its
clean verdict is trusted.

**2.4 Model-supplied text was used as an identity key.** `pair_claims`
tracked consumed claims by `claim_id`, which a model writes. Two claims
sharing an id meant one vanished from the comparison entirely — not
UNCOMPARED, absent. Untrusted input must never be an identity key; the
identity is now the list position, which no model can influence.

**2.5 A structural guard that fires on an unrelated stdlib import is a guard
that gets switched off.** The coding-agent isolation test substring-matched
module names, so `import itertools` was reported as importing `tools`. It had
been correct only because nothing in the package had previously imported
itertools.

**2.6 A mutation gate found a hole 275 tests did not, and the hole was
exactly one assertion wide.** Nothing asserted that a material pairing with
no agreed state blocks CONVERGED. Two safety-critical mutants walked through
it. Coverage did not predict this; an adversarial mutation did.

## Section 3 — neither, but still needed

**3.1 The zero-turn dry run of the POST-TURN path paid for itself
immediately.** `outcomes.aggregate` expects rows keyed
`baseline_score`/`deep_score`/`outcome`/`noise`; the runner passed different
names. That `KeyError` would have fired after all eight cases were paid for
and destroyed the entire 40-turn budget. The brief's rule — never use live
subscriptions to debug — is exactly what this protects.

**3.2 Refusing to truncate evidence paid out for the first time.** Because
`baseline_result_full` and the whole `deep_consensus_result_object` were
stored untruncated, the scorer defect in 2.3 was corrected and all eight
cases re-scored at **zero model turns**. Had the evidence been truncated as
Sprint 4's was, re-measuring would have cost a second 40-turn budget. This
retires any remaining argument for trimming stored evidence.

**3.3 Verifying my own tool's NEGATIVE claim prevented a wrong escalation.**
The Grok preflight reported NOT_LOGGED_IN and told the Owner to run
`grok login`. Grok was logged in; the detector produced a transient false
negative. I was one step from asking the Owner to fix a problem that did not
exist. The "verify, don't dismiss" discipline applies to my own tools'
negatives, not only to the Owner's reports.

**3.4 `requested_model` and `reported_model` genuinely diverge in
production.** Requested `grok-4.6`, reported `grok-4.6-build`, on all 15
slot-B turns. Sprint 3's requirement to record both separately is
load-bearing, not ceremonial.

**3.5 `stage=one_sided_check` had no producer when the replay harness was
written and now has one.** The agent that built it flagged the stage as
possibly a spec drafting assumption and asked for confirmation. It was not:
`S4-DB-1`'s third turn was a cross-check-only turn.

**3.6 The product question is now bottlenecked on case selection, not on
the engine.** Eight cases where a strong single model is already correct
cannot demonstrate error catching. This is the single most important open
item and it needs design work before more turns are spent.

## ACTION ITEMS — awaiting explicit Owner approval

A1–A6 from the Sprints 3+4 retro remain **open and unapproved**. These are
additional, also unapproved and not started.

| # | Action | Addresses |
|---|---|---|
| A7 | Add a parallelism input to the sizing rubric: an estimate must state whether it prices sequential or concurrent execution | 1.1 |
| A8 | Price agent-contract reconciliation explicitly when a sprint plans N concurrent write-capable agents | 1.2 |
| A9 | When an agent-written test disagrees with my implementation, read and answer its stated ARGUMENT before resolving either way | 2.1 |
| A10 | Treat a cost-motivated change to a correctness component as a correctness change for review purposes | 2.2 |
| A11 | Audit the scorers and diagnostics for the defect classes already fixed in the engine — starting with negation and substring matching | 2.3 |
| A12 | Audit the engine for other places model-supplied values are used as identity keys | 2.4 |
| A13 | Design the "baseline actually fails" evidence set, including how cases are chosen without watching the model fail | 3.6 |
| A14 | Size the "does a stronger single Claude model beat the pair" question as its own item with its own turn budget | Sprint 4 limitation 3 |

A7 and A8 are the two that would have changed this sprint's estimate. A13 is
the one that would change the next sprint's value.
