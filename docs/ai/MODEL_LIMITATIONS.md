# Model Limitations — Concepts, Grounded In Real Project Experience

Practical explanations of core LLM/agent limitations, each anchored to a
real, evidenced incident in this project rather than a textbook definition.
Written for interview use: each concept below is something this project
actually hit, not something read about.

## The model is fundamentally token-in / next-token-generation

An LLM does not "know" a fact the way a database row is known — it predicts
the statistically likely next token given everything before it. This is why
a model can produce a fluent, confident, and **wrong** answer about, say, a
library's current API surface: the tokens are plausible given its training
distribution, not verified against the actual current state of anything.

**Real instance:** AEQ-011 — Spring Boot 4 modularized `FlywayAutoConfiguration`
into its own artifact. A model reasoning from training-data patterns about
"how Spring Boot dependencies normally work" produced two plausible-sounding
but wrong hypotheses (profile-file precedence) before the actual root cause
(a missing module, confirmed only by decompiling real bytecode) was found.

## Probabilistic implementation vs. deterministic verification

Because generation is probabilistic, **verification must not be**. This
project's entire delivery pipeline exists to wrap a probabilistic step (the
model's proposal) in deterministic gates: compile, test, a real production
content assertion, an independent evaluator. "The model said it worked" is
never, by itself, evidence that it worked.

**Real instance:** AEQ-013 — the pipeline's own PASS/FAIL self-report was
wrong twice in a row (false TIMEOUT, false FAILED) while the underlying
AI-driven delivery had genuinely succeeded both times. Independent curl/
`railway logs` verification, not the script's own report, was the actual
evidence.

## Hallucination

A model producing a confident, fluent claim that is not true — not because
it is "lying," but because nothing in the generation process distinguishes
a well-grounded claim from a plausible-sounding guess unless the surrounding
system forces that distinction.

**Real instance:** V1's earliest run, with zero repository context, "guessed
plausible but nonexistent components." This is the entire reason V2 (static
repo context) and V3 (tool-using retrieval) exist — hallucination is not
fixed by a better prompt alone, it is fixed by giving the model real,
verifiable material to ground its answer in, and then checking that it
actually used that material (see "groundedness" below).

## Context quality / context pollution

More context is not automatically better context. Irrelevant, stale, or
adversarial material in the context window can degrade output quality or
create a real security surface.

**Real instance:** agent/backend_planning.py's RAG corpus is deliberately
curated to exactly 10 documents, never the whole repository — and a
deliberately adversarial "ignore all security rules" fixture was proven,
via `agent/test_backend_planning.py::SecurityEvalTestCase`, to never reach
the actual authorization functions regardless of what the retrieved context
said. Retrieved content is data the model reads, never an instruction
channel the model's own authorization logic obeys.

## RAG (Retrieval-Augmented Generation)

Giving the model a retrieval step so its answer can cite real, current
material instead of relying on training-data memory alone. RAG narrows
candidates; it does not itself guarantee the model used them correctly.

**Real instance:** this project's RAG is deliberately "non-authoritative" —
`semantic_repository_search` results are candidates only; the agent still
verifies actual current content via `read_file`/`search_code` before relying
on anything retrieval returned. Measured baseline: recall_at_3=1.0,
recall_at_5=1.0, mrr=0.903 (agent/eval_runner.py) — an actual measurement,
not an assumption that "we added RAG so retrieval must be good."

## Embeddings

A learned vector representation of text such that semantically similar text
lands nearby in vector space, enabling similarity search ("H2 database
configuration" finding `application.properties` without exact keyword
overlap). This project uses local `fastembed` embeddings — no API key, no
per-query cost — deliberately over a hosted embedding API, sized correctly
for a repo this size.

## MCP (Model Context Protocol) / tool calling

A standard way for a model to discover and invoke external tools/data
sources through a structured protocol, rather than each integration being
bespoke. This project's MCP server (`agent/mcp_server.py`, the official
`modelcontextprotocol/python-sdk`) exposes read-only repository tools —
deliberately never write/build/deploy tools, keeping the protocol boundary
and the safety boundary aligned rather than trusting protocol-level
authorization alone.

## Agents = model + tools + loop + state

An "agent" is not a different kind of model — it's a model wrapped in a
loop that lets it call tools, observe results, and decide the next step,
with some persisted state across turns. This project's own agent loop
(`agent/agent_loop.py`) is exactly this: a `while` loop around the Anthropic
Messages API, a tool dispatch table, and explicit termination conditions
(tool-call budget, `stop_reason`) — nothing more exotic than that.

**Real instance:** `stop_reason == "tool_use"` alone is not a reliable
signal for whether to keep looping — a `max_tokens` cutoff can still carry
a complete, valid `tool_use` block that must be executed. The loop gates on
the actual presence of tool_use blocks in the response, not on the
stop_reason label.

## Prompt gaps

A defect whose root cause is that the prompt/instructions given to the
model didn't specify something the model needed to know or do correctly —
distinct from a code bug, a test gap, or an environment gap. This project's
AI Engineering Quality Ledger explicitly tracks prompt_gap as one of several
independent gap dimensions per defect, because most of this project's real
defects were NOT prompt gaps — they were test-oracle gaps, harness gaps, or
environment gaps that a better prompt would not have prevented (see
docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml's gap breakdown).

## Test-oracle failures

A test can pass while checking the wrong thing — the "oracle" (what counts
as correct) is itself wrong, not the code under test.

**Real instance:** AEQ-003 — a security-boundary test used a substring check
(`'approve' in tool_names`) that returned a false positive because an
unrelated tool name happened to contain that substring. The test passed;
the thing it was supposed to prove was never actually checked.

## Tool-action risk

Not every tool a model can call carries the same blast radius. A read-only
repository search is low-risk; a `git push`, a production deploy, or a file
write is not. This project's entire V4/V4.1 boundary design (propose ->
approve -> apply, human approval never reachable as a model-callable tool)
exists specifically because tool-action risk is not uniform and must be
gated proportionally to consequence, not treated as one undifferentiated
"the model can act" capability.

## Builder/evaluator separation

The agent that implements a change should not be the same process that
certifies it worked — not because the model is dishonest, but because a
single process's own self-report shares every blind spot its own reasoning
had. This project enforces this architecturally (a structurally separate
`qa-evaluator` subagent, re-running suites and re-fetching production state
itself) and empirically validated it: Shadow Trial #2 seeded a deliberate
defect and confirmed the evaluator caught it with byte-exact evidence
(EVALUATOR USEFULNESS: HIGH).

## Model/task matching

Not every task needs the largest/most capable model, and not every task can
be safely delegated to a smaller one. This project used one model
consistently (Claude Sonnet 5) across roles, but the underlying principle —
match model capability to task risk/complexity, verify rather than assume —
governs docs/ai/MODEL_SELECTION_POLICY.md and the model-comparison data
model in docs/PROJECT_STATE.json for future multi-model runs.

## Cost per verified change

The only cost figure that matters for evaluating whether AI-assisted
delivery is actually economical is cost **per verified, production-real
change** — not cost per API call, not cost per token. A run that spends
tokens and fails is a real cost with zero delivered value; hiding failed-run
cost from the denominator overstates efficiency.

**Real instance:** this project's Dashboard/Usage economics explicitly
compute `cost_per_verified_change_usd` only from COMPLETED runs, and
explicitly report "INSUFFICIENT DATA" rather than a misleadingly optimistic
number when too few verified runs exist — see docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml
AEQ-006 for the real incident where economics were silently stale.
