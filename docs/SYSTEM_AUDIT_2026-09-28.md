# Agentic Software Delivery System — Full System Audit

**Date:** 2026-09-28
**Audited at:** `master` @ `bac7cea` (= `origin/master`, 0 ahead / 0 behind)
**Auditor:** Claude Opus 5 session, read-only. No code, config, state document or
deployment was modified to produce this report.
**Status of this file:** UNTRACKED and UNCOMMITTED. It is the 8th untracked path in
a repository where the other 7 are deliberate. Commit it or delete it — do not let it
sit unexplained.

---

## 0. How to read this, and what it is worth

Every number and claim below carries the command that produced it. Where a claim comes
from a state document rather than from the running system, it says so. Where I did not
verify something, it says that too, rather than rounding up to "verified".

**What I actually executed:** filesystem/Git inspection, static parsing of the real
JSON/Python artifacts, and 10 live HTTPS requests against production.

**What I did NOT execute** (and therefore do not certify): the Python test suite, the
Maven suites, the Playwright E2E suite, `si_acceptance.py`, or any model call. Test
counts below are *static* counts of test methods in source, not a green run. Under this
project's own rule — SKIPPED is not PASSED — the test suite's current pass/fail state is
**UNVERIFIED IN THIS SESSION**. The last recorded green run (614 tests, 0 failures) is a
level-3 document claim, not something I observed.

---

## 1. System at a glance

| Dimension | Measured | Command |
|---|---|---|
| Tracked files | 685 | `git ls-files \| wc -l` |
| Java | 284 files | `git ls-files \| sed 's/.*\.//' \| sort \| uniq -c` |
| Python | 126 files | same |
| Markdown | 106 files | same |
| JavaScript | 33 files | same |
| Documents in `docs/` | 61 entries | `ls -1 docs/` |
| Python test modules | 53 | `ls agent/test_*.py` |
| Python test methods | 898 | `grep -rh "^    def test_" agent/test_*.py \| wc -l` |
| Java test classes | 58 | `find app services -name "*Test*.java"` |
| Java `@Test` methods | 307 | `grep -rh "@Test" app services --include=*.java` |
| Playwright specs | 13 | `ls e2e/*.spec.js` |
| Node frontend harnesses | 5 | `ls agent/test_*.js` |
| HTTP routes on the platform server | 62 (13 pages, 49 APIs) | route literals in `agent/web_server.py` |
| Event-ledger event types | 53 | `KNOWN_EVENT_TYPES`, `agent/event_ledger.py:89` |
| Knowledge domains | 31 | `agent/web/learn-tree.json` |
| Knowledge topics | 396 (427 nodes incl. domains) | same |

**Largest modules** (`wc -l`): `web_server.py` 2214 · `triage_execution.py` 1219 ·
`interview_topics.py` 1184 · `event_ledger.py` 1155 · `session_history.py` 975 ·
`build_learn_tree.py` 702 · `standing_interview.py` 652.

**Largest test modules**: `test_web_server.py` 1398 · `test_event_ledger.py` 948 ·
`test_triage_execution.py` 776 · `test_standing_interview.py` 743.

---

## 2. Architecture: two systems in one repository

This is the single most important structural fact and it is easy to miss.

**(a) The AI delivery platform** — `agent/`, `agent/web/`, `public-site/`.
Python. The product. A planner, a tool-using execution agent, an approval-gated write
boundary, an MCP adapter, three separate retrieval corpora, deterministic evals, a
durable Postgres event ledger, cost telemetry, and 13 browser surfaces.

**(b) The target application** — `app/`, `services/`.
Java 21 / Spring Boot 4.1.1 (`app/pom.xml:21`, `:10`). This is the *software the platform
does engineering work on*, not part of the platform. 121 Java files in `app/`, plus a
7-module decomposition:

| Service | Java files |
|---|---|
| billing-service | 51 |
| customer-service | 40 |
| notification-service | 26 |
| metering-service | 20 |
| api-gateway | 10 |
| legacy-billing-stub | 4 |
| eureka-server | 3 |

Both are exercised by one GitHub Actions pipeline (`.github/workflows/ci.yml`) with six
job groups: `backend-java`, `agentic-platform-python`, `agentic-platform-frontend`,
`microservices` (matrix over 6 services), `real-topology` (gating), `e2e-playwright`
(explicitly non-blocking).

---

## 3. The AI layer, component by component

This section is the heart of the audit: what AI machinery genuinely exists, with its real
parameters read out of the real source.

### 3.1 Model access

