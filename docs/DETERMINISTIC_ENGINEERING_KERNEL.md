# Deterministic Engineering Kernel

Phase 2 of the Base Architecture V3 directive. Per Phase 1's Intelligence
Placement Audit (`docs/INTELLIGENCE_PLACEMENT_V3.md`), this codebase's real
deterministic modules already implement most of the directive's conceptual
`kernel/` responsibilities — the honest, evidence-grounded output of this
phase is a **mapping of what already exists, plus an explicit REJECT
decision on physically moving files into a `kernel/`/`domains/` folder
split right now**, not a speculative redesign. This follows the directive's
own instruction: "Choose repository structure based on actual code" and its
Phase 24 Technology Decision Rule ("what happens if we do nothing?").

## The mapping (existing module → kernel responsibility)

| Kernel concept | Real implementation today | Domain-coupled? |
|---|---|---|
| **workflow** | `agent/web_server.py`'s `Run` class + `Run.set_status()`/`KNOWN_RUN_STATES` (added this phase) | No — generic run-lifecycle tracking, no Customer-App concepts |
| **policy** | `agent/risk_policy.py` (text-level authorization), `agent/change_risk.py` (blast-radius rules), `agent/backend_planning.py::classify_backend_routing` (pre-retrieval authority decision) | Partially — rule tables reference this project's file paths, but the *mechanism* (ordered rule table, fail-closed-to-UNKNOWN) is generic |
| **invariants** | Business rules enforced in compiled Java (`ContractPlanService`'s idempotency check, `WorkspaceAccessGuard`, `SecurityConfig`'s route matrix) + Python boundary checks (`write_tools.py`'s `ALLOWED_WRITE_PREFIXES`) | Yes, by nature — invariants are inherently domain-specific; the *pattern* (compiled/DB-enforced, not prompt-enforced) is what's reusable |
| **evidence** | `agent/event_ledger.py` (structured envelope: event type, source, payload, timestamps), `agent/verify_change.py`'s evidence JSON, `backend_planning.py::check_groundedness` | No — the event ledger schema has zero Customer-App-specific columns |
| **provenance** | `agent/triage_promotion.py`'s SHA256 hash binding (candidate → approval → promotion, TOCTOU-safe), `agent/write_tools.py`'s approve/apply hash binding | No — hash-equality-based identity binding is fully generic |
| **capabilities** | `agent/execution_tools.py::_EXECUTION_DISPATCH` (an exact, auditable 4-key dict — `approve_edit`/`reject_edit` provably absent), `agent/mcp_server.py`'s read-only tool exposure | No — dict-membership-based capability control is generic |
| **sensors** | `agent/build_tools.py` (compile/test), `agent/triage_execution.py::_isolated_compile_java_candidate` (now compile+test, this phase), CI (`.github/workflows/ci.yml`) | Partially — the *shape* (subprocess argv-list, no shell, structured pass/fail + evidence) is generic; what gets compiled is Java-specific |
| **knowledge** | `agent/tools.py` (read-only repo access + path security), `agent/rag_index.py`/`agent/backend_rag_index.py` (embeddings) | Partially — `tools.py`'s path-security boundary (`_resolve_safe_path`) is fully generic; the RAG corpus content is project-specific |
| **execution** | `agent/demo_execution.py`/`agent/backend_execution.py` (isolated-workspace clone → commit → push → deploy, timestamp-verified) | Partially — the isolated-workspace/dedicated-branch pattern is generic; the deploy target (Railway/this app) is not |
| **learning** | `docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml` (structured defect schema with `recurrence_status`/`analysis_confidence`), `docs/LESSONS.md` | No — the schema itself is generic; the entries are this project's history |
| **reasoning** | 4 direct Anthropic call sites (`agent/main.py`, `agent/agent_loop.py`, `agent/backend_planning.py`, `agent/triage_execution.py`) — see Phase 3 | This is the one area Phase 1's audit and this phase found genuinely under-consolidated |

## Decision: do NOT physically restructure into `kernel/`/`domains/` folders now

Per the directive's own Phase 24 rule, answered honestly:

1. **What problem exists?** No real one observed yet. Every deterministic
   module above already has a single, clear owner and is independently
   tested; nothing is duplicated across "domains" because there is only
   one domain (the Customer App / Agentic Delivery platform itself).
2. **Is it important?** Not urgently — this is a solo, single-domain
   project. The value of a `kernel/` split is proven by a *second* domain
   successfully reusing it, which doesn't exist and the directive
   explicitly says not to build ("Do NOT build another business domain
   now").
3. **Can existing code solve it reliably?** Yes — every module above
   already works, is tested, and (per the table) most are already
   domain-agnostic in their actual logic even without being physically
   relocated.
4. **Would moving files provide stronger deterministic intelligence?**
   No — a directory move changes nothing about correctness; it only
   changes import paths, at real risk (this is a live, working,
   recruiter-visible production system — see `docs/RECOVERY.md`,
   `pre-architecture-v3-baseline` rollback tag) for zero behavioral gain.
5. **What happens if we do nothing?** Nothing bad. The code remains
   exactly as reusable in principle as it would be after a rename — reuse
   is a property of *coupling*, not of *directory name*. A future second
   domain (if one is ever built) can import these modules from their
   current locations exactly as easily as from a `kernel/` package; the
   directory name is a cosmetic decision that can be made at that time,
   with real evidence from an actual second consumer, not speculatively.

**Conclusion: REJECT the physical `kernel/`/`domains/` folder split for
now.** The reusable architecture the directive asks for already exists in
substance (see the mapping table); formalizing it into a literal package
boundary is deferred until a real second consumer exists to validate the
boundary against, per the directive's own Phase 20 instruction
("Demonstrate through architecture/interfaces how another business domain
could plug into the kernel. Do NOT build another domain now.").

## What Phase 2 actually changes

Nothing in code. This document is the Phase 2 deliverable: a named,
evidence-grounded map from the directive's abstract kernel vocabulary to
this project's real, already-tested modules, so a future session (or a
genuine second domain) has a concrete starting point instead of a blank
page. See `docs/INTELLIGENCE_PLACEMENT_V3.md` for the underlying
per-capability evidence this table is built from, and
`docs/REUSABLE_PLATFORM_BOUNDARIES.md` (to be written) for a closer look
at exactly which of the above modules have zero Customer-App-specific
dependencies today, as verified evidence for a future reuse decision.
