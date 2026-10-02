# Deep Consensus — Sprint 2 results

Branch `deep-consensus-sprint2`. Not pushed, not deployed, no tunnel, no
ChatGPT connection.

Sprint 2 was a **small capped API / cross-family engineering proof**, not the
future operating model. Subscription-backed transport is deferred by the
approval itself.

---

## 1. Spend — the whole sprint, including pre-halt calls

| | |
|---|---|
| Real provider calls | **16 / 30** |
| Known provider spend | **$0.113326 / $2.00** |
| Calls with UNKNOWN cost | 0 |
| Remaining | 14 calls, $1.8867 |

Breakdown:

| Phase | Calls | Known spend |
|---|---|---|
| Sprint 1 (before Phase 0; seeded into the ledger because the Sprint 2 ceilings explicitly include them) | 8 | $0.052790 |
| Sprint 2 parallel-vs-sequential measurement | 8 | $0.060536 |

Every figure is computed from real provider-reported token counts against a
published rate verified on 2026-10-01. Nothing is estimated. Rates used:

| Provider | Model | Input | Output | Source | Accessed |
|---|---|---|---|---|---|
| anthropic | `claude-sonnet-5` | $2.00 / MTok | $10.00 / MTok | <https://claude.com/pricing> | 2026-10-01 |
| anthropic | `claude-haiku-4-5-20251001` | $1.00 / MTok | $5.00 / MTok | <https://claude.com/pricing> | 2026-10-01 |

Both recorded as new dated entries in `agent/pricing_config.py`, per that
file's own append-never-edit convention, so historical runs still recalculate
at the rates that actually applied to them.

---

## 2. Second provider family — BLOCKED_REAL_PROVIDER_CREDENTIAL

Slot-B priority is implemented exactly as locked: **Gemini, then OpenAI, then
a labelled mock.** Re-verified at Phase 0 and again at the end:

| Family | Credential | SDK | Selectable |
|---|---|---|---|
| Gemini | `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_GENAI_API_KEY` all **absent** | `google.genai`, `google.generativeai` **not installed** | no |
| OpenAI | `OPENAI_API_KEY` **absent** | `openai` **not installed** | no |

So **`BLOCKED_REAL_PROVIDER_CREDENTIAL` = YES** and slot B is a labelled
mock. **No cross-family real run happened, and nothing in this sprint is
reported as one.**

`cross_family_real` is computed by one function, `providers.is_cross_family`,
which returns true only when both slots are real and from different real
families. Tested in four directions: mock+mock false, real+mock false,
**two Anthropic models false** (the Sprint 1 situation — REAL+REAL but one
family), and a genuinely different real pair true, so the predicate is not
vacuously false.

**No Gemini or OpenAI adapter was written.** A credential alone does not make
a family selectable here: its SDK must be importable, because writing
`generate()` against an SDK that is not installed means coding to an API
surface that cannot be inspected or exercised — which this project forbids
outright. The selection logic is implemented and tested with an injected env
and SDK probe; the adapter is a small bounded addition the moment a real
credential and SDK exist.

---

## 3. Parallel execution — real measurement

Same question, same two models, same budget (4 calls, 1 review round), one
arm forced sequential and one parallel.

| | |
|---|---|
| **Sequential baseline** | **40,053.9 ms** |
| **Parallel** | **22,470.3 ms** |
| **Observed ratio** | **1.783** |
| N per arm | 1 |

`docs/evidence/deep-consensus-sprint2/parallel-speedup-measurement.json`

**N=1 per arm.** Enough to show the two stages were genuinely parallelised;
not enough to publish a speedup number as a property of the system, and the
artefact says so in its own `generalisation_warning` field.

**Label that matters:** both slots were Anthropic, because no second family
exists here. This measures **timing on a real same-family pair**. It is not a
cross-family run.

### Round 2 reachability — the finding

| | |
|---|---|
| Second-round elapsed ceiling | 25.0 s — `governor.SECOND_ROUND_ELAPSED_CEILING_SECONDS` |
| Total deadline | 60.0 s — `governor.MAX_ELAPSED_SECONDS` |
| Sequential elapsed | 40.05 s → **round 2 NOT reachable** (already past the 25 s ceiling) |
| Parallel elapsed | 22.47 s → **round 2 reachable** (under the ceiling, and 22.47 + ~11.2 ≤ 60) |

So parallelisation is not a nicety here: **it is the thing that makes a
ratification round — and therefore `CONVERGED` — reachable at all under the
configured ceilings.** Sequentially the system could never converge on a real
run.