- **Model:** `claude-sonnet-5` — `DEFAULT_MODEL`, `agent/agent_loop.py:26`, overridable
  via `CLAUDE_MODEL`. 44 occurrences of the id across `agent/`.
- **Central Reasoning Gateway** (`agent/reasoning_gateway.py`, 210 LOC): Base
  Architecture V3 Phase 3. Phase 1's audit found 4 direct Anthropic call sites
  (`main.py`, `agent_loop.py`, `backend_planning.py`, `triage_execution.py`); the gateway
  is the single chokepoint in front of them, with an `llm_mode_disabled()` kill switch, an
  `ADVISORY_PURPOSES` allowlist, and an injectable `create_fn` so every path is testable
  without a network call.
- **Temperature:** never set anywhere. API default is used.
- **Extended thinking:** not requested, but *handled correctly* — `agent_loop.py:203-207`
  carries thinking blocks back into the next turn unmodified rather than filtering or
  reconstructing them, which is the documented correct behaviour for a tool-use loop.
  `reasoning_gateway.py:201` detects the "thinking ate the whole `max_tokens` budget"
  failure and reports it as such instead of as an empty answer.

### 3.2 Tool use / the agent loop

`agent/agent_loop.py` — V3 tool-using planner. Budgets: `MAX_TOOL_CALLS = 8`,
`MAX_TOKENS = 6000`.

Two things here are better than the common implementation:

1. **It gates on the presence of `tool_use` blocks, not on `stop_reason == "tool_use"`**
   (`:210-216`). A response truncated by `max_tokens` that still contains valid tool calls
   is still answered with `tool_result`, which is the correct protocol behaviour and a
   frequent source of silent breakage elsewhere.
2. **Budget exhaustion returns a `tool_result` saying so** (`:245`) rather than dropping
   the call — the model is told it ran out of budget instead of being left to hallucinate.

**Read-only tool surface** (`agent/tools.py`, 4 tools): `list_repository_files`,
`read_file`, `search_code`, `semantic_repository_search`. No shell, no writes, no symlink
following, no Git — repository-bounded by construction.

**Write/execute tool surface** (`agent/execution_tools.py`, 4 tools):
`propose_source_change`, `apply_approved_source_change`, `run_controlled_compile`,
`run_controlled_tests`. Composed *on top of* the read-only schemas, not duplicating them.

### 3.3 The write boundary (the strongest security control in the system)

`agent/write_tools.py:42-43`:

```
ALLOWED_WRITE_PREFIXES = ("app/src/main/java/", "app/src/test/java/",
                          "app/src/main/resources/static/")
ALLOWED_WRITE_EXTENSIONS = {".java", ".html"}
```

Three prefixes, two extensions, enforced at propose time and again at apply time. The
agent cannot write Python, cannot write config, cannot write to `agent/`, cannot write
outside `app/`. `agent/build_tools.py` is the same idea for execution: exactly two
possible operations (Maven compile, Maven test) selected by exact allowlist match, with no
path by which an arbitrary command string can reach `subprocess.run`.

This is genuine least-privilege, not a prompt instruction.

### 3.4 Retrieval: three separate corpora, deliberately not one

| Index | Path | Size | Chunking | Purpose |
|---|---|---|---|---|
| Whole-repo | `agent/.rag_index/index.json` | 13.1 MB | fixed window, `CHUNK_LINES=40`, `CHUNK_OVERLAP=8` | "what in this repository is relevant" — V3 CLI agent |
| Curated backend | `agent/.backend_rag_index/index.json` | 3.6 MB | **semantic**: Java class/method-aware, Markdown heading-aware, JSON catalogue-aware; `MAX_CHUNK_LINES=120`, sub-window 40/8 | backend requirement planning + `/ask-codebase` |
| Standing Interview | `agent/.si_corpus/corpus.json` | 3.6 MB, **361 chunks, 8 books** | built by `scripts/build_si_corpus.py` | first-person interview answers |

The whole-repo index is **incremental**: unchanged files reuse their chunk vectors
verbatim (zero re-embedding), and a `chunking_version` change forces a full rebuild so the
index can never silently mix two chunking strategies. That is a real correctness control,
not an optimisation.

Retrieval is in-memory numpy cosine similarity over JSON. There is no vector database, and
the code says so explicitly rather than implying scale it does not have.

### 3.5 Embeddings

`agent/embeddings.py` — pluggable provider behind `embed_texts()` / `embed_query()`.

- **Active:** `BAAI/bge-small-en-v1.5` via `fastembed` (ONNX, no PyTorch, no API key).
  Confirmed live in production: `/api/standing-interview/status` returns
  `"model_id":"local:BAAI/bge-small-en-v1.5"`.
