# Deep Consensus — FINAL CLOSURE

**Date:** 2026-10-02
**Branch:** `deep-consensus-sprint5-typed-claims` (local only)
**Status:** **PAUSED AFTER SPRINT 6 — PRODUCT THESIS UNPROVEN**
**Next sprint:** **NONE AUTHORIZED**

This is the canonical closing record of the Deep Consensus experimental
program. It interprets frozen evidence. It does not alter any of it.

---

## 1. Final owner adjudication

> **OWNER ADJUDICATION: PAUSE.**

The Owner reviewed the two flagged measurement rows that the mechanical
verdict depended on and determined they are not genuine material baseline
falsehoods. The predeclared scientific interpretation of the frozen evidence
is therefore **PAUSE**.

This adjudication is an **interpretation of frozen evidence, not a mutation
of the experiment.**

---

## 2. Mechanical result vs owner adjudication

Both are true statements about different things, and both are preserved.

```
FROZEN MECHANICAL PIPELINE
        |
        v
ONE MORE LOOK  (Rule 5)
        |
        v
OWNER REVIEWS FLAGGED MEASUREMENT ARTIFACTS
        |
        v
ARTIFACTS ARE NOT GENUINE MATERIAL FALSEHOODS
        |
        v
SCIENTIFIC INTERPRETATION OF FROZEN EVIDENCE
        |
        v
PAUSE  (Rule 3)
        |
        v
NO NEW EXPERIMENT
```

| Layer | Value | Where it lives |
|---|---|---|
| Frozen mechanical verdict | **ONE MORE LOOK — Rule 5** | `sprint6-decisive-results.json` → `frozen_verdict` (UNCHANGED) |
| Owner scientific adjudication | **PAUSE — Rule 3** | this document |
| Final program status | **PAUSED / PRODUCT THESIS UNPROVEN** | this document, `PROJECT_STATE.json` |

**The frozen mechanical result has not been edited, and must never be.** The
rule that fired, fired. Rewriting it to say PAUSE would destroy the only
evidence that the pipeline was followed mechanically rather than steered to a
conclusion — which is the single most valuable property this program has.

Rule 5 as frozen: *">= 1 baseline material false claim corrected OR
specifically exposed, AND Deep Consensus introduced zero material false
claims -> ONE_MORE_LOOK."*

Rule 3 as frozen: *"baseline material false claims == 0 -> PAUSE. This is NOT
inconclusive, NOT rerun, NOT collect harder cases."*

---

## 3. Why the two rows are measurement artifacts

The mechanical ONE MORE LOOK rested **entirely** on two claims in one blind
case, `S6-BLIND-JV-1-bare-transactional-defaults`:

| Frozen golden claim | Baseline answered | Reality |
|---|---|---|
| `default_propagation` = ENUM `REQUIRED` | `PROPAGATION_REQUIRED` | the same propagation. `TransactionDefinition.PROPAGATION_REQUIRED` and `Propagation.REQUIRED` are two documented spellings of one value. |
| `default_isolation_level` = ENUM `DEFAULT` | `ISOLATION_DEFAULT` | the same isolation. `TransactionDefinition.ISOLATION_DEFAULT` and `Isolation.DEFAULT` likewise. |

The baseline was **correct** on both. The frozen case data pinned one
spelling of a value that has two, and the ENUM comparator — correctly
performing normalised-exact equality and never similarity — reported a
CONFLICT.

**The comparator was not at fault and must not be weakened.** Exact ENUM
equality is precisely the property that makes `SHARE` vs `ACCESS EXCLUSIVE` a
genuine conflict. The defect was in the benchmark, and it was detectable at
zero model turns before freezing (see lesson A16).

Detected post-hoc by `deep_consensus/sprint6_suspect_scoring.py`, which
changes no score, no case and no rule. Its output:

