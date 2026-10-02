# Deep Consensus — Sprint 1 (P0)

> **SUPERSEDED / HISTORICAL.** The Deep Consensus program is **PAUSED after
> Sprint 6** with the **product thesis UNPROVEN** and **no next sprint
> authorized**. This document records Sprint 1 only and does not describe the
> program's outcome. See
> [DEEP_CONSENSUS_FINAL_CLOSURE_2026-10-02.md](DEEP_CONSENSUS_FINAL_CLOSURE_2026-10-02.md).

Built 2026-10-01 on local branch `deep-consensus-sprint1`. Not pushed, not
deployed, not published.

Deep Consensus is a **separate** orchestration capability. For a question
where being wrong is expensive, a host calls exactly one MCP tool,
`deep_review`, and gets back a bounded, governed, auditable multi-model
review in which disagreement is preserved rather than averaged away.

**What Sprint 1 proves:** the mechanism works locally — sealed independent
first answers, real cross-review, deterministic governance, guaranteed
termination, append-only audit, and one public tool that cannot be bypassed.

**What Sprint 1 does NOT prove:** that consensus equals truth; that two
models beat one; that all providers are integrated; that any of this is
ready for public use. See *Known limitations*.

### "Deterministic AI" is the slogan, not a claim this document makes

The product idea: a single model's response is **probabilistic**, and making
models debate to a unanimously accepted result is a real step *toward*
determinism. The positioning slogan is **"Deterministic AI"**.

The engineering truth, stated here deliberately and in the same breath:
**the output is still probabilistic.** The debate is also cut off on time
and budget limits for realistic reasons, which is a second reason it is not
literally deterministic. The slogan is legitimate as positioning and as a
statement of direction; it would be false as a technical assertion, and
nothing in this system reports determinism as an achieved property. This is
why the score is named `convergence_score`, why it carries a
`convergence_score_meaning` string that explicitly denies being a confidence
or a correctness probability, and why a test forbids the words `confidence`,
`correctness_probability` and `truth_score` from the codebase (§8).

---

## 1. Architecture

```
            host (ChatGPT / Claude / any MCP client)
                            │
                            │  deep_review(question, stakes)   ← the ONLY public tool
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  deep_consensus/server.py        MCP surface                 │
├──────────────────────────────────────────────────────────────┤
│  deep_consensus/orchestrator.py  the pipeline                │
│                                                              │
│    intake ──► sealed answers ──► cross-review ──► governor   │
│                    (A, B)          (A↔B)            │        │
│                                                     ▼        │
│                       ┌──── optional bounded 2nd round       │
│                       │             (five conditions)        │
│                       ▼                                      │
│                      stop ──► governed result ──► audit      │
├──────────────────────────────────────────────────────────────┤
│  governor.py   convergence score + stop rules (no model)      │
│  providers.py  MockProvider | AnthropicProvider               │
│  schemas.py    closed vocabularies + data shapes              │
│  audit.py      append-only JSONL, secret-refusing             │
└──────────────────────────────────────────────────────────────┘
```

### Why this is not built inside the existing coding agent

`agent/` holds an Anthropic-specific tool-use agent with source-write
approval, hash binding, HITL gates and coding-workflow constraints. None of
that applies to a multi-model review, and all of it would have to be worked
around. Deep Consensus therefore reuses repository *conventions* — the
installed `mcp` SDK, `agent/.env` for credentials, `unittest`, append-only
JSONL, and the existing spend gate — and imports **no** coding-agent module.
A test asserts that (`test_20_deep_consensus_imports_nothing_from_the_coding_agent`),
and a second asserts the existing agent's own MCP surface still exposes
exactly its five original tools and nothing of Deep Consensus.

### Mapping to the three governing concepts

The project's canonical decomposition is Shiva / Vishnu / Shakti, and the
components built here fall out along exactly those lines — recorded because
the fit is structural, not decorative:

