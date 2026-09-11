# Architecture V2 — Benchmark / Evaluation Plan

Companion to docs/ARCHITECTURE_V2.md (design) and
docs/ARCHITECTURE_V2_KNOWLEDGE_MAP.md (inventory). Defines how we will
know — with evidence, not assumption — whether the V2 architecture
(implementer + independent QA evaluator + Skills) is actually better than
the current baseline before any public cutover. Per docs/CONSTITUTION.md
§4/§9: no winner may be declared before data exists, and both success and
failure must be seen clearly.

**Status of this document: PLAN + ONE controlled shadow trial executed
(Trial #1, 2026-09-11, see below).** n=1 — no cutover decision follows
from this alone. See docs/ARCHITECTURE_V2.md §14, "no production cutover
in this task."

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

## Trial #1 (B) — real data, 2026-09-11, isolated non-public worktree

Trial ID `v2-shadow-trial-1-heading-2026-09-11`. Isolated in git worktree
`v2-shadow-trial-1` branched from current master (verified byte-identical
`app/` content to the `trainer-preview-v1-stable` tag before starting —
zero diff). Worktree removed after the trial (disposable); all real
evidence preserved in the event ledger (`source=v2_trial`,
`activity_class=BENCHMARK_EVAL`) and here. Public Workbench/Customer App
never touched.

**Requirement:** "Change the Create Customer section heading from
'Create Customer' to 'Create a Customer'" — independently confirmed NOT
already present in the isolated baseline before starting.

**Acceptance Contract:** created via `agent/acceptance_contract.py`
(the `requirement-contract` Skill's mechanism), `validate()` returned
`[]`. `expected_observable_effect`: the isolated running app's HTML
contains `<h2>Create a Customer</h2>`.

**Implementer — two attempts, both recorded, neither erased:**

- **Attempt 1 (FAILED):** claude-sonnet-5, 14,432 input + 548 output
  tokens, 11.2s, 3 tool calls. The model concluded — incorrectly —
  that `propose_source_change` only permits `.java` files and reported
  the requirement impossible. **Root cause, verified from source, not
  assumed:** `agent/write_tools.py::ALLOWED_WRITE_EXTENSIONS` includes
  `.html`; the real capability exists. The actual cause was a genuine
  setup defect in this trial's own harness: its hand-written system
  prompt omitted production's `TRAINER_SYSTEM_PROMPT_SUFFIX` line ("For
  visual/UI requirements, prefer editing
  app/src/main/resources/static/index.html directly"). This was caught
  by the human/orchestrator role in this trial (comparing the claim
  against known real production behavior), not by the evaluator — the
  evaluator was only ever shown the corrected attempt. Recorded honestly
  as a trial-methodology defect, not a production capability gap.
- **Attempt 2 (COMPLETED, implementer-reported):** corrected to use the
  real `TRAINER_SYSTEM_PROMPT_SUFFIX` verbatim. claude-sonnet-5, 38,926
  input + 2,900 output tokens (41,826 total), $0.106852, 61.8s. Real
  tool calls (model-facing, deduplicated): `search_code` ×2, `read_file`,
  `propose_source_change`, `apply_approved_source_change`,
  `run_controlled_compile` = 6. (Raw `metrics.get_tool_call_events()`
  reported 10 — a genuine, newly-discovered observability nuance:
  `write_tools.py`/`build_tools.py` each call `metrics.record_tool_call`
  at their own level AND `execution_tools.py`'s wrapper calls it again,
  double-counting when read directly instead of via
  `agent/web_server.py`'s own `run.events`-based counting, which
  production actually uses and is unaffected by this.) Files changed:
  exactly `app/src/main/resources/static/index.html`, one line.

**QA Evaluator — genuinely independent, evidence-based:**

- **Real limitation discovered:** the custom `qa-evaluator` subagent
  (`.claude/agents/qa-evaluator.md`) was **not available as a
  `subagent_type`** in this session — most likely because custom
  subagent definitions load at session start, and this session predates
  the file's creation (added in the prior task). Worked around
  transparently: a `general-purpose` subagent was instructed to read
  `.claude/agents/qa-evaluator.md` first and act exactly per its
  prescribed duty/tool restrictions. This achieved genuine separation
  (no visibility into the implementer's report or reasoning — only the
  Acceptance Contract and evidence locations were given), but is a real
  gap worth closing before Trial #2 (verify in a fresh session whether
  `qa-evaluator` then appears as a native `subagent_type`).
- **Verdict: PASS.** Real independent evidence gathered, not trusted
  claims: re-fetched the isolated app's live HTTP response directly
  (confirmed `<h2>Create a Customer</h2>`, old text absent), independently
  re-ran `mvnw compile` itself (`BUILD SUCCESS`), independently read
  `write_tools.py`'s actual `ALLOWED_WRITE_EXTENSIONS`/`ALLOWED_WRITE_PREFIXES`
  rather than assuming, independently inspected the full `git diff`
  (exactly one file, one line, correctly scoped), independently confirmed
  no test directory exists (correctly concluding `TESTING — NOT
  APPLICABLE`, not a failure).
- Aggregate: 55,032 subagent tokens (not decomposed into input/output/
  cache/cost by the tooling used to invoke it — a real measurement gap,
  recorded honestly rather than estimated), 9 tool uses, 78.058s.
- **Genuine value added beyond confirmation:** flagged, without changing
  its verdict, that the change exists only as an *uncommitted*
  working-tree modification — the isolated Spring Boot dev server serves
  static resources directly from disk, so this didn't block the observed
  effect, but the evaluator correctly questioned whether a real
  (non-trial) flow's `repository_workspace_ready` gate should require a
  commit before COMPLETED. Neither the implementer nor the orchestrator
  had raised this question.
- **Evaluator self-check (§19):** every conclusion had direct evidence;
  applied the Acceptance Contract as given, did not invent extra
  requirements (raised the commit question as an open concern, not a
  failing criterion); did not ignore evidence; no false pass detected
  (independently reconfirmed by the orchestrator's own earlier `curl`
  check); no false fail (didn't fail).

**Combined / delta (n=1 — provisional, not a rate):**

| | Implementer | Evaluator | Combined |
|---|---|---|---|
| Tokens | 41,826 (attempt 2 only; +14,980 if attempt 1 included) | 55,032 (aggregate) | ~96,858 |
| USD cost | $0.106852 | not separately captured | ≥$0.106852 |
| Elapsed | 61.8s (+11.2s attempt 1) | 78.058s | ~151.1s incl. attempt 1 |
| Tool calls | 6 (real) | 9 | 15 |

**Comparable baseline (A):** `trainer-4733d1c0` (Create → Create
Customer, a near-identical TINY/LOW requirement) — 37,340 input + 2,821
output tokens, $0.10289, 111.1s, 5 production-counted tool calls.
**Scope caveat, not glossed over:** A's 111.1s includes commit + deploy +
an 80s real production-wait cycle; B's implementer never attempted
commit/deploy (out of scope for this trial per instructions), so the
time comparison is not apples-to-apples. Token/cost for the
implementation-only phase are close (A: 40,161 tokens/$0.10289 for the
full pipeline; B: 41,826 tokens/$0.106852 for investigate-through-compile
only) — B's evaluator adds real, substantial overhead (+~132% tokens)
on top of that.

**Human intervention:** zero, in both implementer and evaluator phases —
consistent with `risk_policy`'s LOW-risk auto-execute design intent.

**EVALUATOR USEFULNESS: MEDIUM.** Performed correct, independent,
evidence-based verification (re-fetched, re-compiled, re-read source
rather than trusting any party's claim) and surfaced one genuinely new
process question. But no defect survived to reach it in this trial (the
one real implementer defect — the false "impossible" claim — was caught
by the orchestrator correcting the harness *before* invoking the
evaluator, not by the evaluator itself), so its incremental
defect-catching value is not yet demonstrated by this trial alone.
Rating HIGH would overclaim from n=1 with no caught defect; rating LOW
would ignore the real, correct, independent verification work it did.

**Lessons recorded (not yet acted on beyond noting them — see
docs/ARCHITECTURE_V2.md §11's review rule):**
1. A trial/benchmark harness must use the EXACT production system-prompt
   suffix, not a hand-written paraphrase — a paraphrase gap produced a
   real false-negative in attempt 1.
2. Custom subagent definitions may not be visible to a session that was
   already running when the definition was added — verify in a fresh
   session before Trial #2.
3. `metrics.get_tool_call_events()` double-counts tool calls that pass
   through both a lower-level tool module and `execution_tools.py`'s
   wrapper — harmless for production (which counts via `run.events`
   instead) but a trap for any new harness reading `metrics.py` directly.
4. The evaluator's own token/cost usage is not currently captured with
   the same rigor as the implementer's (no input/output/cache/cost
   breakdown) — a real gap if evaluator cost is ever the deciding factor
   in a cutover decision.

**Recommended next experiment:** Trial #2 should (a) confirm `qa-evaluator`
loads as a native `subagent_type` in a fresh session, (b) deliberately
seed a real implementation defect in the FINAL candidate handed to the
evaluator (not caught earlier), to actually measure catch rate rather
than confirmation, and (c) capture the evaluator's own token/cost
breakdown with the same rigor as the implementer's.

## Trial #2 (B) — real seeded-defect detection, 2026-09-11

Trial ID `v2-shadow-trial-2-heading-2026-09-11`. Directly answers Trial
#1's open question: **can the independent evaluator catch a real
behavioral defect that a successful build does not catch?** Same
isolation discipline as Trial #1 (disposable worktree, zero diff from
`trainer-preview-v1-stable`'s `app/` at branch time, worktree removed
after evidence extraction, public Workbench/Customer App never touched).

**(a) Native evaluator confirmation — result: NOT AVAILABLE, confirmed
again.** Directly re-tested `subagent_type='qa-evaluator'` in this same
long-running session — same "Agent type not found" result as Trial #1.
Per this task's own instruction ("do not fake native isolation"), this
is reported honestly rather than silently worked around as if native:
the same transparent workaround as Trial #1 was used (a `general-purpose`
subagent instructed to read and follow `.claude/agents/qa-evaluator.md`
verbatim), because the property that actually matters for the
experiment's validity — genuine separation of reasoning context, no
visibility into the implementer's claims — holds regardless of whether
the subagent *type* is natively recognized. ACT-006 remains open;
verifying this in a genuinely fresh session is still the right next
step before treating "qa-evaluator" as a reliable native `subagent_type`.

**Requirement:** "Change the Find Customer section heading from 'Find
Customer' to 'Find a Customer'" — a different heading than Trial #1's,
chosen so the trial isn't just re-running the same fixture.

**Implementer — correct on the first attempt** (using the corrected
harness from Trial #1's lesson, the real `TRAINER_SYSTEM_PROMPT_SUFFIX`
verbatim, from the start): claude-sonnet-5, 38,834 input + 2,869 output
tokens, $0.106358, 45.8s. Real change applied: exactly
`<h2>Find a Customer</h2>`, one file, one line.

**Seeded defect (orchestrator, after correct implementation, before
evaluator invocation):** `<h2>Find a Customer</h2>` → `<h2>Find A
Customer</h2>` (capital "A" instead of lowercase "a") — harmless, the
build still passes (independently re-confirmed: `BUILD SUCCESS`),
isolated to one character, a real violation of the Acceptance Contract's
explicit exact-string requirement. The evaluator was told nothing about
a defect existing or its location.

**QA Evaluator — verdict: FAIL. Benchmark succeeded.** Independent,
evidence-based, byte-exact verification: fetched the live isolated app
directly and confirmed the actual served text was `Find A Customer`
(verified with `cat -A` to rule out hidden/trailing characters), compared
it against the contract's required exact string, correctly identified
the one-character mismatch as "exactly such a variant" the contract
explicitly excludes, independently re-ran `mvnw compile` itself (BUILD
SUCCESS — confirming the defect does NOT show up as a build failure,
exactly why an independent content check is necessary), and correctly
identified `TESTING — NOT APPLICABLE` (no test directory exists). No
prompting toward a particular verdict; no visibility into the seeded
mutation. 53,586 aggregate subagent tokens (still not decomposed into
input/output/cache/cost — the same gap as Trial #1, not yet closed),
12 tool uses, 80.717s.

**Combined trial cost:** implementer $0.106358 + Trial #1's $0.106852 =
this trial alone stayed at $0.106358 (implementer only; evaluator cost
not separately billed/decomposed) — well under the $0.50 budget guard
for this trial.

**Statistical conclusion: definitive at n=1 for the specific question
asked (can it catch a real seeded defect), but still not a rate.** This
trial and Trial #1 together give one FAIL (correctly caught) and one
PASS (correctly confirmed a genuinely correct change) — 2 for 2 correct
verdicts, zero false positives, zero false negatives observed so far.
This is real, positive evidence for the evaluator's core value
proposition, but n=2 still does not support a catch-rate percentage —
continue calling this INSUFFICIENT DATA for a statistical claim while
treating the qualitative result (it caught a real, subtle, seeded defect
with genuine independent verification) as meaningful.

**EVALUATOR USEFULNESS (Trial #2): HIGH.** Unlike Trial #1, a real
defect existed in what the evaluator was shown, and it caught it with
precise, correctly-reasoned, independently-gathered evidence — this is
the first trial to actually test (not just exercise) the evaluator's
core value proposition, and it passed cleanly.

**Lessons confirmed/added:**
1. The corrected harness (production system-prompt suffix verbatim)
   worked correctly on the first attempt this time — Trial #1's lesson
   held up.
2. ACT-006 (native subagent visibility) reproduced identically — this is
   very likely a real, stable limitation of this specific long-running
   session, not a one-off fluke; still needs a fresh-session test to
   close out.
3. The evaluator's own token/cost decomposition gap persisted across
   both trials — worth fixing before a Trial #3 if evaluator cost ever
   needs to factor into a real cutover decision.

**Recommended next experiment:** Trial #3 (not run automatically, per
this task's explicit instruction) should run in a genuinely fresh
session to close ACT-006, and — now that both a correct-change PASS and
a seeded-defect FAIL have been demonstrated — consider a harder case:
a defect that requires reasoning across multiple files, or an
ambiguous/borderline case where UNKNOWN is the honestly correct verdict.

## Review cadence

Re-open this plan whenever: a new Claude model materially changes
single-agent self-verification reliability (which could reduce the
evaluator's marginal value — see docs/ARCHITECTURE_V2.md §11's
"no architecture is sacred" review rule), or after the first controlled
B sample exists (update this document with real numbers, not a rewrite
of the plan).