```
mechanical baseline false claims : 2
mechanical catches               : 2
FLAGGED baseline false claims    : 2
FLAGGED catches                  : 2
if every flagged row is artefact : 0 baseline false claims, 0 catches
```

---

## 4. Final Sprint 6 measurements

Engineering/evidence-integrity run: **PASS**. Mechanical product verdict:
**ONE MORE LOOK**. Owner adjudication: **PAUSE**. Final: **PAUSED / THESIS
UNPROVEN**.

### Sizing

| | |
|---|---|
| estimate | 300–360 min |
| midpoint | 330 min |
| confidence | LOW |
| mode | CONCURRENT |
| agents planned / used | 6 / 6 |
| reconciliation allowance | 40 min |
| actual | **97 min** |
| ratio | **0.295** |
| conclusion | **ESTIMATION WRONG — over-estimate** |

### Phase 1 safety work

| | |
|---|---|
| scorer negation + substring audits | COMPLETE — **9 defects** |
| identity-key audit | COMPLETE — **2 defects** |
| duplicate-id regression | PRESENT |
| downstream tests | PRESENT |
| mutation gate | **PASS 19/0** |

### Baseline entitlement

| | |
|---|---|
| attempted / answered | YES / YES |
| requested | `claude-opus-5` |
| reported | `claude-haiku-4-5-20251001` |
| entitlement result | **NOT GRANTED** |
| frozen baseline | **`claude-sonnet-5`** |

An answer is not an entitlement. The subscription accepted the Opus model
identifier and served Haiku 4.5. Freezing that literally would have made the
"strongest baseline" weaker than the verified Sonnet and every subsequent
figure flattering by construction.

### Frozen datasets — hashes preserved verbatim, never regenerated

| | |
|---|---|
| blind N | 8 |
| challenge N | 12 |
| blind hash | `50e94aef19e56b5ec17d62708934a55c34e96cf8d6d0cc300c00304b565736cb` |
| challenge hash | `5cd28db988a720f7dccf8c137b16a169eee76bf93bc15d6ec717b1036adb20b4` |
| sources/scoring hash | `bceedd51113d0fa7fa0142b2807d0aced64767a44f1a160d7b9c6162a8164796` |
| decision-rule hash | `1bd284c96815d8867475a726531b4f2bac5df7741ad87ec0fef546e5d63977a5` |
| package hash | `a4d7e1c7c70e2da1adca72ffa923b2459022f53e48e8d5c0224fa7044711dd5f` |
| frozen at (UTC) | `2026-10-02T07:40:50.855909+00:00` |
| freeze git HEAD | `a66f9d88a8c52faad9bebedfd068c97ba3cf0beb` |

### Results — BLIND and CHALLENGE never pooled

| | BLIND (n=8) | CHALLENGE (n=12) | TOTAL (N=20) |
|---|---|---|---|
| baseline material false claims (mechanical) | 2 | **0** | 2 |
| corrected | 2 | 0 | 2 |
| specifically exposed | 0 | 0 | 0 |
| repeated | 0 | 0 | 0 |
| **DC introduced** | **0** | **0** | **0** |
| unresolved useful | 0 | 0 | 0 |
| unresolved noise | 3 | 7 | **10** |
| NEEDS_OWNER | 11 | 18 | **29** |
| average DC turns | 3.75 | 3.92 | **3.85** |

median DC turns 4.0 · 2-turn cases 0 · 3-turn cases 3 · 4-turn cases 17 ·
baseline turns 1 per case.

### Owner scientific interpretation of the same frozen evidence

| | |
|---|---|
| genuine baseline material false claims demonstrated | **0** |
| genuine Deep Consensus FALSE → TRUE catches demonstrated | **0** |
| Deep Consensus introduced material false claims | **0** |
| challenge-set baseline material false claims | **0 / 12** |
| unresolved-noise cases | **10 / 20** |
| average DC turns vs baseline | **3.85 vs 1** |

### Providers