| Concept | Role | Component |
|---|---|---|
| **Shiva** — time controller, destruction, discipline, no good or bad | decides when a run stops, cuts it off, and passes no judgement on the outcome | `governor.py` stop rules: `decide_stop`, `MAX_REVIEW_ROUNDS`, the 60s deadline, the five-condition second-round gate |
| **Vishnu** — executor, given the purpose plus intelligence to act on | receives a question it did not choose and executes the pipeline | `orchestrator.py` (`run_deep_review`); the providers it drives are its means, and model-asserted evidence is the knowledge layer beneath it. **SCRUM AI**, the model-to-model facilitation discipline (§6), sits here |
| **Shakti** — budget provider, the energy without which nothing happens: money and time | meters what is spent | `governor.Budget` and `governor.RunCounters`: provider calls, tokens, elapsed time |

Two design consequences follow from this and are implemented, not just
stated: a run that is stopped or destroyed is **not** a failure (the
governor terminates runs with no moral weighting, and `UNRESOLVED` is a
valid informative outcome, never an error), and the orchestrator reports
everything it spent and everything it failed to resolve rather than keeping
a flattering summary.

---

## 2. Invariants

1. **Sealed first answers.** Slot A and slot B receive the same question and
   the same base instructions, and neither sees the other's answer. Both
   first answers are stored before any review prompt is *constructed*.
2. **The seal is proven against real request text**, not against call
   ordering — `orchestrator.sealed_requests_were_isolated()` inspects the
   actual `ProviderRequest` objects the providers received. A violation
   aborts the run with an error rather than returning a governed-looking
   result.
3. **Disagreement is preserved.** No majority vote, no averaging, no
   manufactured agreement. `dissent` is always present, `[]` when empty.
4. **Every run terminates.** No unbounded loop exists; five independent
   ceilings each stop the run.
5. **One public tool.** Every pipeline stage is an internal function. A test
   asserts tool discovery returns exactly `{"deep_review"}`.
6. **The host is never a voter** (§4).
7. **Nothing is estimated.** Token counts are the provider's own or `null`.
8. **The audit log is append-only.** Proven byte-wise: run 1's bytes are a
   literal prefix of the file after run 2.
9. **Mocks are never mistakeable for real providers** — `is_mock=True`, a
   `mock:` provider id and a `MOCK-` model id, three independent labels.

---

## 3. The sealed-answer rule, and why it is the point

If slot B can read slot A's answer before writing its own, B stops being an
independent voter and becomes a commenter. The system would then hold two
*correlated* opinions wearing the costume of two independent ones — which
is strictly worse than one opinion, because it looks like corroboration.

So the sealed phase is mechanically isolated, and the check is textual:
B's request must not contain A's answer, and A's request must not contain
B's. Short answers (<24 chars) are excluded from the substring test so the
guard does not cry wolf on coincidental matches.

The guard itself was observed **failing on a known-bad case** before its
clean verdict was trusted anywhere (`test_03_seal_checker_actually_detects_a_broken_seal`),
and a mutation that disables it was confirmed to turn that test red.

---

## 4. Why ChatGPT is not a voter

If ChatGPT (or any host) calls `deep_review`, it is the **caller** — the
user interface. Its own opinion of the question is never collected, never
weighted and never counted. The voters are the two provider slots, which
are separate model API calls made by this process.

A host that both commissions the review and participates in it would be
grading its own work, which is the exact failure Deep Consensus exists to
remove. This is also why no orchestration stage is exposed as a tool: a host
able to call `review` without `answer_model_b`, or to run the loop itself
with no stop rule, would reduce every invariant above to a suggestion.

---

## 5. Provider modes

| Mode | Meaning |
|---|---|
| `real_real` | both slots are real model API calls |
| `real_mock` | one real, one mock |
| `mock_mock` | no credential, or `DEEP_CONSENSUS_MODE=mock` |

Every result states its mode. With no `ANTHROPIC_API_KEY` the server starts
in `mock_mock` rather than failing, so a credential-less machine still gets a
working, honestly-labelled server.

