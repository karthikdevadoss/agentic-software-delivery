# Agentic Software Delivery

An AI agent that makes real changes to a real Java application, with a person
approving every change before it lands. It reads the codebase, proposes an
edit, waits for approval, then applies, tests, deploys and checks the result
in production.

Live: https://agentic-platform-backend-production.up.railway.app

## What is in here

**An agent that edits files only after a person approves.**
`agent/write_tools.py` splits a write into propose, approve and apply. A
proposed edit is a diff; nothing touches disk until a person approves it. The
approval stores a SHA-256 hash of the exact path and content, and apply checks
that hash again, so an edit that changes after approval is refused. The model
can propose; it has no way to approve. On the Workbench page, a change to the
Customer App is deployed only after the owner approves it.

**A tool-calling loop.** `agent/agent_loop.py` runs Claude with a small set of
repository tools (list, read, search, semantic search), with a cap on tool
calls and tokens per run. Every billed model call (`call()` and `converse()`)
goes through one gateway, `agent/reasoning_gateway.py`, which checks the
purpose, enforces durable SQLite budgets and rate limits (`agent/gateway_budget.py`,
`agent/budget_store.py`), supports an opt-in local LiteLLM proxy
(`agent/litellm_route.py`, `infra/litellm/`), and has an off switch; a test
fails the build if code calls the SDK directly.

**An MCP server with read-only tools and bearer auth.** `agent/mcp_server.py`
exposes the same repository tools over the Model Context Protocol (`stdio` and
Streamable HTTP), protected by bearer-token auth and per-tool scopes
(`agent/mcp_auth.py`, `docs/MCP_AUTH.md`). All tools are read-only and share
the same path checks as the agent.

**Retrieval with permission filtering and six eval suites.** The repository and
a curated set of project docs are embedded locally and searched by cosine
similarity (`agent/rag_index.py`, `agent/backend_rag_index.py`,
`agent/ask_codebase.py`), with code-enforced document access-level filtering
(`agent/permission_retrieval.py`) before ranking. Quality is measured across
six suites (retrieval Recall@3 0.833 / MRR 0.868, tool routing, security
routing, recorded agent decisions, permission filtering, and self-eval) by
`agent/eval_runner.py`, shown with run history and reproducibility hash on
`/eval`. CI fails the build if a score drops below its recorded threshold.

**A LangGraph workflow that survives a crash.** `agent/durable_workflow.py`
runs a software change as a graph — investigate, propose, wait for approval,
apply, compile, test, verify — and checkpoints each step to Postgres. It can
pause for a person, survive a restart and resume without repeating the apply
step. The crash drill is written up at `/case-study/durable-agent`.

**A Postgres ledger, OpenTelemetry spans, and typed triage.** Every meaningful
step and every model call is written to an event ledger (`agent/event_ledger.py`,
`infra/event-ledger/schema.sql`) with real token counts and versioned pricing
(`agent/pricing_config.py`). `agent/tracing.py` emits OpenTelemetry spans
(`gateway.model_call`, `retrieval.semantic_search`, `approval.gate`) readable
via `GET /traces/{run_id}` (`docs/OTEL.md`). Incident Triage Lab Scenario A
diagnoses run through a typed Pydantic AI slice (`agent/pydantic_ai_gateway.py`,
`docs/PYDANTIC_AI.md`), and `agent/self_eval.py` adds an opt-in pre-proposal
self-evaluation check.

**Local Django admin slice and Kubernetes manifests.** `django_admin/` provides
a small local read-only Django view over the Postgres event ledger. `infra/k8s/`
holds kubeconform-validated Kubernetes manifests (`docs/KUBERNETES.md`), paired
with `/healthz` and `/readyz` probes in `agent/web_server.py`.

**The Java side.** `app/` is a Spring Boot 4 / Java 21 Customer App — REST and
GraphQL, Spring Security with JWT, Flyway on Postgres, Redis caching, and an
outbox for events. `services/` splits the same domain into microservices
(gateway, Eureka, customer, billing, metering, notification) with distributed
tracing and a multi-process test that starts them together.

## Pages

| Path | What it shows |
| --- | --- |
| `/` | Overview |
| `/workbench` | Enter a requirement and watch the agent work; a recorded end-to-end run |
| `/triage` | A contained defect: reproduce, diagnose, patch, test, approve |
| `/ask-codebase` | Questions answered from permission-filtered retrieval over this repository |
| `/eval` | Six-suite eval scores, run history, reproducibility hash and CI status |
| `/usage` | Token/cost telemetry and remaining gateway budget |
| `/dashboard` | Live system capabilities, telemetry and verification snapshot |
| `/case-study/durable-agent` | Crash-recovery case study (LangGraph Postgres checkpointer) |
| `/recruiters` | What AI engineering job postings ask for, and where to check it here |
| `/interviewer` | A short brief for a technical interviewer |
| `/healthz`, `/readyz` | Liveness and readiness probes |
| `/traces/{run_id}` | In-memory OpenTelemetry spans for one run (JSON) |

## Running it locally

Python 3.12 and Java 21. The Maven wrapper downloads Maven on first use.

```bash
# Platform (needs ANTHROPIC_API_KEY in the environment or agent/.env)
pip install -r agent/requirements.txt
cd agent
python rag_index.py && python backend_rag_index.py   # build the local indexes once
python web_server.py                                 # http://127.0.0.1:8420

# Customer App
cd app
./mvnw spring-boot:run                               # http://localhost:8080
```

## Tests

```bash
cd agent && python ci_python_tests.py   # hermetic Python suite
cd agent && python eval_runner.py all   # all 6 eval suites against thresholds
pytest django_admin/tests/              # local read-only Django admin slice
cd agent && node test_nav_frontend.js && node test_dashboard_frontend.js && node test_usage_frontend.js && node test_trainer_frontend.js && node test_learn_frontend.js
cd app && ./mvnw test                   # Java, including Testcontainers Postgres
npx playwright test                     # browser tests; starts web_server.py
```

CI (`.github/workflows/ci.yml`) runs all of these on every push and pull
request to `master`, plus each microservice, the Postgres ledger tests and the
multi-process topology test.

## Docs

Start at `START_HERE.md`. Architecture decisions are in `docs/DECISIONS.md`,
lessons learned in `docs/LESSONS.md`, and the security model in
`docs/CAPABILITY_SECURITY_MODEL.md`.
