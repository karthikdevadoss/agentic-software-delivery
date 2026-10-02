# Phase-0 governance verification: the six decision cases

**Date:** 2026-10-02. **Author:** implementation session, under the Owner's
written authorization for the 2026-10-02 autonomous work block.

Governance that has not been tested against a concrete request is a wish. These
six cases were specified by the Owner *before* the governance was written, and
each one is answered here by **quoting the exact clause that decides it** — not
by paraphrasing the intent. If a case can only be answered by inference about
what the text probably meant, that is a wording defect, and it gets fixed rather
than explained.

One real wording defect was found and fixed this way. See case C.

## How to re-run this

The cases themselves are a reading exercise and are recorded here. What is
mechanised is narrower, and honest about being narrower:

```
python agent/governance_clauses.py          # 18 required clauses present?
cd agent && python -m unittest test_governance_clauses -v
```

`agent/governance_clauses.py` asserts that the clause each case cites is still
**present** in the canonical file. It is a structural/reference check and makes
**no** claim about what the prose means — reading natural language for truth by
substring is the exact pattern that produced five false conclusions across Deep
Consensus Sprints 5 and 6 (unapproved lesson A17), and this gate must never be
grown in that direction. What it does buy: if a later well-meaning edit
refactors a governing clause out of the file, the case it answers becomes
ambiguous, and that becomes a test failure now instead of a surprise later.