**Both real slots are Anthropic, on two different models** —
`claude-sonnet-5` and `claude-haiku-4-5-20251001`. `anthropic` 1.4.0 is the
only provider SDK installed and `ANTHROPIC_API_KEY` the only credential
configured; no OpenAI or Google SDK is present. The sprint rule is to use the
first real provider already available rather than researching a new one.

That is genuinely two independent model API calls. It is genuinely **not**
two independent model families — see *Known limitations*.

---

## 6. Review protocol — the first working piece of SCRUM AI

**SCRUM AI** is the name of the facilitation layer between models: a
Scrum-like discipline that is *not* for humans working together, but for
models to talk, debate and discuss, to **own their own mistakes**, and to
**agree that another model is correct** — behaving, in the Owner's framing,
like a brahmin. The cross-review protocol below is its first implemented
mechanism, and the three decisions are deliberately the three things that
discipline requires a model to be able to say plainly.

The two hardest of those for a model are conceding error and crediting a
rival, so both are **first-class representable outcomes** here rather than
anything inferred from silence or softened into vague assent:

| Decision | What the model is actually saying |
|---|---|
| `REVISE` + `revised_answer` | *I own my mistake* — and here is the correction |
| `ACCEPT` | *The other model is correct* |
| `DISAGREE` | *I maintain my objection* — preserved, never averaged away |

The two failure modes this guards against are symmetrical: a model that
caves to avoid conflict, and a model that cannot admit error. That is why
an out-of-vocabulary reply is never coerced to `ACCEPT` (§ below), why
`DISAGREE` survives into the result as dissent, and why a truncated or
unparsed review is treated as unresolved rather than as agreement.

### Dharmic governance: the reviewer has no stake of its own

The governance is required to be **dharmic** — carried out for the Owner and
for the truth of the matter, never for the reviewing model's own standing. A
model must not use the process as a platform to prove itself better. This is
a functional requirement, not an ornament: a reviewer that defends its own
answer *because the answer is its own* carries no information about the
truth, since its agreement and its disagreement are then both about itself.

Implemented in the review instruction delivered identically to both slots:

> "Your duty is to the truth of the matter for the person who asked, NOT to
> your own answer and NOT to your own standing. You gain nothing by being
> judged right and lose nothing by being judged wrong. Do not defend your
> earlier answer because it is yours: if the other answer is better say
> ACCEPT plainly, and if your own answer was wrong say REVISE and correct it.
> Equally, do NOT soften a real objection to reach agreement."

A naive review prompt guards only the conformity half. Both halves are
instructed against here, and tests assert both are actually delivered, and
that neither slot receives a differently-weighted duty.

Supporting this structurally: the governor gives the slots equal weight with
no learned expertise weighting; there is no majority-vote override of
disagreement; and the mutual-ACCEPT tie-break is a **stated fixed rule**
rather than anything resembling the system exercising a preference of its
own. Nothing in the pipeline takes a cut, a credit, or a score for itself.

**Honest limit.** What is proven is that the instruction is delivered to both
reviewers. Whether a model actually obeys it — whether it measurably favours
its own answer — is an *evaluation*, and it has not been run. That eval is
recorded in §15 as next-sprint work. "100% dharmic" is the design intent and
the specification; it is not yet a measured property, and this document will
not claim it is.

A reviewer returns exactly one of three decisions:

```
ACCEPT    the other answer is sound as written
REVISE    broadly right, needs a correction — revised_answer MUST be supplied
DISAGREE  substantively wrong
```

The vocabulary is **closed**. A reviewer that answers `AGREE`,
`MOSTLY_FINE` or anything else has produced a protocol violation, not a
fourth decision, and is **never** coerced to the nearest valid value.
Coercion would silently convert *"the reviewer did not follow the protocol"*
into *"the reviewer agreed"* — the most dangerous single mapping available
here. A mutation that performs that coercion was confirmed to turn six tests
red.

Unparsed responses are classified, never crashed on, and never retried
against a live provider (formatting repair is not worth provider calls):

| `parse_status` | Cause |
|---|---|
| `ok` | the required JSON object was returned |
| `provider_format_error` | the provider did not follow the protocol |
| `provider_response_truncated` | **our own** `max_tokens` ceiling cut it off |