| | |
|---|---|
| Claude subscription calls | 61 |
| Grok subscription calls | 38 |
| paid API calls | **0** |
| billing violations | **0** |
| provider-limit events | **0** |
| ceiling / committed | 102 / 99 |

### Replay

| | |
|---|---|
| Sprint-5 recordings replayed | 8 |
| differences | 6, **all EXPLAINED with evidence** |
| DEFECTs | **0** |
| REPLAY_DIVERGED | **0** |
| model calls | **0** |
| Sprint-6 self-replay | 20 replayed, **0 differences**, **0 model calls** |

The six Sprint-5 differences were each a false credit withdrawn by the
Sprint-6 scorer fix, verified against the recorded text before any rule was
written to explain them: `pin` had been matching inside **kee·pin·g**, and
`26` inside **january 20·26** — the model's own knowledge-cutoff sentence.

### Fixtures

77 stored · full text preserved · secrets **0**.

---

## 5. Evidence-integrity status

**PASS — 16 of 16 checks.**

| check | result |
|---|---|
| frozen hashes still match | PASS |
| cases changed after freeze | **NO** |
| sources changed after freeze | **NO** |
| scoring changed after freeze | **NO** |
| decision rule changed | **NO** |
| baseline switched | **NO** |
| evaluated cases rerun | **NO** |
| four-call cap respected | PASS |
| no billing violation | PASS |
| no billing var in child allowlist | PASS |
| cross_family_real on every case | PASS |
| baseline used subscription transport | PASS |
| notional cost not converted to billed | PASS |
| secret scan | PASS |

---

## 6. Open action-item status

**12 of 14 closed. Two remain honestly open. A15–A23 remain UNAPPROVED and
are not implemented.**

| # | State |
|---|---|
| A1 | **APPROVED, applied by hand, NOT CLOSED** — the sizing gate is not mechanised. Closing it would claim a mechanism that does not exist. |
| A2 | CLOSED |
| A3 | CLOSED — deviation: 4 sprints, not 5 (Sprint 5 was genuinely sized; its real ratio is calibration data and was not deleted) |
| A4 | CLOSED |
| A5 | CLOSED |
| A6 | CLOSED — Owner |
| A7 | CLOSED |
| A8 | CLOSED |
| A9 | CLOSED |
| A10 | **APPROVED, NOT CLOSED** — never exercised; no cost-motivated change to a correctness component arose |
| A11 | CLOSED |
| A12 | CLOSED |
| A13 | CLOSED |
| A14 | CLOSED — one overspend turn recorded |

**A15–A23: UNAPPROVED. Retained as lessons and proposed future controls only.
They are not authorization for another sprint and must not be silently
promoted to approved backlog.**

Two are preserved verbatim because they are the most valuable:

> **A16** — Before freezing a future benchmark, run the scorer against the
> frozen golden claims using a deliberately correct synthetic answer. Any
> golden claim that does not score CORRECT is a benchmark/scoring defect
> detectable at zero model turns.

> **A17** — Any assertion over prose inside a guard, scorer, identity
> mechanism, routing rule, or test should be treated as suspect by default.
> This defect pattern has repeatedly produced false conclusions.

A16 would have caught this sprint's artifact before the freeze, at zero
turns. A17 describes a pattern that fired **five times across two sprints**.

Neither is implemented now. They are lessons.

---

## 7. Why no Sprint 7 will occur

The decision rule was frozen and pre-registered before any evaluated answer,
and the scientific interpretation of the frozen evidence is PAUSE. PAUSE
means stop, not "stop and immediately design a better experiment."

Starting Sprint 7 after a PAUSE would convert a pre-registered decision rule
into a formality — the thing it exists to prevent. The program closes here.

## 8. Why no ablation will occur