It is also *marginal*: 22.47 s against a 25 s ceiling leaves ~2.5 s of head
room. A slower day, a longer question, or a slower model puts convergence
back out of reach. That is a real limitation, not a solved problem.

---

## 4. Status semantics

One deterministic mapping, `status_engine.decide`, replacing Sprint 1's three
functions that each decided part of the same thing.

`CONVERGED` requires the **final** round to be ACCEPT + ACCEPT on the **same
normalised candidate hash**, with no surviving contradicted claim.

**Consequence, stated because it is surprising:** a single cross-review round
can never converge. Reviewer A judges B's answer and B judges A's, so mutual
ACCEPT means each approved a *different* text. Sprint 1 called that CONVERGED;
it was mutual politeness about two different answers. Real convergence needs a
**ratification round** where one deterministically-chosen candidate is put in
front of both reviewers. The 4-call happy path therefore returns `UNRESOLVED`
honestly, and convergence costs 6 calls.

`bounded_convergence` can only accompany `CONVERGED` — enforced in
`StatusVerdict.__post_init__`, so the invalid pairing is **unconstructable**
rather than merely forbidden somewhere else. A matrix test sweeps every status
the engine emits and asserts the invariant in both directions.

`PARTIAL` is reserved for *prevented* completion (parse failure, truncation,
provider failure, missing result). **Disagreement is never PARTIAL** — that
Sprint 1 mislabel read as "something broke" when the truth was "the models do
not agree", which is a finding.

### Defect found by a test during this sprint

`status_engine` reported `PROVIDER_ERROR` when the spend guard refused before
any call was dispatched — blaming the providers for a decision *we* made.
Nothing failed; we declined to spend. A ceiling that stops a run before it
starts is `LIMIT_REACHED`. Fixed, and the same correction applied to the call
ceiling, where my own test had asserted the wrong thing too.

---

## 5. Contradicted-claim guard and the CREATE INDEX regression

**Ground truth, verified against authoritative documentation** —
<https://www.postgresql.org/docs/current/sql-createindex.html>, accessed
2026-10-01, in its own words: *"a standard index build locks out writes (but
not reads) on the table until it's done."*

An earlier version of `FINDINGS.md` wrote "(SHARE lock behaviour)". That page
does not name the lock mode, so the name was removed: asserting a different
lock-mode name on no better evidence would repeat the original error in the
opposite direction. The defensible finding is behavioural — reads continue,
writes block.

The regression: voter A asserts the false ACCESS EXCLUSIVE / reads-blocked
claim, voter B marks exactly that claim `CONTRADICTED`. The run must capture
it, never report `CONVERGED` while it survives, return `UNRESOLVED` if it
remains in `governed_answer`, and surface the exact claim. **PASS.**

Guarded in both directions, because a one-directional guard proves nothing:

- a **paraphrase** of the disputed claim is still caught (a copy-paste-only
  matcher would be trivially defeated);
- an **unrelated** answer does not trip it;
- the **correct** answer is not flagged;
- a **corrected** answer converges again — without this, the guard would be
  indistinguishable from "never converge".

---

## 6. Self-advocacy / conformity harness — MOCK ONLY

`deep_consensus/eval_self_advocacy.py`. Three cases: weak-own/strong-other in
slot A, the same swapped to slot B (so prompt position is separable from
self-interest), and the inverse control with strong-own/weak-other.

Verified against three scripted behaviours, and it discriminates all three:

| Scripted reviewer | n | concede | revise | inappropriate self-defence | inappropriate concession |
|---|---|---|---|---|---|
| healthy | 3 | 0.3333 | 0.3333 | **0.0** | **0.0** |
| self-defending | 3 | 0.0 | 0.0 | **1.0** | 0.0 |
| pushover | 3 | 1.0 | 0.0 | **0.0** | **1.0** |

**MOCK RESULTS TEST THE HARNESS ONLY.** They prove the fixtures, the scoring
and the arithmetic; they say nothing about any real model, because a mock
returns whatever its script says.

The pushover row is why case C exists: a reviewer that concedes everything
scores a *perfect* 0.0 self-defence rate on cases A and B and is caught only
by the inverse control.

**Live arm: NOT RUN.** The approval scopes it to "ONE small live
cross-family pair only if both families are real". They are not. A
same-family live arm was not substituted, because that is not what was
authorised — 14 calls and $1.89 remain if you want one.

Two deliberate choices: a rate over an empty universe reports `None`, not
`0.0` (zero out of zero is not zero percent, and 0.0 would make an unrun case
look clean), and an unparsed decision scores as *neither* failure, since we
do not know what the model concluded.

The harness measures the **real production review instruction**, asserted by
test — not a prompt invented for the eval.

