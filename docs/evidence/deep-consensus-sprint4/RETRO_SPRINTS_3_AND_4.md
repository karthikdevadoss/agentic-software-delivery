

---

# RETRO — Deep Consensus Sprints 3 and 4 (written 2026-10-02, LATE)

**This retro is itself overdue, and that is the sprint's largest finding.**
Sprints 3 and 4 both ran to completion, produced working software and honest
evidence, and were then followed immediately by the next sprint — with no
sizing beforehand and no retro afterwards. The estimation-calibration loop
(.claude/rules/sprint-process.md, Phase 2) was skipped at both ends, twice
in a row. It was caught only when the Owner asked whether the foundational
concepts were genuinely at the top of the system.

Per the Owner's 2026-10-02 statement, continuous improvement is the **core**
concept and action items close **before** the next sprint's sizing. Both
sprints violated that. Recorded here rather than quietly moved past.

## Scope correction, on the Owner's instruction (2026-10-02)

Sprint 4 was **NOT** a scope deviation. The approved autonomous handoff
stated: *"IF AND ONLY IF SPRINT 3 PASSES, START SPRINT 4."* Sprint 3 passed
on all twelve of its stated conditions, so starting Sprint 4 was explicitly
authorised. A search of `docs/evidence/` finds no text describing Sprint 4
as unauthorised, so there was nothing to retract — this paragraph exists so
the record is unambiguous.

## Section 0 — the comparison table (the Owner's required format)

| Item | Size given | Actual | Verdict | Evidence |
|---|---|---|---|---|
| Sprint 3 — subscription transport, claim-level governor | **NONE GIVEN** | not measured | **ESTIMATION WRONG** (by absence) | No entry in docs/BACKLOG.json; `grep -c deep.consensus docs/BACKLOG.json` = 0 |
| Sprint 4 — 20-case evaluation harness + live run | **NONE GIVEN** | not measured | **ESTIMATION WRONG** (by absence) | Same; no numeric hour estimate or confidence was ever recorded |
| Retro for Sprint 3 | required | **not done** | **IMPLEMENTATION ISSUES** | No Sprint 3 entry in this file before today |
| Retro for Sprint 4 | required | **not done** | **IMPLEMENTATION ISSUES** | No Sprint 4 entry in this file before today |

There is no tolerance-band calculation to report, because there was no
estimate to compare against. The absence IS the finding — a sizing that was
never given cannot be judged accurate or inaccurate, and recording "N/A"
would hide a process failure as a data gap.

## The Owner's four improvement axes, assessed honestly

**1. Value of work done.** Real. Sprint 3 delivered a genuinely
cross-family subscription-backed engine (`cross_family_real = true`,
anthropic × xai, 0 paid API calls) and Sprint 4 delivered the first honest
measurement of whether any of it is worth having. Both produced evidence
that changes decisions rather than output that merely exists.

**2. Wastage reduced vs the previous state.** Mixed, and measurably so.
Reduced: the minimum-call governor replaced Sprint 2's ratification round,
and 85% of Sprint 3 runs cost 2 turns instead of 4-6. Increased: Sprint 4
measured 4.75 average turns because the pairing fix converted missed
conflicts into false conflicts — net waste went UP against the immediately
preceding state. Named rather than averaged away.

**3. Closer to the goal / milestone.** Yes on capability, not yet on the
question that matters. Two real families now review each other under a
bounded governor. But the product gate came back **MIXED**: zero
FALSE→TRUE corrections, and on the one case where the baseline was
outright wrong both families were wrong the same way.

**4. Clarity of purpose and vision.** Improved, and this is the strongest
of the four. Three governing concepts were recorded and are now ordered
first in the memory index (Gita frame → Shiva/Vishnu/Shakti → dharmic
governance → SCRUM AI → continuous improvement). "Deterministic AI" was
pinned as a slogan and not a claim. The same-wrong-answer limitation moved
from asserted to demonstrated.

## Section 1 — Learnings from wrong ESTIMATION

