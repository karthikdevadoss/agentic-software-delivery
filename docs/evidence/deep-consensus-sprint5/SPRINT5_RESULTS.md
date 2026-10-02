# Deep Consensus — Sprint 5: typed claims and the one-sided cross-check

Branch `deep-consensus-sprint5-typed-claims`. Not pushed, not deployed. No
paid API call, no API-key model call, no third family.

The question: **did typing the claim values and cross-checking one-sided
claims change the Sprint-4 result on the same eight cases?**

The answer: **the mechanism improved measurably, the product evidence did
not.** Status quality improved, the examination gap closed, and the turn
cost got very slightly worse. Zero outright falsehoods were corrected —
because the frozen baseline published zero outright falsehoods in this
sample.

---

## 1. What was run

| | |
|---|---|
| Cases run | **8 of 8** — exactly the Sprint-4 case ids |
| Ground truth | fingerprint `c51b4a39d6ec6719`, **unchanged from Sprint 4**, re-checked before and after every case |
| Baseline model | **`claude-sonnet-5`**, frozen, unchanged from Sprint 4 |
| Deep Consensus | A = `claude-sonnet-5` (anthropic), B = `grok-4.6` (xai) |
| `cross_family_real` | **true on all 8** |
| Subscription turns | **39 / 40** (anthropic 24, xai 15) |
| Paid API calls | **0** |
| Billing violations | **0** |
| Provider limit events | **0** |
| Turn ceiling raised | **no** |

8 baselines + 31 Deep Consensus calls = 39. The ledger charges per slot and
the figure is exact, not a division of a total — see §6.

**Model substitution, recorded because it is real:** every slot-B turn
requested `grok-4.6` and the provider reported **`grok-4.6-build`**. Sprint 3
required `requested_model` and `reported_model` to be recorded separately;
that requirement is now demonstrably load-bearing rather than ceremonial.

---

## 2. Correctness: no change, and the reason matters

| | Baseline | Deep Consensus |
|---|---|---|
| CORRECT_COMPLETE | 7 | 7 |
| CORRECT_INCOMPLETE | 1 | 1 |
| INCORRECT | 0 | 0 |

**All 8 cases: `SAME_RESULT`.** Zero `FALSE_TO_TRUE`, zero
`FALSE_TO_SPECIFICALLY_EXPOSED`, zero `INCOMPLETE_TO_COMPLETE`, zero
regressions.

The decisive fact is in the first column: **the baseline published no
material falsehood on any of the eight cases.** The opportunity for this
product to demonstrate its central claim did not arise. That is a property
of the sample, not a result about the product, and it must not be reported
either as a success or as a failure.

**Sprint 4 reported "2 errors caught" on these same cases and this run
reports 0. That difference is mostly the SCORER, not the product.** Sprint 4's
`baseline_ok` test was `verdict ∈ {YES, DEFECT_IDENTIFIED}`, which counted a
completeness gain as a catch — the Sprint 4 report said so itself. Sprint 5
separates the categories by construction, and under that separation both
former catches are completeness-neutral. The underlying fact is identical in
both sprints: **no outright falsehood was corrected, because none was
offered.** Comparing the two counts as if one scorer produced both would be
dishonest.

---

## 3. What genuinely improved: the examination gap

This is the real Sprint-5 result.

| | Sprint 4 | Sprint 5 |
|---|---|---|
| Material one-sided claims | 29 | 18 |
| **Of those, ever shown to the other model** | **0** | **18** |
| Confirmed by the other model | — | 11 |
| Contested | — | 1 |
| Answered UNKNOWN | — | 3 |
| Left UNCOMPARED | — | 3 |

Sprint 4 reported 29 material claims that only one model had made, and not
one of them was ever shown to the model that had not made it — while those
runs still reported CONVERGED. Half of an answer could be unexamined
assertion and the status said agreement.

Every eligible claim is now asked about, and **UNCOMPARED blocks
convergence**, so CONVERGED is no longer reachable without having looked.
The 3 UNCOMPARED claims produced `PARTIAL` and `UNRESOLVED` statuses rather
than a confident one.

**Status quality improved on 4 of 8 cases:**

| Case | Sprint 4 | Sprint 5 |
|---|---|---|
| S4-DB-1-create-index-lock | UNRESOLVED | **CONVERGED** |
| S4-DB-3-read-uncommitted | UNRESOLVED | **CONVERGED** |
| S4-JV-4-virtual-thread-pooling | UNRESOLVED | **CONVERGED** |
| S4-SEC-3-bcrypt-salt-column | UNRESOLVED | **CONVERGED** |
| S4-VER-1-spring-boot-java-baseline | PARTIAL | UNRESOLVED (worse) |
| S4-JV-1, S4-SEC-1, S4-AP-2 | unchanged | unchanged |