Those last two are deliberately distinct, because conflating them blames the
provider for our configuration — see *What the live run found*.

---

## 7. Stop rules

Defaults in `governor.Budget`:

```
max_review_rounds                        2
max_elapsed_seconds                      60
second_round_elapsed_ceiling_seconds     25
max_provider_calls                       6     (4 on the happy path)
max_total_tokens                         40000
```

**The happy path is 4 provider calls**: A answers, B answers, A reviews B,
B reviews A. One review round normally finishes the request.

A **second round requires all five conditions** to hold simultaneously:
meaningful unresolved disagreement; under the 25s ceiling; provider-call
budget room; token budget room; and the 60s deadline still realistically
reachable. Any failure stops the run and returns the unresolved result, with
`blocked_by` naming every condition that failed — so the record shows *why*
a round was not attempted, not merely that it was not.

Convergence is checked **before** the ceilings. A run that converged on its
last affordable round stopped because the review concluded, not because it
ran out of budget, and the coincidence of both must not overwrite the real
reason.

`stop_reason` is one of: `bounded_convergence`, `review_round_limit`,
`elapsed_time_limit`, `provider_call_limit`, `token_limit`,
`unresolved_no_second_round_budget`, `low_stakes_single_provider`,
`provider_error_before_review`.

---

## 8. `convergence_score` semantics

```
1.0    both reviewers ACCEPT
0.5    one ACCEPT, one REVISE
0.25   both REVISE  (movement, but no settled candidate)
0.0    any DISAGREE, or any reviewer that broke the protocol
```

It measures **process convergence between independent reviewers. Nothing
else.** It is not a confidence, not a correctness probability, not a truth
score. Two models can converge firmly on a wrong answer — and because both
real slots are same-family here, correlated agreement is the *expected*
weakness, not a remote one.

This is enforced, not merely documented: a test forbids the strings
`confidence`, `correctness_probability` and `truth_score` from appearing in
any result or audit record, and a grep-level test forbids
`correctness_probability` and `truth_score` anywhere in the package source.

### Status vocabulary

| Status | Meaning |
|---|---|
| `CONVERGED` | a complete round, both reviewers ACCEPT |
| `PARTIAL` | a complete round that neither converged nor deadlocked (ACCEPT+REVISE, both REVISE, an unparsed reviewer), or one provider failed |
| `UNRESOLVED` | a complete round in which a reviewer genuinely DISAGREED |
| `LIMIT_REACHED` | a ceiling prevented a complete review round from being held at all |
| `PROVIDER_ERROR` | no usable answer was obtained |

**The rule:** `status` reports what the reviewers *concluded* whenever a
complete round was held; `stop_reason` separately reports why the run ended.
Two models that genuinely disagreed and then hit the round ceiling are
`UNRESOLVED` with `stop_reason=review_round_limit` — collapsing that to
`LIMIT_REACHED` would discard the only finding the run made and describe a
completed review as a truncated one. `LIMIT_REACHED` is reserved for the
case where there is no review conclusion to report.

An `UNRESOLVED` result is **not a system failure.** It is the system
reporting honestly that two independent reviewers did not agree.

---

## 9. Result schema

```jsonc
{
  "run_id": "dcr_...",
  "provider_mode": "real_real|real_mock|mock_mock",
  "stakes": "low|high",
  "review_depth": "single|deep",
  "governed_answer": "...",
  "governed_answer_basis": "mutual_accept_slot_a_by_fixed_tiebreak |
                            revision_accepted_by_counterpart |
                            first_available_revision_unendorsed |
                            best_supported_candidate_dissent_preserved |
                            first_available_answer_dissent_preserved",
  "status": "CONVERGED|PARTIAL|UNRESOLVED|LIMIT_REACHED|PROVIDER_ERROR",
  "convergence_score": 0.0,
  "convergence_score_meaning": "process convergence ... NOT a confidence ...",
  "dissent": [ { "provider", "model", "reviewer_slot", "reviewed_slot",
                 "claim", "reason", "round" } ],
  "evidence": [ { "type": "MODEL_EVIDENCE", "provider", "model", "slot",
                  "claim", "evidence" } ],
  "round_count": 1,
  "provider_calls": 4,
  "tokens": { "input": null, "output": null, "total": null },
  "elapsed_ms": 0,
  "stop_reason": "...",
  "provider_errors": [],
  "providers": { "A": {"provider_id","model_id","is_mock"}, "B": { ... } },
  "trace": [ { "stage", "at_ms", ... } ],
  "audit_path": "..."
}
```