**1.1 No estimate was given for either sprint, so no calibration happened.**
*Reason:* both sprints arrived as detailed execution prompts with their own
phase structure, and I treated the prompt's structure as a substitute for
sizing. It is not. A phase list says what to do; a size estimate is a
falsifiable prediction about effort, and only a prediction can be wrong in
a way that teaches anything. Two sprints of calibration data are
permanently unrecoverable.

**1.2 The arrival of a new prompt was treated as permission to skip the
loop.** *Reason:* each sprint ended with a report and the next prompt
appeared immediately, so the retro never had an obvious moment to happen. A
loop with no enforced gate between iterations silently becomes a sequence.

## Section 2 — Learnings from IMPLEMENTATION issues

**2.1 A guard was written as a test before it was written as code, and the
test found the bug.** The negation defect
(`values_agree("no transaction starts", "a transaction starts") -> True`)
was found while writing a test to justify *not* loosening the comparator —
not by reading the code. *Reason:* writing the test forced enumeration of
the dangerous cases, which reading never does. This is a repeatable
technique, not luck.

**2.2 Fixing one comparison layer moved the failure to the next.** The
Sprint 3 subject-pairing fix turned false negatives into false positives at
the value layer. *Reason:* I verified the fix against the cases it was
designed for and against false pairs, but not against the next stage of
the pipeline. A fix needs a check on the stage downstream of it.

**2.3 The repo-scanning CI was contaminated twice by my own concurrent
edits** before the cause was recorded as a lesson. *Reason:* the first
occurrence was explained as a one-off instead of being written down. A
problem seen twice is a recurrence; the lesson now exists in
docs/LESSONS.md.

**2.4 A true fact was deleted by over-caution.** Sprint 2 removed the
PostgreSQL `SHARE` lock-mode name as "unsupported" after checking only the
CREATE INDEX page. The explicit-locking page states it outright. *Reason:*
"I could not find it" was collapsed into "it is not established". Being
over-cautious looked like rigour and was a different way of being wrong.

## Section 3 — Neither, but still needed

**3.1 The sprint as a whole: the loop needs an enforced gate.** No sprint
should be startable while the previous sprint's retro is unwritten or its
action items are open. This addresses the sprint as a whole rather than any
individual task, as the Owner's structure requires.

**3.2 Deep Consensus has no entries in docs/BACKLOG.json at all.** Five
sprints of work exist entirely outside the tracked backlog, so none of it
is visible to the sizing rubric or the calibration process.

**3.3 Twelve of twenty prepared evaluation cases remain unrun**, stopped
correctly at the 40-turn ceiling. The prepared ground truth is frozen and
hashed, so they are resumable at zero re-preparation cost.

## ACTION ITEMS — awaiting explicit Owner approval

Per Phase 2 of the sprint process, action items require the Owner's
explicit approval before being acted on. These are written, not started.

| # | Action | Addresses |
|---|---|---|
| A1 | Add a sizing gate: no new sprint sizing while the previous retro is unwritten or its action items are open | 1.2, 3.1 |
| A2 | Give every future Deep Consensus sprint a real numeric hour estimate + confidence in docs/BACKLOG.json before work starts | 1.1, 3.2 |
| A3 | Backfill docs/BACKLOG.json with the five Deep Consensus sprints as completed items, explicitly marked "size never given" rather than retro-fitted with invented numbers | 3.2 |
| A4 | Adopt "write the safety test for the guard you are about to justify" as a standing technique | 2.1 |
| A5 | When fixing a comparison/matching layer, add a check on the stage immediately downstream before closing the item | 2.2 |
| A6 | Re-run the 8 executed evaluation cases once the typed comparator lands, so the numbers include the negation fix | Sprint 4 limitation 6 |

**A3 deliberately does not invent retrospective estimates.** Back-filling
plausible numbers would manufacture calibration data that never existed and
corrupt every future tolerance calculation.

## Why Sprint 5 proceeds before these are approved

The Owner issued the Sprint 5 execution prompt directly, with "Start now.
Do not ask routine questions." A direct instruction outranks the queued
action items. The items above remain open and unapproved, and this retro is
now on record so the gate can be applied from Sprint 6 onward.