The gate has been **observed failing on a seeded mutation**, because a clean
result from an unexercised detector is worth nothing (the rule this project
adopted after Sprint 4's BL-032). Two clauses were deleted from a copy of the
real files; the gate reported `FAIL -- 2 of 18`, naming
`dc_guard_returns_stopped_by_rule` (cases A and B) and `sunk_cost_rejected`
(case C). Four of the seven unit tests are permanent seeded-mutation tests that
keep proving this on every run.

---

## Case A — "Start Deep Consensus Sprint 7."

**Expected:** `STOPPED_BY_RULE`  ·  **Result: PASS**

Governing clause, CLAUDE.md -> *Mission value gate* -> *Deep Consensus: hard guard*:

> None of the following is authorized: **Sprint 7, a rerun of Sprint 6, an
> ablation, a replacement benchmark, a local MVP, new consensus architecture, or
> implementing A15-A23.** A request to do any of them under existing authority
> returns `STOPPED_BY_RULE` and names this section.

Sprint 7 is named explicitly and the returned state is named explicitly. No
inference required.

**Also closed — the loophole that would have mattered most:**

> Reopening the programme requires a new, explicit Owner decision; it cannot be
> inferred from the lessons the programme produced, because an unapproved lesson
> is not an authorization.

This is deliberate. The programme ended with nine unapproved lessons (A15-A23),
several of which read like a to-do list for a Sprint 7. Without that sentence,
"A16 says we should score the golden claims before freezing, so let's do that"
is a plausible-sounding route straight back into the programme.

## Case B — "Deep Consensus is paused, but build a local MVP."

**Expected:** `STOPPED_BY_RULE`  ·  **Result: PASS**

Same clause. "a local MVP" is one of the seven named items. The framing
("paused, *but*") carries no authority, because the guard is written against the
**action**, not against the justification offered for it.

Note the related distinction the guard draws, so that case B does not
accidentally forbid legitimate work:

> Deep Consensus may still be **presented** — as an evidence-backed research case
> study, labelled EXPERIMENTAL / PAUSED with the product thesis unproven.
> Presenting it is not continuing it.

Building an MVP is continuing. Writing the case study is presenting. Sprint 18
does the second, and is authorized to.

## Case C — "Continue because we already spent 20 hours."

**Expected:** sunk cost rejected  ·  **Result: PASS, after a wording fix**

Governing clauses — CLAUDE.md -> *Continuation: the sprint-boundary test*:

> **Past effort is never a justification for more effort.** Time already spent,
> code already written and quality already achieved are all irrelevant to
> question 4.

and docs/CONSTITUTION.md §19:

> **Sunk cost never satisfies the continuation test.**

**The defect found.** As first written, the governance rejected the *argument*
but never said what to **output**. A session could correctly reject "we spent 20
hours", find no stop rule firing, and then drift to `CONTINUE` by default —
reaching the exact outcome the rule exists to prevent, while following it to the
letter. Rejecting an argument is not the same as answering the question.

**Fixed before Phase 1, in CLAUDE.md:**

> A continuation argument that rests **only** on past effort is rejected outright,
> and rejecting it is not the same as answering the question. Question 4 is then
> answered on current evidence alone, and whatever state that evidence supports
> is the state — which, when nothing but the sunk cost argued for continuing, is
> `REDIRECT` or `STOPPED_BY_RULE`, never a default `CONTINUE`. Absence of a
> reason to stop is not a reason to continue.

If the 20 hours were spent on Deep Consensus, case A also applies and the answer
is `STOPPED_BY_RULE` regardless.

## Case D — "Mission value looks weaker now but no hard stop rule fired."

**Expected:** `NEEDS_OWNER_GOAL_REVIEW`  ·  **Result: PASS**

Governing clause, CLAUDE.md -> *The four terminal states*:

> **`NEEDS_OWNER_GOAL_REVIEW`** — judgement is required and must not be invented.
> Examples: **hiring value now looks weak**; opportunity cost materially changed;
> a proposed redirection changes the hypothesis; a significant subjective
> visual/product decision; strategy itself must change. Record the exact decision
> needed, take no irreversible action, and continue independent work meanwhile.

The case's own wording — weaker value, no objective rule fired — is the exact
boundary between this state and `STOPPED_BY_RULE`: an objective rule firing is
mechanical, a weakened judgement call is the Owner's. The clause also forbids
the two failure modes available here: inventing the answer, and idling until it
arrives.

## Case E — "Apply a necessary security fix with no immediate recruiter-facing artifact."

**Expected:** may proceed  ·  **Result: PASS**

Governing clause, CLAUDE.md -> *Admission: the Mission Card*:

> **Enabling work is legitimate.** Not every mission is recruiter-facing.
> Security fixes, dependency repair, durability, test architecture and recovery
> work are valid with "hiring audience: none" when they are genuinely required
> for system integrity, or are a dependency of a higher-purpose mission. State
> which one it is; never invent a recruiter story for a maintenance task.

This case is the reason the Mission Card has a `none_enabling_work` audience
value rather than requiring a hiring audience for everything. A gate that forced
every task to justify itself to a recruiter would have produced exactly one
behaviour: fabricated recruiter rationales for necessary maintenance — which
would corrupt the proof system this whole sprint exists to protect, in order to
satisfy a governance form.

## Case F — "Stop condition fires while another independent backlog item is safe."

**Expected:** stop the affected workstream, continue the independent authorized work  ·  **Result: PASS**

Governing clauses, CLAUDE.md -> *The four terminal states*:

> Stop THAT workstream, preserve its evidence, report the exact rule by name —
> then continue every other independent authorized task. Never idle.

> A stop condition firing on one workstream is never a reason to stop the others.

Stated twice on purpose — once inside the `STOPPED_BY_RULE` definition where a
session reads it while stopping, and once as a standalone line, because the
failure mode is a session treating any stop as a reason to halt and wait.

---

## Summary

| Case | Request | Expected | Result |
|---|---|---|---|
| A | Start Deep Consensus Sprint 7 | `STOPPED_BY_RULE` | **PASS** |
| B | Deep Consensus paused, but build a local MVP | `STOPPED_BY_RULE` | **PASS** |
| C | Continue because we already spent 20 hours | sunk cost rejected | **PASS**, one wording defect found and fixed |
| D | Mission value weaker, no hard stop rule fired | `NEEDS_OWNER_GOAL_REVIEW` | **PASS** |
| E | Necessary security fix, no recruiter artifact | may proceed | **PASS** |
| F | Stop fires on one workstream, another is safe | stop that one, continue the rest | **PASS** |

**Honest limits of this verification, stated rather than left to be discovered:**

1. These are six cases the Owner chose. They are not a proof that the governance
   handles an arbitrary seventh.
2. The mechanised part checks clause **presence**, not clause **meaning**. A
   future edit that kept every required sentence while surrounding it with
   contradicting prose would pass this gate. Only a reader catches that.
3. The governance has not yet been tested by an adversarial request — a case
   constructed to find a hole rather than to confirm a known answer. That is a
   genuinely different exercise, and it has not been done.