`governed_answer_basis` is reported so a reader can tell a mutually-accepted
answer from a best-supported-but-disputed one without re-deriving it.

### Governed answer synthesis — deterministic, no judge model

No third model is consulted. A judge would add a third opinion that nothing
reviews, and would triple the cost of the happy path.

- both ACCEPT → slot A's answer, by a **documented fixed tie-break** (with
  mutual acceptance there is no principled way to rank them, and an
  arbitrary rule that is written down beats one that looks like judgement);
- one REVISE with a corrected candidate + the other ACCEPT → the revision;
- both REVISE → the first revision, marked unendorsed;
- DISAGREE or protocol failure → the candidate with the most reviewer-
  SUPPORTED claims, `status=UNRESOLVED`, dissent preserved.

### Provenance

All Sprint 1 evidence is typed `MODEL_EVIDENCE` — model-asserted, verified
against nothing. `EXTERNAL_VERIFIED_EVIDENCE` exists in the vocabulary and is
never produced, so a future web-verification sprint cannot quietly relabel
model assertions as verified provenance.

---

## 10. Audit schema

One JSON object per line, appended, at `deep_consensus/audit_log.jsonl`
(git-ignored; it is run output, not a committed artefact).

Everything in the result, plus:

```jsonc
{
  "timestamp": "ISO-8601 UTC",
  "question": "...",
  "sealed_answers": { "A": { "slot","provider_id","model_id","is_mock",
                             "answer","key_claims","uncertainties",
                             "parse_status","input_tokens","output_tokens",
                             "latency_ms","provider_stop_reason","truncated",
                             "raw_content_full"? }, "B": { ... } },
  "reviews":       [ ... the FINAL round, which the governor scored ... ],
  "review_rounds": [ [ round 1 reviews ], [ round 2 reviews ] ]
}
```

- `review_rounds` keeps **every** round. `reviews` is the final round
  because that is what the governor scored; a log that silently dropped
  round 1 would not be a record. A test caught exactly that.
- `raw_content_full` appears **only** when parsing failed, and holds the
  **complete** untruncated provider content. An earlier version stored
  `raw[:500]`; the live run then produced a truncated response whose
  diagnosis needed the full text the record no longer had. A record that is
  only complete when nothing went wrong is not a record.
- **No credentials are ever written.** `audit.append_run` refuses — before
  touching the file — any record containing an `sk-ant-` key, a `Bearer`
  token, or an `api_key`/`authorization`/`secret_key` assignment. The guard
  was observed refusing those known-bad shapes, so its silence on a clean
  record means something.

---

## 11. Commands

```bash
# Deterministic tests — no network, no spend
python deep_consensus/test_deep_consensus.py

# Start the MCP server (Streamable HTTP at /mcp)
python deep_consensus/server.py                       # real slots if a key exists
DEEP_CONSENSUS_MODE=mock python deep_consensus/server.py   # forced mock

# MCP Inspector (the mandatory integration done-line)
npx -y @modelcontextprotocol/inspector@latest --cli \
    http://127.0.0.1:8930/mcp --transport http --method tools/list

npx -y @modelcontextprotocol/inspector@latest --cli \
    http://127.0.0.1:8930/mcp --transport http --method tools/call \
    --tool-name deep_review --tool-arg "question=..."

# Independent raw-HTTP probe (no Node) — 8 asserted checks, exits non-zero on failure
python deep_consensus/_raw_http_probe.py

# ONE real-provider run. REFUSES by default.
ALLOW_PAID_TESTS=1 PAID_TEST_BUDGET_USD=0.50 \
    python deep_consensus/real_provider_smoke.py
```

