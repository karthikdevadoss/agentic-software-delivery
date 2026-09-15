# Reusable Platform Boundaries

Phase 20 of the Base Architecture V3 directive. Identifies which of this
project's real deterministic modules already have zero Customer-App/
Energy-Platform-specific coupling today — evidence for a future reuse
decision, not a claim that reuse has actually happened (it hasn't; no
second domain exists, and the directive explicitly says not to build one
speculatively). Companion to `docs/DETERMINISTIC_ENGINEERING_KERNEL.md`'s
mapping table — this document goes one level deeper on *which* of those
mapped modules are actually import-ready for a hypothetical second domain
versus which are domain-coupled by their nature.

## Genuinely domain-agnostic today (a second domain could import these unchanged)

| Module | Why it's domain-agnostic |
|---|---|
| `agent/tools.py`'s `_resolve_safe_path`/path-traversal-security | Operates on any repository root; zero Customer-App concepts |
| `agent/event_ledger.py` | Schema is generic (event type, source, payload, timestamps); zero Customer-App-specific columns |
| `agent/write_tools.py`'s approve/apply hash-binding mechanism | Hash-equality identity binding has no business-domain awareness |
| `agent/triage_promotion.py`'s candidate-hash-binding pattern | Same mechanism as above, reused for a second real use case already (proof this pattern generalizes even within one codebase) |
| `agent/execution_tools.py`'s dispatch-dict capability-control pattern | Exact-set-membership tool exposure is a generic technique |
| `agent/build_tools.py`'s subprocess-argv-list-no-shell pattern | The *shape* (never `shell=True`, real exit codes, structured evidence) is generic even though *what* it compiles (Java/Maven) is not |
| `agent/reasoning_gateway.py` | Purpose-gating/default-deny/`LLM_MODE=DISABLED` logic has zero business-domain awareness — only the `ADVISORY_PURPOSES` values would need revisiting per-domain, and even those (semantic interpretation, ambiguity analysis, root-cause hypotheses, implementation proposals, adversarial test ideas, human explanation) read as genuinely domain-general categories |
| `agent/risk_policy.py`/`agent/change_risk.py`'s rule-table *mechanism* | Ordered rule table, fail-closed-to-`UNKNOWN` — the mechanism is generic; the actual rules (file-path patterns, keyword lists) are this project's own and would need replacing, not the engine |

## Domain-coupled by nature (the pattern is reusable, the content is not)

| Module | What's coupled | What's actually reusable |
|---|---|---|
| Business invariants (`ContractPlanService`'s idempotency check, `WorkspaceAccessGuard`) | The specific rule (duplicate enrollment, per-customer isolation) | The *pattern* — compiled/DB-enforced invariants, never prompt-enforced |
| `agent/rag_index.py`/`agent/backend_rag_index.py`'s corpus | The actual indexed content (this project's own source/docs) | The chunking-at-logical-boundaries + incremental-reindex *mechanism* |
| `agent/demo_execution.py`/`agent/backend_execution.py` | The deploy target (Railway, this specific app) | The isolated-workspace-clone → dedicated-branch → timestamp-verified-deploy *pattern* |
| `docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml`'s entries | This project's own incident history | The schema itself (`defect_id`, `root_cause`, `recurrence_status`, `analysis_confidence`, etc.) — already proven reusable in spirit, since this session's own AEQ-022 entry used the exact same schema a different session originally designed |

## What "reusable" does NOT mean yet

None of the modules above have been extracted into a separate installable
package, published, or actually imported by a second project — "reusable"
here means *structurally decoupled enough that doing so would be low-
effort*, evidenced by the coupling analysis above, not that reuse has been
demonstrated. Per the directive's own Phase 20 instruction ("Demonstrate
through architecture/interfaces how another business domain could plug
into the kernel. Do NOT build another domain now"), this document *is*
that demonstration — a second domain wiring in its own risk rules, its own
RAG corpus, its own deploy target, and its own invariants while reusing
the event ledger, hash-binding, capability-dispatch, and reasoning-gateway
mechanisms unchanged is a concrete, evidenced claim, not a speculative one.