An ablation (strongest-model-only versus strongest-model-plus-verification,
or any component-removal study) is a **new experiment** requiring a new
pre-registration, new primary-source cases and new subscription turns. It
would be run in the shadow of a thesis that has just failed its own decision
rule, which is precisely the condition under which a result cannot be
trusted. Not authorized, not performed.

## 9. Why Sprint 6 will not be rerun

Rerunning a completed pre-registered experiment after seeing its result is
the canonical way to manufacture a different one. The run completed cleanly
(`completed_all_frozen_cases`, 20/20 cases, zero provider limits), the
evidence passed every integrity check, and the result is reproducible offline
with zero model calls. There is nothing to recover by rerunning it and
everything to lose.

## 10. Why no replacement benchmark will be constructed

The challenge set was selected by **predeclared failure-prone category** from
primary sources, before any model answered, and the frozen Sonnet baseline
answered **all 12 correctly**. The set's own author recorded in advance that
this was a possible and legitimate outcome, and that it must be reported as a
real result rather than treated as a reason to hunt harder questions.

Building a new, harder benchmark now — after observing that the baseline did
not fail — would be difficulty escalation after seeing results. It is
explicitly forbidden by the frozen protocol and it is the exact behaviour
that makes negative results disappear from projects.

**The negative result is the finding, and it is preserved.**

---

## 11. Measurement-system lessons

### The central finding of the program

> **Every major product headline in the recent evaluation history was
> determined by a defect in the measurement system rather than by
> demonstrated product capability.**

- **Sprint 5 produced a manufactured regression.** A substring test read
  *"they are **not** suited to CPU-bound work"* as publishing the falsehood
  *"suited to cpu-bound"*. The answer was correct. The sprint's headline
  briefly became "Deep Consensus introduced a material false claim".
- **Sprint 6 produced a manufactured catch.** An ENUM spelling difference
  (`PROPAGATION_REQUIRED` vs `REQUIRED`) became two baseline falsehoods and
  two catches, which is the sole support for the mechanical ONE MORE LOOK.

**These defects point in opposite directions.** One made the product look
worse than it was; the other made it look better. That rules out a simple
evaluator bias for or against the product, and licenses only one conclusion:

> **The measurement system was not yet reliable enough to support the product
> claim.**

### Thirteen defects found in Sprint 6, every one observed failing first

Nine in the scorer, two in identity/routing, one in the entitlement check,
and two in the artifact detector built to catch the artifact.

The two identity defects deserve naming because they are the most dangerous
class found anywhere in the program: both would **publish a false
agreement**. Stage-4 decisions were routed by normalised subject — a
model-written string — so two claims sharing a subject collapsed to one
routing entry and a claim whose own models both said MAINTAIN could resolve
`CORRECTED_AND_AGREED` carrying a value copied from a different claim.
Separately, fuzzy reword routing picked a winner among equally plausible
subjects. Neither would have been visible in the result.

### The recurring defect pattern

A guard, scorer or test that searches **text** for the name of a thing it
forbids will fire on the text that forbids it. Observed five times across two
sprints:

1. `import itertools` flagged as importing the coding-agent module `tools`.
2. The Sprint-5 scorer reading *"not suited to CPU-bound"* as a claim.
3. A frozen case recording `false` for *"is the convergence score a
   correctness probability"* flagged by the honest-labelling guard.
4. A test asserting `"pooled"` absent from a summary dict, firing on the
   sentence that forbids pooling.
5. A test asserting `"inconclusive"` absent from a verdict, firing on
   *"so this is PAUSE -- not inconclusive"*.

**The fix in every case is to assert over STRUCTURE** — keys, verdict values,
parsed imports, typed comparisons — **never over prose.**

### A surviving mutant is a question, not a verdict

The mutation gate blocked on a surviving safety-critical mutant that turned
out to be harmless by construction: setting a negation window constant to `0`
makes `tokens[-0:]` equal `tokens[0:]` — the whole list — so the mutant
*widened* negation detection. Reporting it as a coverage gap would have been
a false finding about the suite. It was replaced with a mutation that
genuinely removes the check, and killed.