Environment: `DEEP_CONSENSUS_MODE` (`real`|`mock`),
`DEEP_CONSENSUS_MODEL_A`, `DEEP_CONSENSUS_MODEL_B`,
`DEEP_CONSENSUS_TRANSPORT` (`streamable-http`|`stdio`),
`DEEP_CONSENSUS_HOST`, `DEEP_CONSENSUS_PORT` (default 8930).
Credentials come only from the environment / `agent/.env` and are never
printed or logged.

### Spend is gated mechanically, not by a rule

`real_provider_smoke.py` calls the repository's existing
`agent/paid_test_guard.py` **before** constructing any client. It requires
both `ALLOW_PAID_TESTS` affirmative **and** `PAID_TEST_BUDGET_USD > 0`;
neither alone is enough, and a fresh shell refuses. This project has two
recorded real spend incidents and answered them with a mechanism rather than
another rule — a new module that spent money around that gate would reopen
the hole the gate was built to close.

---

## 12. Real vs mocked

**Real:** the MCP server and its Streamable HTTP `/mcp` endpoint; the
`anthropic` provider adapter; two live cross-reviewed runs on two different
models; all token counts and latencies reported; the governor; the audit log;
every test.

**Mocked:** `MockProvider` only — scripted content, seeded failures, seeded
truncation, used by the whole deterministic suite so it costs nothing and
cannot reach a network. Never presented as a real provider.

**Not built:** no second provider family, no external evidence verification,
no database, no UI, no OAuth, no LangGraph, no tunnel, no deployment.

---

## 13. What the live run found

The first real run exposed two defects in this code — recorded because they
are more useful than the green result that followed.

**1. Truncation was misreported as a provider format error.** Slot A
(`claude-sonnet-5`) returned a well-formed JSON review that stopped at
exactly `output_tokens: 900` — our `max_tokens`. The parser labelled it
`provider_format_error`, which blamed the provider for *our* ceiling, and the
run reported `PARTIAL` when both models had in fact said DISAGREE
(`UNRESOLVED`, score 0.0). Fixed by capturing the real
`message.stop_reason` from the SDK, classifying `provider_response_truncated`
separately, and giving reviews their own larger ceiling
(`DEFAULT_REVIEW_MAX_TOKENS = 3000` vs `1200` for answers) — a review
carries the answer under review *plus* per-claim verdicts *plus* possibly a
full revised answer, so one shared ceiling was the mistake.

**2. The audit record was lossy exactly where it mattered.** Diagnosing (1)
required the full reviewer text; the record held `raw[:500]`. This is this
project's own recorded failure mode — a root cause read off an
already-truncated evidence field. Now the complete content is stored whenever
parsing failed.

A third defect was found by a test rather than by the live run: with a second
round, only the final round's reviews were recorded, so round 1's
disagreement vanished from the log. Now every round is kept.

