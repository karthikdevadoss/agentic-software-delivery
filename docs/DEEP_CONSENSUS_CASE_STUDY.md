# Deep Consensus — Building an AI Evaluation System That Stopped Itself

*2026-10-02 · outcome: paused, product thesis unproven · full record:
[DEEP_CONSENSUS_FINAL_CLOSURE_2026-10-02.md](DEEP_CONSENSUS_FINAL_CLOSURE_2026-10-02.md)*

*Narrative write-up of the same material, written for a general engineering
reader: `/article/evaluating-the-evaluator` on the running platform
(agent/web/article-evaluating-the-evaluator.html). Local only -- not published.*

## Problem

I wanted to test whether independent frontier-model families could reduce
material errors in software-engineering answers — the kind where being wrong
is expensive: lock modes, transaction semantics, version-specific behaviour,
auth distinctions.

## What I built

A bounded multi-model review behind one MCP tool. Claude and Grok each answer
**sealed** — neither sees the other, and the seal is proven against the real
request text rather than call ordering. Both run on **subscription-backed
transports with zero paid API fallback**, enforced in three layers (preflight
auth proof, child-environment allowlist plus denylist assertion, post-run
metered-provider check); across the whole program, 0 paid API calls.

Answers are decomposed into **typed claims**. Deterministic comparison runs
only for `BOOLEAN`, `ENUM`, `NUMBER`, `VERSION`. **Free text is never
compared semantically by local code** — it goes back to the models or is
marked uncompared. Disagreements trigger one batched **cross-family
challenge**, under a **hard four-call ceiling** with no fifth call and no
synthesis model. Nothing is averaged: `UNRESOLVED`, `CONTRADICTED`,
`UNCOMPARED`, `UNKNOWN` and `NEEDS_OWNER` are first-class outcomes.

Around that: **frozen, hashed evaluation data** registered before any
evaluated answer (and a freeze that refuses re-registration), **replay** from
recorded turns, **mutation and regression testing**, **untruncated
raw-answer retention**, and **provenance** recording requested *and* reported
model identity separately.

## What went wrong

Progressively stronger controls kept finding defects — increasingly in the
**evaluation machinery**, not the product. Across the final two sprints I
found and fixed, each with a test written and observed failing first:
negation errors, substring and prose-interpretation defects, duplicate claim
identity, subject-routing collision, fuzzy routing ambiguity, and
representation/scoring mismatches.

Some of these could only create **false disagreement** — recoverable, since
it costs model turns and the challenge round resolves it. Two could create
**silent false agreement**: two claims sharing a normalised subject collapsed
to one routing entry, so a claim whose own models both held their position
could be recorded as corrected-and-agreed carrying a value copied from a
different claim. Nothing downstream would have questioned it.

## The critical result

Sprint 6 ran 20 pre-registered cases once each and the frozen pipeline
mechanically emitted **`ONE MORE LOOK`**.

That verdict rested entirely on two supposed baseline errors in one case:

- `PROPAGATION_REQUIRED` vs frozen golden `REQUIRED`
- `ISOLATION_DEFAULT` vs frozen golden `DEFAULT`

Those are documented alternate spellings of the same values. The baseline was
right; my benchmark had pinned one spelling of a two-spelling value, and the
ENUM comparator — correctly doing exact matching, never similarity — called
it a conflict.

After adjudication of the frozen evidence:

| | |
|---|---|
| genuine baseline material false claims | **0** |
| demonstrated FALSE → TRUE catches | **0** |
| material false claims introduced by Deep Consensus | **0** |
| challenge-set baseline falsehoods | **0 / 12** |
| cases with unresolved noise | **10 / 20** |
| average Deep Consensus turns vs baseline | **3.85 vs 1** |

Decision: **PAUSE.** No Sprint 7, no rerun, no replacement benchmark, no
goalpost movement. Both results are preserved — the mechanical `ONE MORE
LOOK` was never rewritten, because it is the only evidence the pipeline was
followed mechanically rather than steered.

## What I learned

1. **AI evaluation code needs the same adversarial scrutiny as the AI
   system.** In the final sprint the scorer carried nine defects; the engine
   under test carried two.
2. **Agreement between independent models is not external verification.**
   Two models can be confidently wrong together, and the status must not
   imply otherwise.
3. **Typed schemas reduce ambiguity but do not eliminate semantic failure.**
   An exact ENUM match still can't know that two spellings name one value.
4. **Measurement defects can manufacture both success and failure.** One
   sprint produced a false regression, the next a false catch. Opposite
   directions — so not evaluator bias, but an unreliable evaluator.
5. **Negative results are useful when the experiment is allowed to stop.**
   The decision rule was frozen before any answer, and it was obeyed.
6. **A benchmark should prove that known-correct synthetic answers score
   correctly before inference begins.** That one zero-cost control would
   have caught this project's decisive artifact before the freeze.
7. **Natural-language matching inside supposedly deterministic control logic
   is dangerous** — in scorers, guards, routing and identity alike.

## Outcome

The product thesis is unproven and the program is paused. What the work
became is a case study in AI evaluation engineering, model-governance design,
reproducible experimentation, failure analysis, epistemic controls, and
disciplined stopping criteria.

> The harness found its own false positives in both directions, and the
> product stopped.