### The governance lesson

> **Assurance systems must validate their evaluators as aggressively as they
> validate models.**

In this program the scorer carried nine defects while the engine under test
carried two. A measurement is only as trustworthy as its own worst bug, and
nothing downstream questions a number that flatters the thing being measured.

---

### The two named methodology lessons (A16, A17)

Both are recorded here as **METHODOLOGY LESSONS ONLY**. Neither is
implemented. Both remain **UNAPPROVED** action items in the ledger, and
documenting a lesson does not implement it. Neither is authorization for a
sprint, and neither may be applied retroactively to regenerate or alter
Sprint 6.

---

#### A16 — score the benchmark before you trust it

> **Before freezing an evaluation set, test every frozen golden claim against
> a deliberately correct synthetic answer. If the scorer does not classify
> the deliberately correct answer as CORRECT, the benchmark/scorer pair is
> defective before any model turn is spent.**

**Why this matters, concretely.** Sprint 6's apparent product catch — the
sole support for the mechanical `ONE MORE LOOK` — was an evaluation artifact.
A synthetic answer asserting `Propagation.REQUIRED` and `Isolation.DEFAULT`,
written by hand and known to be correct, would have been scored INCORRECT by
the frozen scorer against the frozen golden claims, because those claims
pinned one of two documented spellings. **That is a benchmark defect
detectable at zero inference cost, before the freeze, before 99 subscription
turns were spent.** The control did not exist, so the defect survived into
the result and had to be caught post-hoc by an artifact detector instead.

The deeper point: a benchmark and its scorer are **one coupled artifact**,
and the coupled artifact needs its own test. Freezing a case set says nothing
about whether the scorer can read it.

**Status: NOT IMPLEMENTED.** Sprint 6 was not regenerated, its results were
not changed, and no scoring rule was altered after the first evaluated
answer.

---

#### A17 — prose assertions inside deterministic control logic

> **Assertions over natural-language prose inside scorers, guards, routing,
> identity logic, or tests are defect-prone unless their semantics are
> explicitly constrained.**

**The recurring failure family, stated precisely:**

> text mentions, negates, abbreviates, or represents X differently, while the
> detector incorrectly treats that text as an assertion of X.

Every instance found in this program fits that single sentence:

| sub-family | real instance |
|---|---|
| **negation** | the scorer read *"they are **not** suited to CPU-bound work"* as publishing *"suited to cpu-bound"* |
| **substring matching** | `pin` matched inside **kee·pin·g**; `26` inside **january 20·26**; `no` inside *now* / *normal* / *not*; `io` inside *production*; `it is safe` inside *it is safer* |
| **identity / routing** | two claims sharing a normalised **subject** collapsed to one Stage-4 routing entry, so a claim received another claim's decision |
| **fuzzy routing ambiguity** | reword routing picked a winner among equally plausible subjects |
| **representation mismatch** | `PROPAGATION_REQUIRED` vs `REQUIRED`; `ISOLATION_DEFAULT` vs `DEFAULT` |
| **measurement-artifact detection** | the artifact detector built to catch the above flagged `ACCESS EXCLUSIVE` vs `EXCLUSIVE` and `SHARE UPDATE EXCLUSIVE` vs `UPDATE EXCLUSIVE` as mere spellings — they are distinct PostgreSQL lock modes |
| **guards and tests** | `import itertools` flagged as importing module `tools`; a test asserting `"pooled"` absent fired on the sentence forbidding pooling; a test asserting `"inconclusive"` absent fired on *"so this is PAUSE -- not inconclusive"* |

Two of these produced **false disagreement** (recoverable: it costs model
turns and the challenge round resolves it). Two produced **silent false
agreement** (not recoverable: a contradiction is published as settled fact
and nothing downstream reopens it). They are not equally bad, and the design
must always resolve ambiguity away from agreement.