- **Coded but blocked:** `voyage-code-4` (`VOYAGE_MODEL`), requires `VOYAGE_API_KEY`.
  Fails closed with a clear error rather than silently degrading.
- The model id is embedded in the index fingerprint, so switching providers invalidates
  the index instead of mixing vector spaces.

### 3.6 MCP

`agent/mcp_server.py` — official `modelcontextprotocol/python-sdk`, spec 2026-07-28,
exposing 5 tools (the 4 read-only repository tools plus `search_project_context`).

Two *distinct* verifications exist, which is unusually rigorous:
- `mcp_demo.py` — in-process SDK `Client`, proves the protocol itself.
- `mcp_demo_http.py` — spawns `mcp_server.py` as a **real separate OS process on a real
  localhost port**, proving the streamable-HTTP transport specifically.

MCP Resources, Prompts and Authorization are **not used**, and are labelled as such.

### 3.7 The Standing Interview pipeline (the newest and most gated surface)

`agent/standing_interview.py`, 652 LOC. Constants read from source:

```
TOP_K               = 6
GROUNDING_THRESHOLD = 0.50
MAX_ANSWER_TOKENS   = 1000
MAX_LIMIT_SENTENCES = 2
```

Pipeline: **route** (`_AI_HINTS` / `_BACKEND_HINTS` regex) → **retrieve 6 chunks**,
employer-balanced via `_balance_by_employer` when no employer is named → **grounding
threshold 0.50** → **generate** → **first-sentence decline gate** (`DECLINE_MARKERS`) →
**deterministic leak scan** (`_LEAK_PATTERNS`, refuses immediately) → **voice gate**
(`_VOICE_BANNED`, one corrective retry, then `voice_rejected`) → answer or refusal.

Every refusal and every "Dissatisfied" click is written to the durable event ledger as
`standing_interview_refusal` / `standing_interview_dissatisfied` — two types, not one,
because a coverage gap and a wrong answer are different defects. Read them with
`agent/si_review.py`.

**Live verification performed this session:**

```
GET /api/standing-interview/status
{"loaded":true,"chunks":361,"model_id":"local:BAAI/bge-small-en-v1.5",
 "books":["BOOK-01",...,"BOOK-08"]}
```

All 13 page routes returned 200 (`/sessions` 308 → redirect, expected).

### 3.8 Deterministic gates in front of the model

This is the system's defining design choice: **the LLM never decides its own authority.**

| Gate | Module | What it decides | When |
|---|---|---|---|
| Risk policy | `risk_policy.py` | BLOCK / allow, by keyword + complexity on raw requirement text | *before* the agent loop starts |
| Change risk | `change_risk.py` | risk + blast radius from changed file paths | after a diff exists |
| Write boundary | `write_tools.py` | path prefix + extension | propose and apply |
| Build boundary | `build_tools.py` | exact operation allowlist | every compile/test |
| STATIC tier | `static_gate.py` | file modes, shebangs, XML/HTML comment defects — zero LLM | CI, blocking |
| Config drift | `check_config_drift.py` | a property in one Spring profile missing from another | CI, blocking |
| Environment preflight | `environment_preflight.py` | JDK version vs `pom.xml` target, fail-closed | before any compile |
| Secret scan | `secret_scan.py` | credential patterns in tracked+staged files, never prints the value | on demand |

`risk_policy.py` is deliberately over-inclusive on BLOCK: a keyword list plus word-count
complexity buckets. Crude, and honest about being crude.

### 3.9 Evals (measurement, kept separate from tests)

`agent/evals/` — version-controlled, hand-labelled, gating in CI
(`"RAG/MCP retrieval + routing evals (must meet recorded thresholds)"`):

| Dataset | Cases | Measures |
|---|---|---|
| `retrieval_dataset.json` | 12 | retrieval quality, 3 metrics |
| `routing_dataset.json` | 14 | deterministic tool routing across 3 routes |
| `agent_decision_dataset.json` | 6 | the real agent's *decisions* (investigate/plan/propose/refuse/write) |

The third is the interesting one: its `scoring_authority` is **"DETERMINISTIC ONLY for
approval/write/unsafe-action/tool-usage/policy-bypass"** — the safety-relevant dimensions
are scored by code, not by a model judging itself.

There is no LLM-as-judge anywhere in the system. That is a deliberate, documented absence.

### 3.10 Observability

