# Sprint 2 — HALT CHECKPOINT

Halted 2026-10-01 on the Owner's instruction, at a safe checkpoint, pending a
replacement Sprint 2 prompt for a **subscription-backed architecture**.

Nothing was discarded. Nothing was in flight. No push, no deploy.

---

## Spend consumed

| | |
|---|---|
| **Real provider calls in Sprint 2** | **0** of 30 authorised |
| **Known spend in Sprint 2** | **$0.00** of $2.00 authorised |
| Real calls ever made (all Sprint 1) | 8 |
| Known spend to date, all runs | **$0.052790** |

Sprint 1 breakdown, computed from real captured token counts against
now-verified published rates (`agent/pricing_config.py`):

| Model | Input | Output | Cost |
|---|---|---|---|
| `claude-sonnet-5` | 2289 | 3661 | $0.041188 |
| `claude-haiku-4-5-20251001` | 1522 | 2016 | $0.011602 |

`deep_consensus/spend_ledger.jsonl` **does not exist**, which is the
mechanical confirmation that the ledger recorded no Sprint 2 call.

---

## Git state

| | |
|---|---|
| Branch | `deep-consensus-sprint2` |
| HEAD | `3a253ea` |
| Sprint 2 commits | `4dee868` (Phase 0 evidence), `3a253ea` (this checkpoint) |
| Branched from | `90364d6` (final Sprint 1 commit) |
| Pushed | **NO** |
| Deployed | **NO** |

---

## Completed and working

| Item | File | State |
|---|---|---|
| Sprint 1 evidence preserved + forensic FINDINGS | `docs/evidence/deep-consensus-sprint1/` | **DONE** |
| Sprint 2 prompt stored verbatim + SHA-256/commit/branch/timestamp | `docs/evidence/deep-consensus-sprint2/` | **DONE** (v1; superseded — see below) |
| Provider **family** metadata + single `is_cross_family()` predicate | `providers.py` | **DONE** |
| Candidate hashing + contradicted-claim material-presence matcher | `candidates.py` | **DONE** (new) |
| One deterministic status mapping; `bounded_convergence` unconstructable except with `CONVERGED` | `status_engine.py` | **DONE** (new) |
| Persistent 30-call / $2.00 ledger, all-or-nothing reservation before dispatch | `spend_ledger.py` | **DONE** (new) |
| `reserve_calls` / `release_calls` on the run budget | `governor.py` | **DONE** |
| Parallel sealed answers + parallel cross-reviews, stages hard-separated | `orchestrator.py` | **DONE** |
| Deterministic audit ordering (logical, not completion order) | `orchestrator.py` | **DONE** |
| Ratification round on one shared candidate | `orchestrator.py` | **DONE** |
| Verified haiku-4.5 pricing + re-verified sonnet-5 | `agent/pricing_config.py` | **DONE** |

### Design consequence worth carrying forward

`CONVERGED` is now **unreachable in a single cross-review round**, because two
independently written answers are never identical after normalisation. This is
correct — Sprint 1 reported mutual politeness about two *different* texts as
CONVERGED — but it means the 4-call happy path honestly returns `UNRESOLVED`,
and convergence costs a ratification round (6 calls).

---

## Partially completed

**Test migration — 8 of 59 failing, by design, not by accident.**

Every failure is a Sprint 1 assertion that encodes the *old* semantics:

| Test | Asserts (old) | Now correct |
|---|---|---|
| `test_04_accept_plus_accept_is_converged_with_score_one` | 4 calls, CONVERGED in round 1 | 6 calls, CONVERGED only after ratification |
| `test_05_accept_plus_revise_...` | `PARTIAL` | `UNRESOLVED` |
| `test_05_revise_plus_revise_...` | basis `first_available_revision_unendorsed` | `slot_a_candidate_revision_unaccepted` |
| `test_06_mock_disagree_...` | basis contains `dissent_preserved` | `slot_a_candidate_disagree_unresolved` |
| `test_03_both_first_answers_exist_before_any_review_prompt` | 2 calls per slot | 3 (sealed, review, ratification) |
| `test_convergence_stops_immediately_without_a_second_round` | round_count 1 | ratification makes it 2 |
| `test_12_provider_exception_...` | `provider_error_before_review` | `incomplete_review` |
| `test_13_malformed_response_still_runs_stop_logic` | round/budget stop reason | `incomplete_review` |

The replacement edits were authored but the shell heredoc carrying them failed
(an apostrophe-quoting problem in this environment, hit several times today),
so **`test_deep_consensus.py` is unmodified and uncorrupted** — the migration
was simply never applied. The exact replacement assertions are recorded in the
checkpoint commit message and reproducible from the table above.