Four cases that previously could not be settled now settle, and the
correctness did not move — so these are runs that used to report doubt about
answers that were already right.

**`converged_with_uncorroborated_one_sided` is true on 3 of the 4 CONVERGED
cases.** Those converged while relying on a claim confirmed only after being
SHOWN to the other model, which is a weaker thing than independent
agreement. It is flagged rather than flattened, because the flag is the
honest part.

---

## 4. What did not improve: the turn cost

| | Sprint 4 | Sprint 5 |
|---|---|---|
| Deep Consensus turns, total | 30 | **31** |
| Average per case | 3.75 | **3.875** |
| Runs at 2 calls | 1 of 8 | **0 of 8** |
| Runs at 3 calls | 0 | 1 |
| Runs at 4 calls | 7 | 7 |

**The typed comparator did not restore the 2-call early-stop path. It
removed the one instance of it.** The cost moved rather than fell: Sprint 4
spent turns on false conflicts between differently-worded prose; Sprint 5
spends them on pairs it correctly declines to judge (`TEXT_UNDECIDED`, 8
across the 8 cases) plus the new cross-check.

This was predictable from the design and should have been predicted in the
sizing: a `TEXT_UNDECIDED` pair still earns a review turn, and the
cross-check creates turns in runs that previously had no conflict at all.
`S4-DB-1` is the clearest example — it cost 2 calls in Sprint 4 and 3 now,
and the extra call is a cross-check turn that examined a claim Sprint 4 had
left unexamined. **That is a better run that costs more**, which is a real
trade and not a regression; but the headline cost figure moved the wrong way
and saying otherwise would be spin.

**Noise rate 0.375** — 3 of 8 cases reported UNRESOLVED while the baseline
had published nothing false, so the extra turns protected against nothing in
those cases.

---

## 5. Product continuation gate: **STILL_MIXED**

> Zero `FALSE_TO_TRUE` and zero `FALSE_TO_SPECIFICALLY_EXPOSED` across 8
> cases, at 4.88 model turns per case against the baseline's 1. The baseline
> published 0 material falsehoods, so the opportunity to demonstrate value
> did not arise in this sample. Noise rate 0.375.

Not `EVIDENCE_IMPROVED`: nothing was corrected, and the turn cost rose.
Not `NOT_JUSTIFIED`: zero regressions were introduced, the examination gap
genuinely closed, and 4 of 8 statuses became correctly confident.

**N=8. No statistical significance is claimed or implied.** Twelve prepared
cases remain unrun and were deliberately not touched — adding them would
have improved the sample and destroyed the comparison.

**The sample cannot answer the product question.** Eight cases on which a
strong single model is already right cannot show whether review catches its
errors. The next evidence sprint needs cases where the frozen baseline
actually fails; selecting those without peeking at model behaviour is the
hard part and is the real open problem.

---

## 6. Four defects found, three of them in code written this sprint

| # | Defect | Consequence if shipped |
|---|---|---|
| 1 | `typed_values._version_bridge` enforced its own docstring by testing the raw text only, so a unit passed as a declared field was invisible | `"17"` with unit `bytes` **AGREED** with version 17 — false agreement across two kinds of fact, reachable only through the declared-unit path, which no test covered |
| 2 | The TEXT identity exception used `normalize_text`, which turns punctuation into spaces | `"x > y"` and `"x < y"` **AGREED**. A reversed comparison operator published as settled. Caught by a test whose stated objection to identity was precisely this |
| 3 | `pair_claims` keyed consumed claims by model-supplied `claim_id` | Two claims sharing an id meant one **vanished from the comparison entirely** — not UNCOMPARED, absent. Model-supplied text was being used as an identity key |
| 4 | A local `by_slot` in `_dispatch` collided with an existing local holding `(response, error)` tuples | `TypeError` on any failed dispatch |

Two of the first three were in **cost-motivated** changes to a correctness
component. That is the pattern worth carrying forward: a change made to save
turns deserves at least the scrutiny of a change made to fix correctness,
because the motivation feels harmless.

### The fifth defect was in the measurement, and it produced a false headline

The scorer that decides whether an answer published a falsehood used a plain
substring test. It read the governed answer

> "They are **not** suited to CPU-bound work, since CPU-bound tasks keep the
> carrier thread busy..."

as having published the falsehood `"suited to cpu-bound"`. The answer is
correct and agrees with the frozen ground truth. On that single false
positive, **this run's first product verdict was that Deep Consensus had
introduced a material false claim** — a regression that never happened.

