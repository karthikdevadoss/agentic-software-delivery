# OpenTelemetry tracing (Python agent platform)

Local/dev tracing, not a production APM install. The Java Customer App's
existing Brave tracing is untouched.

## What is a span
| Span | Where | Key attributes |
|---|---|---|
| `gateway.model_call` | `reasoning_gateway.call()` (every call, incl. denials) | `purpose`, `model`, `gateway.outcome` (ok/denied/error), `llm.input_tokens`, `llm.output_tokens`, `llm.cost_usd` (only when pricing is known), `llm.duration_ms` |
| `retrieval.semantic_search` | `backend_rag_index.semantic_search` (so `ask()` too) | `top_k`, `retrieval.hit_count`, `query.length`, `query.sha256_12` (never the raw query or doc text) |
| `approval.gate` | `execution_tools.traced_approval` (+ mock-run gate) | `edit_id`, `binding_hash` (path+content sha256), `approval.decision` (approved/rejected/error) |

`run_id` is attached to every span when bound (`tracing.bind_run_id`; the web
server binds it per agent run). Nested spans share a trace id.
`agent_loop.py` and `backend_planning.py` now route through
`reasoning_gateway.converse()`, so their model calls also emit `gateway.model_call`
spans. Still not instrumented: tool calls and ledger writes.

## See traces
- Console: `OTEL_TRACES_CONSOLE=1 python agent/web_server.py` (spans printed to stdout).
- In-memory: `GET /traces/<run_id>` returns that run's spans as JSON (process-local, lost on restart).
- OTLP/HTTP: `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` (standard OTel env vars apply).
  Local Jaeger: `docker compose -f docker-compose.otel.yml up`, then open http://localhost:16686.
  (The compose file is provided but was not run in the authoring environment.)
- Off: `OTEL_SDK_DISABLED=true` makes tracing a no-op.

## Datadog
OTLP is what Datadog (and Jaeger, Tempo, Honeycomb, ...) ingest, so this output
is Datadog-compatible in principle. This repo includes no Datadog account,
agent or API key, and nothing here has been tested against Datadog.

## Honest limits
- No `/metrics` endpoint; `metrics.py` remains in-memory.
- "timeout" approval decisions are only recorded if a prompt function raises
  `TimeoutError`; the web approval wait itself has no timeout today.
- The in-memory buffer is bounded and per-process.
