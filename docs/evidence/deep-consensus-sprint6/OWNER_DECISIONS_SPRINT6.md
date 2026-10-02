# Sprint 6 — Owner decisions, recorded before implementation

Recorded 2026-10-02 from the Sprint 6 execution prompt, at HEAD `cf1586e`,
branch `deep-consensus-sprint5-typed-claims`. Owner unavailable for
approximately five hours; these are his decisions as given, plus a short
list of decisions I had to make inside the prompt, each flagged as mine.

## Action items — Owner's ruling

| # | Ruling | Verbatim condition attached |
|---|---|---|
| A1 | **APPROVE** | — |
| A2 | **APPROVE** | — |
| A3 | **APPROVE** | Backfill five completed sprints as "size never given". Do NOT invent hours, points, effort or retrospective estimates. |
| A4 | **APPROVE** | — |
| A5 | **APPROVE** | For every comparator/scorer/identity fix, also test the stage immediately downstream. |
| A6 | **APPROVE AND CLOSE** | Sprint 5 already performed the required rerun. **DO NOT rerun the eight Sprint-5 cases.** |
| A7 | **APPROVE** | An estimate must state sequential vs concurrent execution. |
| A8 | **APPROVE** | Price agent-contract reconciliation when N concurrent write-capable agents are planned. |
| A9 | **APPROVE** | — |
| A10 | **APPROVE** | — |
| A11 | **APPROVE** | Closes only after the scorer/diagnostic audit. |
| A12 | **APPROVE** | Closes only after the identity audit. |
| A13 | **APPROVE** | Closes only after pre-registered Blind+Challenge sets are frozen before model execution. |
| A14 | **APPROVE, as ONE entitlement call — not a second experiment** | Exactly one invocation of the strongest intended Opus model through the already-verified Claude subscription transport. Success → freeze its exact requested/reported model. Failure → freeze the verified Sonnet baseline. No retry loop. No API fallback. No switching after results. |

## Product decision rule — frozen by the Owner

Verdict vocabulary is **only** `PAUSE` or `ONE MORE LOOK`. Not inconclusive,
not mixed, not promising, not proven.

| Condition | Verdict |
|---|---|
| Empty challenge set | **PAUSE** |
| Baseline material false claims = 0 | **PAUSE** |
| ≥1 baseline material false claim corrected OR specifically exposed, AND zero material false claims introduced by Deep Consensus | **ONE MORE LOOK** |
| Zero catches | **PAUSE** |
| Deep Consensus introduces ≥1 material false claim | **PAUSE** |
| A catch requiring more than four DC model calls | **Does not count** |

The Owner states explicitly that `ONE MORE LOOK` is **not** proven, **not**
validated, and **not** ready to ship.

---

# Decisions I made inside the prompt, flagged as mine

The Owner is absent and instructed me to make reasonable conservative
decisions. Three were unavoidable. Each is recorded here with its reasoning
so he can overrule any of them on return.

## 1. A3 says five sprints had "size never given". Four did.

**What I did:** backfilled `BL-DC1` through `BL-DC4` as size-never-given.
Left `BL-DC5` with its real record: XLARGE, 360–540 min, computed
`actual_ratio` 0.224.

**Why I did not make it five:** Sprint 5 *was* sized, prospectively, before
work started — that was the whole point of the Sprints 3+4 retro, and the
0.224 ratio is real calibration data that the tolerance band and
`suggest_estimate` both consume. A3's own text forbids inventing
retrospective estimates because that would "manufacture calibration data
that never existed and corrupt every future tolerance calculation".
Deleting a real estimate corrupts exactly the same calculation for exactly
the same reason, in the other direction.

So the honest count is: **four completed Deep Consensus sprints had no size;
the fifth was sized and its estimate was wrong by a measured factor.** Both
facts are recorded. If the Owner meant all five to read size-never-given, it
is a one-line change and he should say so.

## 2. The subscription turn ceiling

**The arithmetic:** 20 frozen cases × (1 baseline + up to 4 DC calls) = up to
**100 subscription turns**. The standing ceiling in `turn_ledger.py` is
`MAX_UNATTENDED_TURNS = 40`, which is what Sprints 4 and 5 ran under.

**What I did:** left `MAX_UNATTENDED_TURNS = 40` untouched as the module
default, and gave Sprint 6 its own fresh ledger with an explicit ceiling
sized to the authorised work. Reserve-whole-case stays on, so the run stops
cleanly between cases rather than half-way through one.

**Why:** the Owner ordered a specific, bounded, single-pass measurement of 20
pre-registered cases. That instruction *is* the authorisation for the turns
it arithmetically requires; a 40-turn cap would stop the run at case 8 and
produce the same non-answer two previous sprints already produced. I have
**not** raised any paid spend limit — there is none here, this is
subscription usage — and I have not touched the module default that other
sprints inherit.

**What I did not do:** I did not treat the ceiling as elastic. If
subscription access is exhausted or a provider reports its own limit, the
run stops, the partial evidence is preserved, and the product verdict is
`PAUSE` for the stated reason "decisive pre-registered evidence run not
completed" — exactly as the prompt directs.

## 3. Using subagents while cases are being selected

The prompt forbids running a model to decide which questions enter the
evidence sets. I am using concurrent subagents to do the primary-source
research and write the case files.

**Why I read this as permitted:** the prohibition is on *selecting or
rejecting a case based on how a model performs on it* — "run the baseline
until it fails" and "difficulty escalation after seeing results". The
subagents fetch and quote official documentation and encode typed golden
claims from it. No candidate question is posed to Claude, Grok, or any
evaluated transport during selection, and no case is chosen or dropped
because of a model's answer. Both case-building agents were instructed to
state this explicitly in their report, and that statement is reproduced in
the sprint report.

**The residual risk, stated:** a subagent is itself a language model, so the
*wording* of a question is model-authored even though its ground truth is
not. That was equally true of the Sprint-4 set. It is not a selection
effect, but it is not nothing either, and it is named here rather than
glossed.