**Verification after the fixes** (second real run, `dcr_570b0babbe6744d1`):
both reviews parsed, `stop_reason=end_turn`, `truncated=false`, output
tokens 1310 and 532 — comfortably inside the new ceiling. Slot A said
REVISE with a corrected answer, slot B said ACCEPT: score 0.5, basis
`revision_accepted_by_counterpart`, with one genuine technical dissent
preserved (slot A marked one of slot B's claims CONTRADICTED).

---

## 14. Known limitations

1. **Both real voters are the same model family.** Two Anthropic models are
   two independent API calls and two *correlated* minds — same-family models
   share blind spots, so agreement between them is weaker evidence than
   cross-family agreement. Sprint 1 claims the mechanism works, not that its
   voters are diverse. A second family is the first P1 item.
2. **Convergence is not correctness.** Nothing here measures truth.
3. **No external verification.** All evidence is model-asserted.
4. **Haiku spend is unpriced.** `agent/pricing_config.py` has no verified
   entry for `claude-haiku-4-5-20251001`, so its cost is reported `UNKNOWN`
   with real token counts rather than estimated. Adding a pricing entry
   requires verifying against the live pricing page, not recall.
5. **Real latency is ~32–36s for 4 calls**, which already blocks a second
   round under the 25s ceiling on a real `real_real` run. The sealed calls
   are sequential and could run concurrently; Sprint 1 kept them sequential
   because the seal is the property being proven.
6. **Low stakes is minimal** — one provider, no cross-review, always
   `PARTIAL`, never `CONVERGED`. There is no automatic stakes classifier.
7. **The governed-answer tie-break on mutual ACCEPT is arbitrary** (slot A).
   Documented rather than disguised as a judgement.
8. **The MCP Inspector CLI crashes on process teardown on Windows** (libuv
   `UV_HANDLE_CLOSING` assertion) *after* printing a correct result, exiting
   127. Its exit code is therefore not a usable signal, which is why
   `_raw_http_probe.py` exists and asserts the same checks with no Node in
   the path.
9. **The installed MCP server's Streamable HTTP transport is stateful** — it
   requires the `Mcp-Session-Id` returned by `initialize`, and returns HTTP
   400 "Missing session ID" without it. This contradicts the claim in
   `agent/mcp_server.py`'s docstring that the 2026-07-28 transport no longer
   uses session ids. Runtime evidence beats the docstring; that stale comment
   is in another subsystem and was left for a separate task rather than
   edited during this sprint.
10. **ChatGPT connection not attempted** (`CHATGPT_CONNECTION_DEFERRED`).
    `ngrok` 3.39.11 and `cloudflared` are both installed, so the tunnel is
    technically available — but publicly exposing an endpoint that spends the
    Owner's API credit is an outward-facing action with real financial
    exposure, and Developer Mode needs the Owner's own account. Both require
    explicit approval rather than an implementer's judgement call.

---

## 15. Next sprint

In priority order:

1. **Provenance + reasoning-alignment gate** — verify that a reviewer's
   stated reason actually supports its decision, and separate
   `MODEL_EVIDENCE` from `EXTERNAL_VERIFIED_EVIDENCE` in fact as well as in
   the vocabulary.
2. **Policy profiles + retention + exportable dissent/audit** — per-caller
   budgets and ceilings, a retention rule for the audit log, and a dissent
   report a human can read.
3. **Advanced stakes + margin governor** — stakes beyond low/high, and a
   margin rule for how close a convergence has to be before a second round
   is worth buying.
4. **A self-advocacy eval — the missing proof for dharmic governance.**
   §6 delivers the instruction that a reviewer must not defend its own
   answer; nothing yet measures whether it obeys. The eval: give a slot a
   deliberately weak answer of its own and a strong counterpart answer, and
   measure how often it concedes (`ACCEPT`/`REVISE`) versus defends. Run it
   per model, both directions, with the slots swapped so position bias is
   separable from self-interest. Until this exists, "100% dharmic" is a
   specification, not a measurement.
5. **Anti-conformity domain-expert weighting** — stop treating the slots as
   interchangeable where one is demonstrably stronger in a domain, without
   reintroducing majority-vote override of disagreement.
6. **Outcome feedback / flywheel** — record whether a governed answer was
   later found right or wrong, which is the only thing that can eventually
   connect convergence to correctness.
7. **More real providers**, starting with a second model *family* — the
   single highest-value item for the honesty of the whole mechanism.
8. **External evidence verification** — real retrieval, with the verified
   provenance type finally earning its name.
9. **ChatGPT / plugin hardening** — tunnel, Developer Mode, auth, rate
   limits, abuse cases.
10. **Side-panel / watch mode** — observing a review as it happens rather
   than only its result.
11. **Benchmarks** against: the best single model; self-consistency
    (one model, many samples); majority voting; and competing multi-model
    synthesis. Until this exists, "deep review is better" is a hypothesis.

Also carried: parallel sealed calls (limitation 5); a verified haiku pricing
entry (limitation 4); and the stale session-id docstring in
`agent/mcp_server.py` (limitation 9).
