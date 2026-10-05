# Agentic Software Delivery System

A production-deployed agentic AI delivery platform that I build and operate
myself, running against a real Java 21 / Spring Boot application. It is my
own system, not an employer's product.

The platform takes a natural-language change request, investigates the real
repository, proposes a change, verifies it with real compile and test runs,
deploys it, and checks production afterwards. Every step and every model
call is written to a durable event ledger with real token counts and cost.

Public site: <https://agentic-platform-backend-production.up.railway.app>

## One approval story

The public pages, this file and the code tell the same story, and tests hold
them to it (`agent/test_public_surface_gate.py`, `e2e/copy-contract.spec.js`).

- **A deterministic policy, not the model, decides what may run.**
  `agent/risk_policy.py` classifies the raw requirement text before any model
  is called: a keyword denylist plus a size heuristic, in plain Python. The
  model never decides its own authority.
- **Inside a narrow pre-declared band, the Workbench applies a small change
  with no approval.** A short, low-risk request is implemented, verified and
  deployed automatically. There is no approval event on that path, and no
  model call anywhere on it either; the change comes from a fixed catalogue.
- **Outside that band, nothing is applied until a person approves.** The
  approval is bound by hash to the exact file and content that was approved
  (`agent/write_tools.py`), re-checked at apply time, and the approve step is
  not a tool the model can call.
- **Triage always stops at a human approval.** The Incident Triage Lab
  reproduces a contained defect, has the model diagnose and patch it, runs
  the real tests, and then waits for an admin-authenticated approval that is
  checked server-side (`agent/triage_execution.py`).

So it is false to say every change needs a person, and equally false to say
the model approves itself. Both claims are forbidden by the tests above.

## What is in the repository

| Path | What it is |
|---|---|
| `agent/` | The Python platform: web server, Workbench pipeline, risk policy, write boundary, durable LangGraph workflow, RAG index, MCP server, event ledger, and the test suites next to each module. |
| `agent/web/` | The public pages. The proof-rows block inside `home.html` and `proof.html` is generated from the registry below (`agent/build_proof_surface.py`) and must not be hand-edited; the rest of each page is ordinary copy. |
| `app/` | The Customer application the platform operates against: Java 21, Spring Boot, REST and GraphQL, PostgreSQL with versioned migrations. |
| `services/` | A six-service decomposition of the same domain, with a real multi-service test tier. |
| `docs/PORTFOLIO_CAPABILITIES.yaml` | The registry that is the authority for what is true about each capability. |
| `docs/PUBLIC_PROOF_SURFACE.yaml` | The registry that is the authority for what is shown in public, mechanically unable to claim above the verification level recorded for it. |
| `e2e/` | Playwright specs against the real rendered pages. |
| `docs/` | Decisions, lessons, state, backlog, retros, evidence packs. Start at `START_HERE.md`. |

## Public pages

| Route | Purpose |
|---|---|
| `/` | Home: who I am, three proof points, and the evidence rows. |
| `/proof` | The evidence index: every public claim with its status, evidence and limitation. |
| `/workbench` | Submit a real requirement and watch the pipeline run. |
| `/triage` | The Incident Triage Lab, with its human approval step. |
| `/ask-codebase` | Grounded questions against the real repository. |
| `/standing-interview` | Interview questions answered from my own recorded engineering knowledge. |
| `/showcase/senior-java-ai-transformation` | How the work maps to a Senior Backend / Agentic AI role. |
| `/usage` | This platform's own metered spend. Not any employer's telemetry. |
| `/case-study/durable-agent` | The crash-recovery case study. |

## Running it locally

Prerequisites: Java 21 (the Maven Wrapper fetches Maven itself), Python
3.10+, Node for the browser tests, and an Anthropic API key in `agent/.env`
as `ANTHROPIC_API_KEY`. That file is ignored by git and must never be
committed.

The Customer application:

```bash
cd app
./mvnw spring-boot:run        # Windows: .\mvnw.cmd spring-boot:run
```

It starts on `http://localhost:8080`.

The platform:

```bash
cd agent
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..
python agent/web_server.py    # http://127.0.0.1:8420
```

## Verifying it

```bash
python agent/ci_python_tests.py        # release health: the blocking Python suites
python agent/proof_registry.py         # the registry's structural checks
python agent/build_proof_surface.py --check   # generated pages match the registry
npx playwright test                    # browser specs against a local server
```

Release health prints pass, fail and skip counts separately. A skipped
mandatory gate is reported as unverified, never as passed.

## What this does not claim

One model provider. Local cosine retrieval over small corpora, not a managed
vector database. Deployment is scripted but triggered by hand. The
multi-model cross-review experiment is paused with its product thesis
unproven, and is presented only as a negative result. The full list of
limitations, one per capability, is on `/proof`.
