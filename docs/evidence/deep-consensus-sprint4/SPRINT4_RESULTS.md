# Deep Consensus — Sprint 4: the evidence sprint

Branch `deep-consensus-sprint4-evaluation`. Not pushed, not deployed.

The question: **does Deep Consensus catch important errors a strong single
model misses, at an acceptable number of model turns?**

The answer, on this evidence: **MIXED**, and the honest reading is less
flattering than the headline rates suggest.

---

## 1. What was run

| | |
|---|---|
| Cases **prepared** | **20** (4 each across 5 categories) |
| Cases **run live** | **8** |
| Stop reason | **`turn_ceiling_reached`** — 38 of 40 turns used; a case needs 5 |
| Subscription turns | **38 / 40** (anthropic 23, xai 15) |
| Paid API calls | **0** |
| Provider limit events | none |

Execution order interleaved the five categories deliberately, so stopping at
the ceiling left **coverage of all five** rather than four finished
categories and one untouched. Stopping with 12 cases unrun is the correct
outcome: the Owner did not authorise unlimited subscription use.

**Ground truth was frozen before execution** — fingerprint
`c51b4a39d6ec6719`, re-checked before and after every case. All 16 binary
cases cite a primary source with a quote and an access date. None was
authored by a model under test.

**Baseline frozen: `claude-sonnet-5`** — deliberately Deep Consensus's own
slot A, so the measured delta is attributable to the second *family* plus
the governor rather than to a model upgrade.

---

## 2. Headline numbers

| Metric | Baseline | Deep Consensus |
|---|---|---|
| Correct (binary, n=7) | **0.571** (4/7) | **0.857** (6/7) |
| Partial | 0.286 | 0.000 |
| Material errors | 1 | 1 |
| Defect identified (judgment, n=1) | 1.0 | 1.0 |
| Model turns per case | **1** | **4.75 avg**, median 5 |

| | |
|---|---|
| Errors caught vs baseline | **2** — `S4-DB-1-create-index-lock`, `S4-VER-1-spring-boot-java-baseline` |
| Errors introduced by governor | **0** |
| False disagreements | **5 of 8** |
| Missed pairings (estimate) | 2 |
| Unresolved rate | 0.75 |
| DC stopped at 2 calls | **12.5%** |
| DC required 4 calls | **87.5%** |

---

## 3. The honest reading of "2 errors caught"

**Both catches were `PARTIAL` → `YES`, not `NO` → `YES`.** The baseline did
not assert a falsehood in either case; it gave an *incomplete* answer and
Deep Consensus produced the complete one. The harness counts that as
"caught" because its `baseline_ok` test is `verdict ∈ {YES,
DEFECT_IDENTIFIED}` — a definitional choice, and it flatters the product.

So the defensible claim is narrower than the metric name:

> On 2 of 7 binary cases, the cross-family review produced a **more complete**
> answer than the frozen single-model baseline. On 0 cases did it correct an
> outright false claim, because the baseline did not make one in this sample.

**The one case where the baseline was outright wrong, Deep Consensus was
wrong too.** `S4-DB-3-read-uncommitted`: both scored `NO`. Both models share
the misconception, so cross-family review cannot help — the
same-wrong-answer limitation, now measured rather than asserted for the
second sprint running.

---

## 4. The cost: 4.75 turns against a baseline of 1

87.5% of cases took the full 4 Deep Consensus calls, versus 85% stopping at
2 in Sprint 3. The minimum-call governor got *worse*, and the cause is
specific and traceable.

**Sprint 3's pairing fix moved the failure from false negatives to false
positives.** Before it, subjects did not pair, so conflicts went undetected
and runs early-stopped at 2 turns. After it, subjects pair — and the **value
comparator** now raises conflicts between values that are semantically
identical but differently phrased:

| Slot A value | Slot B value | Overlap | Verdict |
|---|---|---|---|
| `do not pool virtual threads in fixed-size pool` | `do not pool` | 0.40 | CONFLICT |
| `IO-bound/blocking work` | `IO-bound` | 0.33 | CONFLICT |
| `no transaction starts` | `no transaction for inner call` | 0.33 | CONFLICT |
| `deletes untracked and ignored files/dirs with no recovery` | `force-deletes untracked and gitignored files and directories` | 0.33 | CONFLICT |

5 of 8 cases contained at least one of these. Each costs 2 extra turns, and
the challenge round then resolves most of them to
`CORRECTED_AND_AGREED` — i.e. **the system spent two model turns to discover
the models had agreed all along.**

---

## 5. Why the value comparator was NOT loosened