`agent/event_ledger.py`, 1155 LOC, append-only Postgres (`infra/event-ledger/schema.sql`),
write-through as events happen rather than batched to run-end. **53 event types** across
the full delivery lifecycle: requirement → risk → run/stage → model call/usage/error →
retrieval → tool call → change proposed/authorized/applied → build → test → commit →
deploy → production verification → transport degraded/recovered → human input/decision →
correction/regression → Standing Interview review → Claude Code dev session.

Two genuinely distinct sources share the ledger: `source="workbench"`
(`activity_class=PRODUCT_RUNTIME`) and `source="claude_code"`
(`activity_class=PRODUCT_DEVELOPMENT`, via `agent/claude_code_hook.py` wired to real
Claude Code hook events).

Note the comment block just after `KNOWN_EVENT_TYPES` recording a real deadlock incident: a
non-reentrant `threading.Lock` caused `sync_spool()` to hang forever on its first
`_insert()` in any fresh process. That class of write-up — the real incident, in the code,
next to the fix — recurs throughout this codebase and is one of its genuine strengths.

### 3.11 Cost and economics

`agent/pricing_config.py` — versioned, dated, sourced:

```
version        anthropic-2026-09-10-v1
effective_date 2026-09-10
source         https://claude.com/pricing
claude-sonnet-5  input $2.00/MTok  output $10.00/MTok
                 cache_write $2.50/MTok  cache_read $0.20/MTok
```

Stored per-token so call sites never convert units. When no verified pricing entry exists
it returns `{"available": False, "reason": ...}` — it does **not** fabricate a zero.
`agent/estimation.py` prefers comparable *real historical runs* over a formula and labels
everything ESTIMATED. Cache token fields are captured from every response
(`agent_loop.py:198-199`, `backend_planning.py:294-295`).

---

## 4. AI topic coverage map

Source: `agent/web/learn-tree.json` (the single canonical knowledge model; both the
interactive Learn UI and the PDF book read it — there is no second knowledge source).

**Totals in the tree as it stands:** 31 domains · 396 topics · 427 nodes.
Of the 396 topics, **19 carry the full 17-section interview schema**, 4 carry 16 sections,
and 158 carry 7 sections. 156 topics have 3 sections or fewer, 14 have none.

### 4.1 The 16 AI domains and every subtopic

Status labels shown are the `status` field as committed. See Finding 2 — several are
contradicted by this repository's own artifacts.

**AI Foundations (6):** Artificial Intelligence · Machine Learning · Deep Learning ·
Neural Networks · Generative AI · Foundation Models

**LLMs (10):** Transformer · Attention · Token · Tokenization · Context Window ·
Inference · Sampling · Temperature · Top-p · Hallucination

**Prompt & Context Engineering (7):** System Prompt · User Prompt · Prompt Engineering ·
Context Engineering · Structured Output · Few-shot Prompting · Context Management

**Embeddings & Retrieval (8):** Embeddings *(runtime verified)* · Semantic Search
*(runtime verified)* · Vector Database *(not used)* · Similarity · Chunking · Metadata ·
Hybrid Search · Reranking *(not used)*

**RAG (7):** Retrieval-Augmented Generation *(runtime verified)* · Indexing · Retrieval
*(runtime verified)* · Grounding · Context Injection · RAG Evaluation *(marked not used —
see Finding 2)* · RAG Failure Modes

**Tool Use (5):** Function Calling *(runtime verified)* · Tool Calling *(runtime
verified)* · Tool Schemas · Tool Authorization *(runtime verified)* · Tool Result Handling
*(runtime verified)*

**MCP (9):** MCP Architecture *(runtime verified)* · Clients · Servers · Tools *(tested)* ·
Resources *(not used)* · Prompts *(not used)* · Transports · Authorization *(not used)* ·
Current Protocol Concepts

**Agents (12):** Agent Loop *(runtime verified)* · Planning · Task Decomposition · State ·
Memory *(runtime verified)* · Tool Selection *(runtime verified)* · Self-correction *(not
used)* · Reflection · Multi-agent Systems *(not used)* · Human-in-the-loop *(production
verified)* · Human-on-the-loop *(runtime verified)* · Autonomy

**Agentic Software Engineering (8):** Coding Agents *(runtime verified)* · Repository
Understanding *(runtime verified)* · Impact Analysis · Agentic SDLC · Verification Gates
*(production verified)* · Risk-based Autonomy *(production verified)* · Human Authority ·
Production Verification *(production verified)*

**Evals / Quality (8):** LLM Evaluation · Agent Evaluation · Deterministic Tests *(runtime
verified)* · Regression Evals *(runtime verified)* · Groundedness *(runtime verified)* ·
Reliability · First-pass Success · Failure Trajectories *(runtime verified)*

