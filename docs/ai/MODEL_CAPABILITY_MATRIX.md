# Model Capability Matrix

Practical notes on what an LLM (specifically Claude, the model actually used
throughout this project) can and cannot do reliably, grounded in this
project's own real usage — not a general AI capabilities survey. See
docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml for the concrete defects behind
several of these rows.

| Capability | Reliable here? | Real evidence from this project |
|---|---|---|
| Understanding a natural-language requirement and producing a correct implementation plan | Yes, when given real repository context (read tools / RAG) | V2/V3 planners; AEQ-013's LLM analysis was correctly grounded, flagged by a deterministic groundedness checker when it claimed an unretrieved file |
| Writing correct, compiling Java/Python code for a well-scoped change | Yes, for bounded, well-specified changes | Multiple real Workbench COMPLETED runs, each independently compiled/tested |
| Reasoning about its own trustworthiness / certifying its own work | **No — architecturally never trusted for this** | approve/reject are never model-callable tools (verified by exact set membership, AEQ-003); a structurally separate qa-evaluator subagent re-verifies |
| Knowing a fast-moving library/framework's CURRENT API surface from training memory alone | **No — frequently wrong or stale** | AEQ-011 (Spring Boot 4's FlywayAutoConfiguration split), the MCP "fastmcp vs official SDK" naming lesson, Testcontainers 2.x artifact renames — training-data recall is not current documentation |
| Predicting its own token/investigation cost before acting | Weak | AEQ-005: a LOW-confidence heuristic undershot real usage by 126% on a TINY requirement — investigation cost, not code-generation cost, dominated |
| Producing plausible-but-wrong output when context is missing, rather than saying "unknown" | Yes, this is a real failure mode to design against | V1 (pre-repository-context) "discovered that without repository context Claude guessed plausible but nonexistent components" — the reason V2/V3 exist at all |
| Following a hard security/scope boundary when the boundary is enforced in code, not just in the prompt | Yes | write_tools.py's scope restriction + approval binding hold regardless of what the model argues for; adversarial prompts against the live risk-classification endpoint were defense-in-depth blocked at the code layer even where the text classifier alone would have let them through |
| Following a hard security/scope boundary when the boundary exists ONLY in the system prompt | Not something this project ever relies on | Every actual safety boundary in this codebase (approval gate, file-scope allowlist, risk_policy) is enforced in Python, never "the prompt tells it not to" |
| Retrieval-augmented grounding vs. hallucinated citation | Reliable when paired with a deterministic groundedness check | agent/backend_planning.py's check_groundedness() catches any file the model claims but that was never actually retrieved |
| Consistent behavior across model/SDK versions without re-verification | **No — assume it changed** | "Claude Sonnet 5 returns thinking blocks by default" caused a real V1 crash from code written against an earlier assumption; MCP Python SDK naming changed mid-project |

## The one-line summary

A model is excellent at *generating* a plausible next step and *reasoning
in-context* about a well-specified, well-grounded problem. It is not
reliable at *knowing what it doesn't know*, *certifying its own
correctness*, or *tracking a fast-moving external fact* (a library version,
its own token cost) without an explicit, deterministic check outside the
model itself. Every reliability mechanism in this project (RAG grounding
checks, deterministic risk classification, independent QA evaluator,
compile/test verification, production content assertion) exists because of
one of the rows above, not as generic best practice.