**The constructive form of the lesson:** assert over **structure** — keys,
enum values, verdict constants, parsed imports, typed comparisons — never
over prose. Where a proposition genuinely cannot be decided structurally, the
honest outcome is an explicit `NEEDS_OWNER` state adjudicated by a human, not
a cleverer string matcher. Each narrowing fix buys one input class and leaves
the next.

**Status: NOT IMPLEMENTED as a systematic control.** Individual defects found
in Sprint 6 were fixed with test-first regressions at the time; the general
rule is not enforced anywhere, and no linter, gate or review step implements
it.

---

## 12. Portfolio interpretation

**The portfolio claim is the refusal.**

Deep Consensus explored whether independent model families could improve
software-engineering answer reliability through sealed answers, typed claims,
deterministic comparison, cross-family challenge, replay, mutation testing
and strict call ceilings. During evaluation, increasingly strong controls
exposed defects not only in the product but in the measurement system itself.
Sprint 6's apparent success depended on two representation/scoring artifacts
rather than genuine baseline errors. The predeclared scientific
interpretation was therefore PAUSE. No new benchmark was created to rescue
the thesis, no Sprint 7 was started, and the negative result was preserved.
The strongest outcome became an AI-governance lesson: assurance systems must
validate their evaluators as aggressively as they validate models.

**Engineering quality and product validation are separate**, and this program
is a strong example of the first and a negative result on the second.

### What may truthfully be claimed — implemented, tested, observed, detected

- **Implemented** sealed independent model answers, with the seal proven
  against the real request text rather than call ordering.
- **Implemented** two real subscription-backed model families (Anthropic and
  xAI), with `cross_family_real` verified on every evaluated case.
- **Implemented and proved** zero paid API fallback in three layers:
  preflight auth proof, child-environment allowlist plus denylist assertion,
  and a post-run metered-provider check. 0 paid API calls across the program.
- **Implemented** typed claims (BOOLEAN / ENUM / NUMBER / VERSION / TEXT) and
  deterministic comparison for the constrained types only.
- **Implemented** the prohibition on local semantic comparison of free text;
  free TEXT is never adjudicated by string arithmetic.
- **Implemented** explicit unresolved states (UNRESOLVED, CONTRADICTED,
  UNCOMPARED, UNKNOWN, NEEDS_OWNER) with **no forced convergence**.
- **Implemented** hard model-call ceilings — 4 provider calls per review, no
  fifth call, no synthesis model — respected on every case.
- **Implemented** replayability: the Sprint-6 verdict is reproducible from
  recordings with 0 differences and 0 model calls.
- **Implemented** raw-answer retention without truncation, which made a
  scoring correction free rather than requiring a second paid run.
- **Implemented** regression testing, mutation testing (19 killed / 0
  survived), evidence freezing with refusal to re-register, and
  provider/authentication provenance recording (requested vs reported model
  recorded separately — and they genuinely differed, twice).
- **Detected** multiple scorer, identity and routing defects, including
  **silent false-agreement failure modes**.
- **Preserved** negative evidence and **refused to continue** after the
  thesis failed its decision rule scientifically.

### What must NOT be claimed

This program did **not** demonstrate any of the following, and the
documentation must never assert them:

- that Deep Consensus is more accurate than frontier models
- that Deep Consensus proved a FALSE → TRUE improvement
- that multiple models improve correctness
- that Deep Consensus is a best-answer engine
- that Deep Consensus is "deterministic AI"
- that Deep Consensus is maximum-assurance AI
- that Deep Consensus is safer than a single model
- that Deep Consensus reduces hallucinations
- that Deep Consensus beats Claude, Grok or any other model
- that consensus equals verification
- that the product thesis was validated

**PAUSE must not be quietly reinterpreted as "promising" or "partial
success."** It is a negative result on the product thesis.

---