This is the same negation blindness that was fixed in the claim comparator,
sitting in the tool that measures whether the product publishes falsehoods.
Fixing a defect in one layer does not fix the layer that measures it.

**It was corrected at zero model turns.** The run stores
`baseline_result_full` and the entire `deep_consensus_result_object`
untruncated, so scoring is a pure function of stored text plus frozen ground
truth, and `rescore_sprint5.py` re-derived every outcome for free. One
category changed: `S4-JV-4` from `TRUE_TO_FALSE` to `SAME_RESULT`. That is
the first time this project's refusal to truncate evidence has actually paid
out, and it paid for the whole policy.

### The turn-ledger leak

The charge was `provider_calls // 2`, justified by a comment reading "turns
are split evenly across the two slots by construction" — true while every
run cost 2 or 4. Sprint 5 made the 3-call path real, and `S4-DB-1` took it
on the very first live case with `by_slot = {"A": 2, "B": 1}`. The old
arithmetic would have charged that as 1 per slot, losing a real subscription
turn from the ceiling and leaving a dangling reservation. Fixed, extracted as
`turns_to_charge`, and tested without live providers.

---

## 7. Gates — both passed before any live turn

| Gate | Result |
|---|---|
| Deterministic tests | **417 tests, 7 suites, all green** |
| Comparator mutation gate | **10 killed / 0 survived / baseline green / nothing skipped — PASS** |
| Live turns spent before the gates passed | **0** |

**The mutation gate blocked on its first run and the two survivors were
real, not equivalent mutants.** Nothing in the then-275 tests asserted that a
material pairing with no agreed state blocks CONVERGED — the single guard
stopping a claim one model never made from riding inside a consensus answer.
Both safety-critical mutants walked through that one hole. It is now killed
by 25 and 2 tests respectively.

Three mutation anchors that the gate's author had left undefined were treated
as **BLOCKING**, not skipped, once `typed_values.py` existed — an unexercised
safety-critical guard is UNVERIFIED and must never read as PASSED. Derived
from the real source and all three now kill.

Recorded-transcript replay is proven: a recorded 4-call run replays with no
divergence at zero turns, the replay providers assert `is_mock`, and a
negative control confirms the comparison detects a changed outcome. All 31
live turns were recorded; **31 recorded = 31 calls, zero transcript errors**.

---

## 8. Known limitations

1. **The sample cannot answer the product question.** The baseline was
   already correct on all 8 cases. Zero corrections is a fact about the
   cases, not a measurement of the product.
2. **N=8 of 20.** Twelve prepared cases deliberately unrun, to protect
   comparability.
3. **Sprint 4 and Sprint 5 used different scorers.** The "2 catches → 0"
   difference is mostly definitional and is not evidence of decline.
4. **A stronger single Claude baseline was still not measured.**
   `claude-opus-5` availability on this subscription remains **UNVERIFIED** —
   `claude --help` lists the alias, which is not entitlement. Probing costs a
   turn from a budget with none spare, and changing the baseline would
   confound the only comparison this sprint exists to make. Still open, and
   still the most important unanswered question about the product.
5. **`grok-4.7` is now the account default.** Slot B stayed pinned to
   `grok-4.6` for comparability, exactly as the Claude baseline stayed
   pinned.
6. **Scoring is lexical.** Deliberately, to keep the headline off a third
   unreviewed model opinion — and §6 shows exactly how a lexical scorer
   fails. Every row keeps the full raw text so any verdict can be re-derived.
7. **3 claims were left UNCOMPARED and 1 cross-check was contested**, so
   even the examination gap is not fully closed.
8. **The Grok preflight produced one transient false negative.** Safe
   direction — it refused before any provider call, costing zero turns — but
   it aborted an authorised run, and it nearly caused an incorrect escalation
   to the Owner asking him to run `grok login` when Grok was in fact logged
   in. Verifying the tool's own negative claim is what prevented the wrong
   ask. Mechanism unconfirmed; a bounded retry is now in place and does not
   weaken any evidence requirement.
9. **All evidence is `MODEL_ONLY`.** Cited sources are recorded and
   explicitly `UNVERIFIED`.

---

## 9. The next highest-value change

**Build an evidence set where the frozen baseline is actually wrong.**

Everything else is now secondary. The engine improved on every axis it can
be measured on internally — examination coverage, status honesty, zero
regressions, bounded cost — and none of that answers whether the product
reduces published falsehood, because the eight available cases never gave it
the chance. Two sprints have now produced that same non-answer.

The hard part is case selection: choosing cases where a strong model fails,
without choosing them by watching the model fail, which would manufacture the
result. That problem deserves its own design work before any more turns are
spent measuring.