The obvious fix is the one that worked for subjects: containment instead of
symmetric overlap. It resolves the table above. It also does this:

| | | containment |
|---|---|---|
| `writes blocked` | `writes not blocked` | **1.00** |
| `reads blocked` | `reads allowed` | 0.50 |
| `transaction starts` | `transaction does not start` | 0.50 |

A false **disagreement** costs two model turns and the challenge round fixes
it. A false **agreement** publishes a contradiction as settled fact. Those
costs are not comparable, so the comparator stays strict and the turn cost
is accepted deliberately. A test now enforces that decision so a later
"small improvement" cannot quietly reverse it.

---

## 6. A high-severity defect found by writing that safety test

While writing the test above — not by reading the code — the comparator was
found to already have the dangerous version of this bug:

```
values_agree("no transaction starts", "a transaction starts")  ->  True
```

A claim and its direct negation compared as **agreeing**. Cause: the
content-word filter drops tokens of two characters or fewer, and `no` is two
characters. `not` (three) survived, which is why only this shape leaked —
and why it would have been easy to miss forever.

Fixed with an explicit negation-parity check, run *before* the overlap test,
which can only ever turn an "agree" into a "conflict" and never the reverse.
Seven negation pairs are now locked by test; identical values still agree;
numbers and versions are unaffected.

**This is the single most valuable thing the sprint produced.** A
contradiction silently reported as agreement is precisely the failure Deep
Consensus exists to prevent, and it was live in the engine while the
evaluation was running.

---

## 7. Pairing diagnostics (reported separately, never folded into accuracy)

| | |
|---|---|
| Pairs formed | 20 |
| Material one-sided claims | 29 |
| Estimated missed matches | **2** |

The estimate counts material one-sided claims from **opposite** slots whose
values actually agree — near-certain same-claim pairs the matcher failed to
join. Down sharply from Sprint 3, where entire runs paired nothing, but 29
material one-sided claims still means the two models frequently decompose a
question differently and much of each answer is never compared at all.

---

## 8. Product continuation gate: **MIXED**

> Deep Consensus corrected 2 cases the frozen baseline got wrong (both
> `PARTIAL` → `YES`, not false → true) while introducing 0 new errors, at
> 4.75 model turns per case against the baseline's 1. It showed 5 false
> disagreements in 8 cases and 2 estimated missed pairings, so the overhead
> is not clearly justified by the catches. On the one case where the baseline
> was outright wrong, Deep Consensus was wrong in the same way.

Not PROMISING: no outright falsehood was corrected, and the turn cost is
roughly 5×. Not NOT_YET_JUSTIFIED: the correctness rate did improve, 0
regressions were introduced, and the cost driver is a specific, identified,
fixable comparator problem rather than something fundamental.

**N=8. No statistical significance is claimed or implied.** Twelve prepared
cases remain unrun.

---

## 9. Known limitations

1. **N=8 of 20.** Stopped at the authorised turn ceiling.
2. **"Errors caught" means PARTIAL → YES**, not false → true (§3).
3. **A stronger single baseline was not measured.** `claude-opus-5` is
   available on the same subscription and may well beat sonnet+grok
   combined. That is a different and important question, named rather than
   avoided.
4. **Scoring is lexical**, not a model judging a model — deliberately, to
   keep the headline number off a third unreviewed opinion. It can mark a
   correct-but-oddly-worded answer wrong, so every row keeps the raw text
   for audit.
5. **One judgment case ran**, and both paths identified the defect, so the
   agent-plan category shows no advantage either way on n=1.
6. **The negation fix is not reflected in these numbers** — it landed after
   the live run, with 2 turns remaining. Re-measurement is the first task
   next session.
7. **Shared blind spots remain undetectable** (`S4-DB-3`), and all evidence
   is `MODEL_ONLY`.
8. 29 material one-sided claims mean much of each answer is never compared.

---

## 10. Next highest-value change

**Re-run the 8 executed cases with the negation fix in place, then measure
whether value-level false disagreement can be reduced without loosening the
comparator.** The specific idea worth testing is *asymmetric* handling:
treat a short value that is wholly contained in a longer one as agreement
**only when negation parity matches and the shorter value has at least two
content tokens** — which resolves `do not pool` ≡ `do not pool virtual
threads in fixed-size pool` while leaving `writes blocked` vs `writes not
blocked` a conflict. It must be proven on both the agreement set and the
negation set before it ships.

That one change plausibly moves the 87.5% four-call rate back toward
Sprint 3's 85% two-call rate, which is what decides whether the turn cost is
defensible.