## 13. FUTURE RESEARCH IDEAS — NOT AUTHORIZED, NOT IMPLEMENTED, NOT VALIDATED

> **WARNING.** Everything in this section is unbuilt design sketch. None of it
> was implemented, measured, or validated. It is **not** the Deep Consensus
> architecture and must never be described as such. It is recorded only so the
> thinking is not lost, and it is **not** authorization for any sprint.

Ideas explored on paper toward a possible future maximum-assurance engine:

- independent requirement sets
- claim **and context** verification
- per-claim evidence sets
- evidence applicability and provenance
- execution and tests as evidence
- versioned primary sources
- verification **before** model persuasion
- trust-laundering prevention
- final falsification pass
- strongest-model plus verification ablation
- observational model intelligence
- answer stability measurement

The PAUSE decision remains intact regardless of how attractive any of these
appear.

---

## 14. Final project state

| | |
|---|---|
| **Deep Consensus experimental program** | **PAUSED AFTER SPRINT 6** |
| **Product thesis** | **UNPROVEN** |
| **Next sprint** | **NONE AUTHORIZED** |
| Sprint 6 engineering / evidence integrity | PASS |
| Frozen mechanical verdict | ONE MORE LOOK — Rule 5 (preserved, unedited) |
| Owner scientific adjudication | PAUSE — Rule 3 |
| Branch | `deep-consensus-sprint5-typed-claims` |
| Pushed | **NO** |
| Deployed | **NO** |
| Sprint 7 | **NOT STARTED** |
| Ablation | **NOT STARTED** |
| Sprint 6 rerun | **NO** |
| Replacement benchmark | **NOT CREATED** |
| NEEDS_OWNER items outstanding | 29 |

### Evidence index

All under `docs/evidence/deep-consensus-sprint6/`:

| file | contents |
|---|---|
| `sprint6-decisive-results.json` | all 20 case rows, frozen mechanical verdict, full untruncated answers |
| `frozen-evidence-manifest.json` | the pre-registered package and its hashes |
| `FROZEN_MANIFEST.md` | human-readable frozen package |
| `frozen-baseline.json` | the single entitlement invocation and the frozen baseline |
| `suspect-scoring-audit.json` | the two flagged rows and both readings |
| `evidence-integrity-manifest.json` | 16/16 integrity and billing checks |
| `sprint5-replay-report.json` | Sprint-5 replay, 6 differences all explained |
| `sprint6-selfreplay-report.json` | Sprint-6 self-replay, 0 differences |
| `fixture-index.json` | 77 transcript fixtures, hashes, secret scan |
| `transcripts.jsonl` | raw redacted provider turns (immutable) |
| `SPRINT6_FINAL_REPORT.txt` | generated report, every figure read from evidence |
| `RETRO_SPRINT6.md` | retro, including the estimate-vs-actual table |
| `ACTION_ITEM_CLOSURE.md` | A1–A14 assessed against work actually done |
| `OWNER_DECISIONS_SPRINT6.md` | Owner decisions recorded before implementation |

Earlier sprints: `docs/evidence/deep-consensus-sprint1` … `-sprint5`, and
`docs/DEEP_CONSENSUS_SPRINT1.md`.

**Presentation layer:** `docs/DEEP_CONSENSUS_CASE_STUDY.md` is a one-page
case study for interviews. It is presentation and may be rewritten; this
closure document and the frozen evidence are the authority, and the case
study must never make a claim this document forbids.

**Off-machine backup:** a full-history `git bundle` of all 93 refs at HEAD
`30b1e4c1d86bf7ad856af83c1b50e4956ab55a0e`, verified by real clone-and-
compare, lives on a separate physical drive with a plaintext recovery note
beside it. The only configured remote (`origin`) was verified PUBLIC and was
deliberately NOT pushed.

---

**Closed 2026-10-02. Interpretation only; no frozen evidence was altered.**
