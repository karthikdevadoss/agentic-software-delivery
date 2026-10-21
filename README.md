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
can propose; it has no way to approve. On the public Workbench page, the
visitor is the person who decides: one click runs a supported change at once on
a sandbox copy of the Customer App and shows the result. There is no approval
queue for visitors, and a visitor click never changes the live app or the repo.
It makes no model call ($0.00) and is rate limited per IP and per day
(`agent/workbench_budget.py`). Only the owner can deploy a change to the live
Customer App.

**A tool-calling loop.** `agent/agent_loop.py` runs Claude with a small set of
repository tools (list, read, search, semantic search), with a cap on tool
calls and tokens per run. Every model call goes through one gateway,
`agent/reasoning_gateway.py`, which checks what the call is for and has an
off switch; a test fails the build if code calls the SDK directly.

**An MCP server with read-only tools.** `agent/mcp_server.py` exposes the same
repository tools over the Model Context Protocol, so other AI clients can use
them. All of them are read-only and share the same path checks as the agent.

**Retrieval with evals.** The repository and a curated set of project docs are
embedded locally and searched by cosine similarity (`agent/rag_index.py`,
`agent/backend_rag_index.py`, `agent/ask_codebase.py`). Quality is measured
against a hand-labelled question set by `agent/eval_runner.py`: Recall@3
0.833 and MRR 0.868, shown on `/eval`. CI fails the build if a score drops
below its recorded threshold.

**A LangGraph workflow that survives a crash.** `agent/durable_workflow.py`
runs a software change as a graph — investigate, propose, wait for approval,
apply, compile, test, verify — and checkpoints each step to Postgres. It can
pause for a person, survive a restart and resume without repeating the apply
step. The crash drill is written up at `/case-study/durable-agent`.

**A Postgres ledger with versioned pricing.** Every meaningful step and every
model call is written to an event ledger (`agent/event_ledger.py`,
`infra/event-ledger/schema.sql`) with real token counts. Cost comes from
`agent/pricing_config.py`, where prices are dated entries that are added, never
edited, so an old run keeps the price that was true when it ran.

**The Java side.** `app/` is a Spring Boot 4 / Java 21 Customer App — REST and
GraphQL, Spring Security with JWT, Flyway on Postgres, Redis caching, and an
outbox for events. `services/` splits the same domain into microservices
(gateway, Eureka, customer, billing, metering, notification) with distributed
tracing and a multi-process test that starts them together.

## Pages

| Path | What it shows |
| --- | --- |
| `/` | Overview |
| `/workbench` | Pick a change and run it with one click on a sandbox copy of the Customer App |
| `/tokens` | Token X-ray: the same tasks done the wrong and the right way, measured in tokens and cost |
| `/triage` | A contained defect: reproduce, diagnose, patch, test, approve |
| `/ask-codebase` | Questions answered from retrieval over this repository |
| `/eval` | Retrieval and routing eval scores and CI status |
| `/recruiters` | What AI engineering job postings ask for, and where to check it here |
| `/interviewer` | A short brief for a technical interviewer |

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
cd agent && python eval_runner.py all   # retrieval and routing evals
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