---

## Not started

- Sprint 2 tests: concurrency proof, reversed-completion audit ordering,
  same-hash rule, contradiction guard, CREATE INDEX regression, self-advocacy
  harness, ledger ceiling tests (prompt items 3–10, 23–30).
- Self-advocacy / conformity eval harness.
- CREATE INDEX deterministic regression case.
- Sequential-vs-parallel performance measurement and round-2 reachability
  calculation.
- MCP re-verification (surface unchanged, but not re-probed this sprint).
- Any live run.

---

## Second provider family — BLOCKED_REAL_PROVIDER_CREDENTIAL

Verified 2026-10-01, unchanged from Sprint 1:

- `OPENAI_API_KEY` **absent**; `openai` SDK **not installed**.
- `GEMINI_API_KEY` / `GOOGLE_API_KEY` / `GOOGLE_GENAI_API_KEY` **absent**;
  `google.genai` and `google.generativeai` **not installed**.

No OpenAI or Gemini adapter was written. That was deliberate: writing an
adapter against an SDK that is not installed and cannot be exercised would be
coding against a remembered API, which this project's rules forbid. The
family *abstraction* is in place, so adding a real adapter later is small.

---

## Prompt supersession — needs attention in the next sprint

`APPROVED_PROMPT.md` holds the **first** Sprint 2 prompt
(SHA-256 `3eac64fb7b606b84be8e39d64a2e2169d88b525fdae576d6c88ad40b618f8f2d`).
A **revised final** Sprint 2 prompt was issued afterwards and was NOT stored
before the halt. Differences that matter:

- field named `cross_family_real` (implemented, alongside `cross_family`);
- 32 required tests rather than 23;
- a "PRODUCT PRINCIPLES — RECORD ONLY" section;
- **"Do not advertise a future exact price yet"** — which reverses an earlier
  instruction in the same conversation to state a rough future price;
- **"Do not market Owner as 'future CTO'"** — public positioning is
  architect/builder of the product.

Both corrections are recorded in the private memory store. The replacement
prompt should be stored verbatim when the next sprint starts.

---

## Reusable under a subscription-backed architecture

Most of this sprint survives a move from per-call API billing to
subscription-backed access, because the pieces were built around *governance*
rather than around billing:

| Reusable as-is | Why |
|---|---|
| `status_engine.py` | Pure function over review facts. Knows nothing about who paid. |
| `candidates.py` | Hashing and contradiction detection are billing-agnostic. |
| `orchestrator.py` parallelism, stage separation, audit ordering | Independent of the credential source. |
| `providers.py` family abstraction | A subscription-backed provider is still a family + model + real/mock. |
| `audit.py` | Append-only record, no billing coupling. |
| MCP surface (`server.py`) | One tool, unchanged. |

| Needs rework | Why |
|---|---|
| `spend_ledger.py` | Its unit is *known USD per call from a published rate*. Under a subscription the meaningful ceilings become quota/seat/rate-limit units, not dollars per token. The all-or-nothing **reserve-before-dispatch** mechanism is the valuable part and transfers directly; the dollar arithmetic does not. |
| `agent/pricing_config.py` usage | Per-token pricing stays correct for BYOK/API mode, but a subscription has no per-call price, so cost must report as `NOT_APPLICABLE_SUBSCRIPTION` rather than $0.00 — a new honest third state alongside known and UNKNOWN. |
| `real_provider_smoke.py` / `paid_test_guard` integration | Still correct for API-key mode; a subscription path needs its own gate with different semantics. |

**Open architecture question this raises** (recorded, not acted on): under a
subscription there is no per-call dollar figure, so "cost per verified
outcome" — the project's stated goal metric — needs a different denominator.
Quota units consumed per verified outcome is the obvious candidate.

---

## Current test state, exactly

```
Deep Consensus:  python deep_consensus/test_deep_consensus.py
                 Ran 59 tests -- 51 pass, 8 FAIL (all old-semantics assertions above)

Existing agent:  python agent/ci_python_tests.py
                 Last clean sequential run (Sprint 1 close): 831 tests,
                 0 failures, 0 errors, exit 0, PASS.
                 Full suite NOT re-run after the Sprint 2 engine changes.

Shared file:     python -m unittest test_pricing_config   (run at halt)
                 Ran 11 tests -- OK. This is the ONLY coding-agent file Sprint
                 2 touched (agent/pricing_config.py, additive dated entries),
                 so its own suite was run rather than left as an argument.
                 Deep Consensus imports no coding-agent module. The full 831-
                 test suite still deserves a re-run before Sprint 2 is called
                 complete.
```