**AI Security / Governance (9):** Prompt Injection · Tool Abuse · Least Privilege
*(runtime verified)* · Sandboxing · Secret Protection *(production verified)* · Data
Classification · RAG Poisoning · Approval Boundaries *(production verified)* · AI
Governance

**AI Observability (9):** AI Tracing *(runtime verified)* · Events *(production verified)* ·
Spans *(not used)* · Model Usage *(runtime verified)* · Token Usage *(runtime verified)* ·
Latency · Human Wait Time · Tool Telemetry *(runtime verified)* · Agent Telemetry *(runtime
verified)*

**Model Engineering (8):** Model Selection · Model Routing *(not used)* · Fine-tuning *(not
used)* · Preference Data *(not used)* · Evaluation Dataset · Training Dataset ·
Distillation · Proprietary Models *(not used)*

**AI Economics (6):** Token Cost *(marked not used — see Finding 2)* · Latency · Cost per
Verified Change · Human Minutes per Change · Model Efficiency · Caching *(marked not
used)*

**AI Delivery Engineering (15):** Event Ledger *(production verified)* · Append-only Data ·
Idempotency · Retry · Durable Spool · PostgreSQL *(production verified)* · TCP Proxy ·
Private Networking · SSE · Polling Fallback *(production verified)* · State Machines ·
Deployment Verification *(production verified)* · Git Evidence · CI/CD *(marked not used —
see Finding 2)* · Production Observability

**AI-Assisted Software Engineering (21 branches, 46 nodes)** — the largest AI domain:
Acceptance Contracts · Independent QA Evaluation · Designing for UNKNOWN · Skills and
Subagents · AI Token/Cost Economics · Requirements with AI · Context Engineering ·
Repository Grounding · Prompting · Agent Loops · Deterministic Gates · Testing/Evals ·
Deployment · Debugging · Multi-Agent Systems · Progressive Autonomy · Continuous Learning ·
AI Context Engineering & Tokenization · AI Agent Tool-Calling Loops, plus two sub-branches:

- **Human Role, Approval, Interruption (7):** Human Owns · AI May Execute Within Authority ·
  Approval · Interruption · Clarification · Escalation
- **AI Failure Modes (18):** Where AI Guesses and Why It Fails · Hallucinated APIs / Wrong
  Framework Assumptions · False Completion / Self-Evaluation Optimism · Deployment Races ·
  Environment Mismatch · Weak Tests · Authorization Assumptions · Incorrect Cost Estimates ·
  Multi-Agent Coordination Errors · Ambiguous Requirements · Missing Context · Stale
  Documentation · Long-Task Drift · Context Loss · Scope Explosion · Security Blind Spots ·
  Prompt Injection · Tool-Output Misunderstanding

**Assessment of AI coverage:** the *breadth* is genuinely comprehensive — 14 pure-AI
domains plus 2 applied ones cover essentially the full surface an AI-engineering
interviewer would probe, and the "AI Failure Modes" branch in particular is material most
portfolios do not have at all. The *depth* is uneven: only 19 of 396 topics carry the full
17-section schema, and the pure-AI domains are largely 1–7 section topics while the
deepest treatment (17 sections) sits mostly on classical backend topics (JVM GC, Hibernate
N+1, Kafka delivery semantics, transactions/MVCC, HikariCP). Only two AI topics —
`ai-context-engineering-tokenization` and `ai-agent-tool-calling-loops-coding-agents` —
reach 17 sections.

### 4.2 The 15 engineering domains (for completeness)

System Design (15 branches / **99 nodes** — by far the largest) · Java Core (13) · JVM
Internals (8) · Spring/Spring Boot (11) · Database/SQL/JPA (12) · REST/API Design (8) ·
Microservices & Distributed Systems (10) · Redis/Caching (6) · Kafka/EDA (9) · Application
Security (9) · Testing/Quality (6) · Observability/Production (10) · Cloud/DevOps (10) ·
Architecture & Delivery Leadership (11) · Testing/Quality Deep Dive (1).

---

## 5. Process and governance machinery

Not usually part of a system audit, but here it is a real subsystem with real code.

- **`.claude/rules/`** — 2 auto-loading rule files: `sprint-process.md` (loads on
  backlog/retro/sprint files), `java-and-services-change.md` (loads on `app/`, `services/`,
  `*.java`, `pom.xml`). Path-scoped so a Python session pays nothing for Java rules.
- **`.claude/agents/`** — 2 subagents: `qa-evaluator` (independent verification; the
  implementer may not certify its own production success) and `shiva` (zero-context
  adversarial review).
