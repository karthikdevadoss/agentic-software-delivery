# Architecture V2 — Benchmark / Evaluation Plan

Companion to docs/ARCHITECTURE_V2.md (design) and
docs/ARCHITECTURE_V2_KNOWLEDGE_MAP.md (inventory). Defines how we will
know — with evidence, not assumption — whether the V2 architecture
(implementer + independent QA evaluator + Skills) is actually better than
the current baseline before any public cutover. Per docs/CONSTITUTION.md
§4/§9: no winner may be declared before data exists, and both success and
failure must be seen clearly.

**Status of this document: PLAN, NOT YET EXECUTED.** No V2 sample runs
have been collected as of this writing. This is deliberate — see
docs/ARCHITECTURE_V2.md §14, "no production cutover in this task."

## Baseline (A) vs. V2 (B)

**A — current baseline (`trainer-preview-v1-stable` tag, commit
`b64d535`):** the single implementer agent (`agent/agent_loop.py` +
`agent/execution_tools.py`, orchestrated by `agent/web_server.py`'s
`_run_trainer_thread`) proposes, applies, builds, and — via the
deterministic gates already in that same code path — self-certifies
against `_decide_deployment_outcome`/`_tests_applicable`. No
independent evaluator exists yet; the implementer's own tool calls are
the only evidence trail.

**B — V2 candidate:** the same deterministic gates and tool surface,
but a second, independent `qa-evaluator` subagent (docs/ARCHITECTURE_V2.md
§7) evaluates the Acceptance Contract (§5) against real evidence *before*
a run is allowed to report COMPLETED, without sharing the implementer's
reasoning context.

## Data sources

1. **Existing historical real runs** — already in the event ledger
   (`delivery_events`, `source IN ('workbench_trainer','workbench')`) and
   in `agent/web_run_history.jsonl`. These are 100% baseline (A) data;
   they predate any evaluator and cannot be relabeled as B. Use them to
   establish A's current real-world numbers (see "Known baseline
   numbers" below) — not to fabricate a B result.
2. **A small controlled future sample** — once the `qa-evaluator` exists
   and is wired into a non-public trial path (never the live public
   Workbench in this task), run the **same set of real requirements**
   through both A and B and record every metric below for each. Sample
   size: start with the smallest number that produces a directionally
   readable signal (a handful of real runs per arm, e.g. 5–10) rather
   than committing to a large study up front — this is a foundation
   task, not the study itself.

## Metrics (collected identically for A and B)

| Metric | Definition | Source |
|---|---|---|
| Verified completion rate | % of runs reaching COMPLETED with real requested-effect verification (not just HTTP 200) | `deployment_completed`/`run_completed` events + independent re-fetch |
| First-pass success | % of runs that reach a correct terminal state without any human correction or re-run | run history + human-intervention events |
| Escaped-defect rate | # of defects a trainer/creator finds AFTER a run reported COMPLETED, per N runs | docs/LESSONS.md entries cross-referenced to run_id |
| False-success rate | % of COMPLETED runs where the requested observable effect was later found absent | manual/evaluator re-check vs. reported outcome |
| Rework/retries | # of re-runs needed to reach a correct terminal state for the same requirement | run_id lineage (same requirement text, multiple run_ids) |
| Human approvals | # of times a human had to intervene/approve/correct | `authorization_decision` events where `decided_by` is human, not policy |
| Human wait time | Wall-clock time a human was blocked waiting on the system | timestamp deltas around human-intervention events |
| Human intervention count | Total distinct human actions needed per verified change | same as above, counted |
| Wall-clock time | Real run duration, `run_started` → terminal event | event ledger timestamps (server-side, consistent within one domain — see docs/LESSONS.md's client/server clock-mixing lesson; never mix with a UI-side clock) |
| Token usage | Real `input_tokens`/`output_tokens`/cache fields | `run_usage_summary` events (already captured, never estimated post-run) |
| USD cost | Real calculated cost from the versioned pricing table | `run_usage_summary.cost_usd` |
| Tool-call count | Real count of tool invocations | `run_usage_summary.tool_call_count` |
| Production verification quality | Was the requested effect actually checked (content match) vs. only HTTP 200 | `deployment.content_verified` field (added this session's stabilization work) |
| Cost per VERIFIED software change | USD cost ÷ count of runs with a real, independently-confirmed effect | derived from the above |

## Known baseline (A) numbers so far (real, not simulated)

From this session's real acceptance runs (all baseline/A, pre-evaluator):

- `trainer-4733d1c0` (Create → Create Customer): COMPLETED, verified,
  6 API calls, 37,340 input + 2,821 output tokens, $0.10289, 111.1s
  elapsed, 1 real production-wait cycle (80s) before content verified.
- `trainer-7769757e` (footer → DEVADOSS): reported COMPLETED but was a
  **false success** at the time (content not yet live) — later fixed at
  the verification-logic level, and the underlying deploy did complete
  on its own. Counts as 1 false-success escape in A's history, already
  root-caused in docs/LESSONS.md.
- `trainer-6aedf022` (footer → DEVADOSS attempt): FAILED at COMMITTING
  (`fatal: not a git repository`) — a genuine escaped infra defect, not
  a false success. Counts as 1 escaped-defect in A's history.

These three data points alone are not a statistically meaningful sample —
they are recorded here as the honest starting point, not as "baseline
performance." Do not compute a rate from n=3.

## What would justify a cutover

A cutover to V2 for the public Workbench requires, at minimum:
- Verified completion rate for B ≥ A on the same requirement set.
- False-success rate for B measurably lower than A (this is the
  evaluator's core value proposition — it exists specifically to catch
  what the implementer cannot see about itself).
- Cost per verified change for B not disproportionately higher than A
  (an evaluator that doubles cost for a marginal quality gain is not
  automatically worth it — see docs/CONSTITUTION.md §7, waste avoidance).
- No new class of defect introduced by the evaluator itself (e.g., the
  evaluator incorrectly failing a genuinely good change).

None of these have been measured yet. This document exists so that once
the `qa-evaluator` and Skills exist, the comparison is designed *before*
the data arrives — preventing the failure mode of picking metrics that
flatter whichever result shows up first.

## Review cadence

Re-open this plan whenever: a new Claude model materially changes
single-agent self-verification reliability (which could reduce the
evaluator's marginal value — see docs/ARCHITECTURE_V2.md §11's
"no architecture is sacred" review rule), or after the first controlled
B sample exists (update this document with real numbers, not a rewrite
of the plan).