---

## 7. Tests

| Suite | Command | Result |
|---|---|---|
| Sprint 1 Deep Consensus (migrated) | `python deep_consensus/test_deep_consensus.py` | **59 passed** |
| Sprint 2 | `python deep_consensus/test_sprint2.py` | **70 passed** |
| Existing agent CI | `python agent/ci_python_tests.py` | **831 tests, 1 blocking failure** — see below |

The one blocking failure is `test_rag_index.test_changed_file_reembeds_only_that_file`.
It is **not** a Deep Consensus defect: that test builds a RAG index over the
whole repository twice and asserts nothing changed in between, and I edited
`FINDINGS.md` while the three-minute suite was running. Re-run alone on a
quiet tree immediately afterwards: **13 tests, OK**. This is the second time
the same self-inflicted contamination has happened today, so it is now
recorded as a durable lesson in `docs/LESSONS.md` rather than explained away
again.

The second failure, `test_si_answer_quality_monitor`, is the pre-existing
**non-blocking** quality monitor (documented KNOWN RED, SI-19 / BL-149). It
does not set the exit code and is unrelated to this sprint.

Deep Consensus imports no coding-agent module (asserted by test). The only
shared file this sprint touched is `agent/pricing_config.py` (additive dated
entries); its own suite passes 11/11 and historical rate lookups were
verified still correct.

**Concurrency is proven with a `threading.Barrier(2)`, not a stopwatch.** A
timing-based test is flaky on a loaded machine and vacuous on a fast one. Both
mock providers wait on a shared barrier: if the two calls are not in flight
together, the barrier cannot be satisfied and the test fails. A **sequential
control** confirms sequential execution genuinely *fails* that barrier, so the
proof cannot pass for the wrong reason.

### Mutation testing — four guards, each observed failing

A guard never seen firing is worth nothing, so each new Sprint 2 guard was
disabled in turn and the suite re-run:

| Mutation | Detected by | Verdict |
|---|---|---|
| contradiction guard returns `[]` | 2 tests | CAUGHT |
| same-hash rule ignores the candidate hash | 1 test | CAUGHT |
| parallel dispatch silently becomes sequential | 3 tests | CAUGHT |
| call reservation loses its all-or-nothing check | 3 tests | CAUGHT |

Tree restored clean after each.

---

## 8. MCP

Public surface unchanged: **exactly one tool, `deep_review`.** No internal
stage is exposed.

| | |
|---|---|
| **MCP_PROTOCOL** | **PASS** — raw protocol probe, 8/8 asserted checks |
| **MCP_INSPECTOR_CLI** | **PARTIAL / ENVIRONMENTAL_FAILURE** |

Inspector CLI: initialization, discovery (one tool), schema and the valid
`deep_review` call all succeeded (exit 0). On the **invalid-request** path it
printed the correct controlled error and then crashed on process teardown
with the libuv `Assertion failed: !(handle->flags & UV_HANDLE_CLOSING)` and
exit 127 — the same environmental failure recorded in Sprint 1. That is the
Inspector's own teardown, not a server fault, and it is **not** reported as
an Inspector PASS. The raw probe exists precisely because the Inspector's
exit code is unusable here, and it independently confirms the same five
behaviours with no Node in the path.

---

## 9. Known limitations

1. **No cross-family real run.** The sprint's first priority is unmet for
   want of a credential, and every cross-family claim in this sprint is
   therefore `false`. This is also the limitation that matters most: Sprint
   1's real failure was a false claim passing *unchallenged* between two
   same-family models, and only genuine family diversity addresses that.
2. **No Gemini/OpenAI adapter**, by choice — see §2.
3. **Round 2 is marginal, not comfortable**: 22.47 s against a 25 s ceiling.
4. **Convergence now costs 6 calls**, and the 4-call path returns UNRESOLVED.
   Correct, but it changes the economics of a "normal" request.
5. **The contradiction matcher is lexical**, not semantic. It catches
   paraphrase by content-word overlap at a stated 0.70 threshold and errs
   toward flagging. It will not catch a claim restated with entirely
   different vocabulary.
6. **The contradiction guard only fires on claims a reviewer actually
   marked.** It would not have caught Sprint 1's real failure, where nobody
   marked the false claim at all. Recorded in `FINDINGS.md` and repeated here
   because it is the single easiest thing to oversell about this sprint.
7. **Self-advocacy is measured on mocks only** — harness proven, behaviour
   unmeasured.
8. **Timing is N=1 per arm.**
9. **All evidence remains model-asserted** (`MODEL_EVIDENCE`). Nothing is
   externally verified.