- **`.claude/skills/`** — 8: `requirement-contract`, `implement-small-change`,
  `test-change`, `testing-strategy`, `production-verify`, `incident-analysis`,
  `ai-feature-evaluation`, `devils-advocate`.
- **Deterministic process scripts** — `backlog.py` (computes size-vs-actual verdicts; the
  agent may interpret the table but may not produce the classification),
  `check_id_available.py` (a real Sprint 4 ID collision between concurrent forks),
  `detect_scope_conflicts.py`, `verify_sprint_merged.py`, `verify_tracking_updated.py`,
  `state_brief.py` (402 KB of state documents → ~15 KB view, writes nothing).
- **`verify_change.py`** (424 LOC) — inspects the real diff, classifies risk, prints the
  test plan *before* running anything, executes it, writes machine-readable evidence JSON,
  returns a real exit code. `aggregate_evidence.py` rolls those up across runs.

---

## 6. Findings

Ordered by how much they matter. Each states how it was verified.

### Finding 1 — The Learn tree publishes metrics that its own builder contradicts by 5× · MEDIUM · verified

`agent/web/learn-tree.json` carries a `metrics` block that is **stale relative to the
`domains` array in the same file**. Recomputing with the builder's own `count_nodes()`
over the committed file:

| Metric | Committed (displayed) | Recomputed by `count_nodes()` |
|---|---|---|
| `total_deep_topics` | **45** | **240** |
| `current_project_experience_topics` | 86 | 154 |
| `learned_understood_topics` | 153 | 199 |
| `planned_not_experienced_topics` | 3 | 1 |
| `total_reference_topics` | 396 | 396 ✓ |
| `total_domains` | 31 | 31 ✓ |

The file records `generated_at_utc: 2026-09-12` and `git_commit: cfc467e`, but the tree
content was edited in **four later commits** (`16e033b`, `3b0336c`, `f5fc65b`, `dec763b` —
all "author deep interview content"). The metrics were never regenerated.

**This is user-visible.** `agent/web/learn.js:343-344` and `agent/learn_pdf.py:322-323`
both render `"{total_domains} domains · {total_reference_topics} reference topics ·
{total_deep_topics} deep evidence-backed topics"`. The live Learn page and the downloadable
PDF book therefore both understate the work by a factor of five.

Note separately that `deep` is defined as `len(sections) >= 4`, which is a generous bar.
The "45 deep 17-part-schema topics" phrasing in `PROJECT_STATE.json`'s `current_version`
conflates two different things: **19** topics actually carry 17 sections; **240** carry ≥4.
Neither number is 45.

*Verify:* `python -c "import json; d=json.load(open('agent/web/learn-tree.json')); print(d['metrics'])"`
then recompute with `build_learn_tree.count_nodes(d['domains'])`.

### Finding 2 — Knowledge content asserts absences this repository disproves · MEDIUM · verified

Three `status`/overview claims in the shipped Learn tree are contradicted by artifacts in
this same repository:

