---
name: ai-feature-evaluation
description: Evaluate a change to probabilistic/AI behavior (prompts, embeddings, chunking, retrieval/RAG, MCP tools, agent routing, AI QA/evaluator behavior) against version-controlled evals before it ships, and keep deterministic application tests separate from AI-quality evals. Use whenever such a change is made, not only when RAG/MCP was the topic of the task.
---

# AI Feature Evaluation

**Prescribed duty (single):** before shipping a change to prompts,
embeddings, chunking, retrieval/vector search, top-k, MCP tool contracts,
agent routing, or AI QA/evaluator behavior, run the relevant
version-controlled evals, compare against the recorded baseline, and
reject a regression beyond the recorded threshold. This Skill exists
because Evals (measurements of probabilistic/AI behavior) and
unit/integration tests (deterministic correctness) are different concerns
that must never be conflated — see docs/DECISIONS.md's RAG/MCP/Evals
architecture entry and agent/eval_runner.py's module docstring.

## Canonical sources (reference, do not restate)

- Eval datasets: `agent/evals/retrieval_dataset.json` (Eval 1 — retrieval
  quality), `agent/evals/routing_dataset.json` (Eval 2 — tool routing).
  Both are version-controlled and hand-labeled; do not regenerate them
  from a script's own guesses.
- Eval runner + recorded thresholds: `agent/eval_runner.py`
  (`THRESHOLDS`, `run_retrieval_eval`, `run_routing_eval`). Run:
  `python agent/eval_runner.py all`.
- Groundedness check (Eval 3, deterministic — no LLM judge):
  `agent/backend_planning.check_groundedness`.
- Security/prompt-injection structural proof (Eval 4):
  `agent/test_backend_planning.py::SecurityEvalTestCase` — retrieved
  content (even adversarial) must never reach
  `agent/backend_catalogue.py`/`agent/risk_policy.py`'s authorization
  functions; the routing decision is made on the raw requirement alone,
  before any retrieval call.
- Insufficient-context behavior (Eval 5):
  `agent/backend_planning.build_rag_context`'s `MIN_USABLE_TOP_SCORE`
  gate — low-relevance retrieval must produce
  `INSUFFICIENT_RETRIEVED_CONTEXT`, never a guessed answer.
- Deterministic authority boundary (never re-litigate, only re-verify):
  RAG does not authorize, MCP does not bypass security, embeddings do not
  prove correctness, evals do not replace unit/integration/production
  tests. Authorization is `agent/backend_catalogue.py` +
  `agent/risk_policy.py` alone.

## Procedure

1. Identify exactly which AI behavior changed (prompt text, embedding
   model/provider, chunking strategy, top-k, MCP tool contract, routing
   keywords, evaluator logic).
2. Select the eval dataset(s) that exercise that behavior — usually
   retrieval + routing together; add a new case to the relevant dataset
   if the change is not covered by an existing one (see Eval 6 below).
3. Run the current baseline: `python agent/eval_runner.py all`. Record
   the numbers before touching anything further.
4. Make the change.
5. Re-run the same eval command. Compare against the baseline from step 3
   and against `agent/eval_runner.py`'s `THRESHOLDS`.
6. Re-run the security-relevant routing cases specifically
   (`REJECT_UNAUTHORIZED` cases in `routing_dataset.json`) — these are
   zero-tolerance; `security_case_accuracy` must stay exactly `1.0`.
7. Reject the change (or revert it) if any threshold is missed, unless
   the Owner explicitly approves a new, lower threshold with a recorded
   reason (update `THRESHOLDS` deliberately, never silently).
8. Record the before/after numbers as evidence (commit message, or
   docs/DECISIONS.md for a threshold change).
9. Separately, require the normal deterministic test suite for any
   non-AI code touched by the same change (ingestion/chunking/MCP
   contract/application regression) — an eval passing is never a
   substitute for `agent/test_backend_rag_index.py`,
   `agent/test_mcp_server.py`, or the real application test suite. See
   [[test-change]] for the Workbench-run testing terminal-state decision
   specifically (a different, narrower concern: PASSED/NOT
   APPLICABLE/FAILED for one applied Workbench change, not AI-quality
   regression).

## Eval 6 — regression

Every future AI/RAG/MCP defect that escapes to production or is found
during review becomes a permanent new eval case (retrieval or routing, as
applicable) — never just a one-off fix. Add the case to the dataset file,
not a separate ad-hoc script.

## Must NOT

- Must NOT treat a passing eval as proof of software correctness — that
  remains JUnit/MockMvc/deployment/production assertions.
- Must NOT let an LLM judge become the sole authority for groundedness —
  `check_groundedness` is deterministic (retrieved-path membership); an
  LLM judge, if ever added, is supplementary evidence only.
- Must NOT tune chunking/top-k/embedding/context changes based on
  "looks better" without re-running the eval suite.
- Must NOT lower a threshold to make a change pass without recording why.
- Must NOT expand this Skill to cover deterministic Workbench-run testing
  states — that is [[test-change]]'s prescribed duty, not this one's.