1. **`ci-cd`** appears **three times** with three different classifications
   (`CURRENT_PROJECT_EXPERIENCE`, `PLANNED_NOT_EXPERIENCED`, `status: NOT USED`) and its
   overviews say *"not yet implemented in this project"* and *"this project currently
   deploys manually (railway up) rather than via an automated pipeline."* But
   `.github/workflows/ci.yml` runs six job groups on every push and pull request. The
   *deploy* half of the claim is fair; the *CI* half is false. `docs/PROJECT_STATUS.md`
   corrected exactly this claim on 2026-09-26 ("the stale list was actively misleading a
   fresh reader") — the correction never reached the Learn tree.
2. **`token-cost`** is `status: NOT USED` while classified `CURRENT_PROJECT_EXPERIENCE`,
   and its own overview describes precisely what `pricing_config.py` implements.
3. **`rag-evaluation`** is `status: NOT USED` while classified `CURRENT_PROJECT_EXPERIENCE`
   — but `agent/eval_runner.py` plus a 12-case labelled retrieval dataset run as a
   **gating** CI step.

Root cause is structural, not a typo: nodes carry **two independent** labelling fields
(`status` on 127 nodes, `experience_classification` on 385) with no rule reconciling them,
so the same topic can say both "I do this" and "not used".

*Why it matters here specifically:* this content is interview material. Saying "no CI/CD"
in an interview while the repository has a six-job pipeline is a worse outcome than
saying nothing.

### Finding 3 — 68 cross-links in the Learn UI can resolve to the wrong topic · MEDIUM · verified

`agent/web/learn.js:64-83` resolves `related` links with `findBySlugAnywhere()` /
`pathToSlugAnywhere()` — a **depth-first search returning the first match**. But
`dedupe_slugs()` (`build_learn_tree.py`) only dedupes **siblings**, not the whole tree.

Result: 427 nodes carry only 402 distinct slugs. **19 slugs are duplicated** across
unrelated domains — `retry` ×4, `idempotency` ×3, `production-verification` ×3, `ci-cd` ×3,
`latency` ×3, plus `memory`, `indexing`, `caching`, `concurrency`, `consistency`,
`authorization`, `least-privilege`, `observability`, `event-ledger`, `context-engineering`,
`multi-agent-systems`, `prompt-injection`, `reliability`, `timeout` ×2 each.

**68 `related` links point at one of those ambiguous slugs.** Concretely, a reader in the
RAG domain clicking `indexing` can land on *database B-tree indexing* (System Design →
Databases) instead of *RAG indexing*; `memory` can send an Agents reader to *JVM memory*;
`latency` exists in Performance, Observability and AI Economics.

*Verify:* the duplicate census and the 68 affected links are both reproducible by walking
`learn-tree.json` and counting slugs — see §7.

### Finding 4 — A third of the Python tests never run in CI · MEDIUM · documented, but unguarded

`agent/ci_python_tests.py` splits 53 test modules deliberately and honestly:

| Tier | Modules | Test methods | Gates CI? |
|---|---|---|---|
| HERMETIC | 41 | **597** | yes, blocking |
| LIVE_INFRA | 10 | **301** | **no** |
| Source-modules-that-look-like-tests | 2 | 0 | excluded on purpose |

The excluded 10 include the three largest suites in the project:
`test_web_server` (76 methods), `test_triage_execution` (60), `test_event_ledger` (42),
`test_session_history` (37), `test_claude_code_hook` (26), `test_learn_pdf` (22).

Each exclusion has a real, stated reason (needs live Postgres, spawns a real server, hits
live Railway, needs a JDK). The design is honest, and `MIN_EXPECTED_TESTS = 520` guards
against silent collapse of the hermetic tier. **But nothing in the repository records when
the 301 excluded tests last passed, or requires them to be run before a release.** Under
this project's own "SKIPPED is not PASSED" rule, the web server, event ledger and triage
engine — three of its most load-bearing components — are permanently in the skipped column
as far as any automated gate is concerned.

### Finding 5 — Interview content states a Java version the build contradicts · LOW · verified

`agent/interview_topics.py:172` — *"Java 17 and 21 (both LTS) are the current mainstream
production baselines; **this project's own app runs Java 17.**"*

`app/pom.xml:21` — `<java.version>21</java.version>`.

Line 207 of the same file correctly says Spring Boot 4.1.1. The Dockerfile comment records
the real production bug that forced the JDK 17 → 21 move ("this image previously installed
openjdk-17-jdk-headless via apt, but app/pom.xml's `<java.version>` was…"). The narrative
text was never updated after that fix.

### Finding 6 — Prompt caching is priced and measured, but never requested · LOW · verified

`grep -rn "cache_control" agent/ --include=*.py` returns exactly **one** hit, and it is a
*comment* in `pricing_config.py:23` noting that no `cache_control` is configured anywhere.

Meanwhile `pricing_config.py` carries cache-write and cache-read prices, and
`agent_loop.py:198-199` / `backend_planning.py:294-295` faithfully record
`cache_creation_input_tokens` / `cache_read_input_tokens` from every response.

So the system can *measure* cache economics but never *asks* for caching. Given that this
project's own recorded cost incident was driven by repeated large cache-read overhead, the
one lever most directly connected to that incident is unexercised in the platform's own
agent loop. Not a defect — the loop is short-lived and caching may genuinely not pay — but
the asymmetry between "fully instrumented" and "never enabled" is worth a deliberate
decision rather than an accident.

### Finding 7 — `PROJECT_STATE.json` staleness banner is a benign self-reference · INFORMATIONAL

`state_brief.py` reports the state doc 1 commit behind HEAD
(`last_verified_code_commit: afb2d9b` vs HEAD `bac7cea`). `bac7cea` is the Sprint 12 retro
commit, docs-only (`ACTION_QUEUE.json`, `BACKLOG.json`, `LESSONS.md`, `RETRO_LOG.md`,
`PROJECT_STATE.json` — no code). A commit cannot stamp its own hash, so this off-by-one is
structural. Correctly left alone; the banner is the only signal that would ever catch a
*real* drift.

### What is genuinely strong

Stated plainly, because an audit that only lists faults misrepresents the system.

1. **Authority is deterministic, never delegated to the model.** Risk classification,
   write scope, build operations, and the safety-relevant eval dimensions are all decided
   by code. The write boundary — 3 path prefixes, 2 extensions, checked twice — is real
   least-privilege.
2. **Incidents are recorded where they recur.** The `event_ledger` deadlock, the
   `railway up` / `.gitignore` interaction, the apt JDK 17 discovery, the false-green
   `unittest discover`, the Sprint 4 ID collision — each is written next to the code that
   fixes it, not filed in a forgotten postmortem.
3. **Absences are labelled.** `vector-database`, `reranking`, `model-routing`,
   `fine-tuning`, MCP Resources/Prompts/Auth, LLM-as-judge — all explicitly "not used"
   rather than implied. The codebase is notably free of capability inflation.
4. **Evals are separated from tests** and the safety dimensions are scored
   deterministically.
5. **A single knowledge source.** The Learn UI and the PDF book read one file. The three
   RAG corpora are separate *by design*, each with a stated reason, not by accident.

---

## 7. Reproducing every number in this report

```bash
# Inventory
git ls-files | wc -l
git ls-files | sed 's/.*\.//' | sort | uniq -c | sort -rn

# Tests, static
grep -rh "^    def test_" agent/test_*.py | wc -l          # 898
grep -rh "@Test" app services --include=*.java | wc -l     # 307

# CI-blocking vs excluded split
python - <<'PY'
import re, pathlib, importlib.util, sys
sys.path.insert(0,'agent')
s=importlib.util.spec_from_file_location('ci','agent/ci_python_tests.py')
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
cnt=lambda mod: len(re.findall(r'^    def test_',(pathlib.Path('agent')/f'{mod}.py').read_text(encoding='utf-8'),re.M))
print('hermetic', sum(map(cnt,m.HERMETIC_MODULES)), 'live-infra', sum(map(cnt,m.LIVE_INFRA_MODULES)))
PY

# Finding 1 — metrics vs recomputed metrics
cd agent && python -c "
import json,importlib.util
s=importlib.util.spec_from_file_location('blt','build_learn_tree.py')
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
d=json.load(open('web/learn-tree.json',encoding='utf-8'))
print('committed :',d['metrics'])
print('recomputed:',m.count_nodes(d['domains']))"

# Finding 3 — duplicate slugs and ambiguous related-links
python -c "
import json,collections
d=json.load(open('agent/web/learn-tree.json',encoding='utf-8'))
c=collections.Counter(); ns=[]
def r(n):
    c[n['slug']]+=1; ns.append(n)
    for k in n.get('children') or []: r(k)
[r(x) for x in d['domains']]
dups={k for k,v in c.items() if v>1}
print('dup slugs:',len(dups),'ambiguous related-links:',
      sum(1 for n in ns for x in (n.get('related') or []) if x in dups))"

# Finding 5 / 6
grep -n "runs Java 17" agent/interview_topics.py ; grep -n "<java.version>" app/pom.xml
grep -rn "cache_control" agent/ --include=*.py

# Live production (what I actually ran)
B=https://agentic-platform-backend-production.up.railway.app
for p in / /standing-interview /dashboard /workbench /learn /ask-codebase /usage /triage; do
  echo "$(curl -s -o /dev/null -w '%{http_code}' --max-time 25 "$B$p")  $p"; done
curl -s "$B/api/standing-interview/status"
```

---

## 8. What this audit did not cover

Named so the gaps are not mistaken for clean results.

- **No suite was executed.** Python, Maven, Playwright, `si_acceptance.py` — all
  static-counted only. Current pass/fail state is unverified.
- **No model call was made.** Answer *quality* on the Standing Interview is unassessed;
  only that it is loaded, has 361 chunks, and returns 200.
- **The private repository was not read.** Strategy, model roles, the eight books and the
  artifact build chain live in `karthik-ai-context` and are out of scope here.
- **No security testing.** `docs/OWASP_TOP_10_SELF_ASSESSMENT.md` and
  `docs/STATIC_SECURITY_SUPPLY_CHAIN_EVALUATION.md` were not re-verified; the
  write-boundary assessment above is a code read, not a penetration test.
- **The Java/microservices layer was inventoried, not reviewed.** 284 Java files were
  counted and their modules mapped; no correctness review was performed.
- **Findings 1–3 were not independently evaluated.** They are reproducible from the
  commands in §7, but this is a single agent's report and per this project's own rule the
  implementer does not get the last word.

---

*Produced read-only at `bac7cea`. No file in the repository was modified to create it.*
