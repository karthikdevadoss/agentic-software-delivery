# Durable budgets, rate limits and the optional LiteLLM proxy

Branch `feat/durable-budgets-litellm`. Local/dev capability; **production
(Railway) is unchanged and nothing here is deployed.**

## 1. Durable budgets and rate limits

| Piece | File | Scope in the store | What it caps |
|---|---|---|---|
| Store | `agent/budget_store.py` | all | SQLite, atomic check-then-reserve (`BEGIN IMMEDIATE`, WAL) |
| Platform policy | `agent/gateway_budget.py` | `gateway` | daily $ cap, per-run $ cap, per-request $ cap, rate limit |
| Triage Lab | `agent/triage_budget.py` | `triage` | per-endpoint request counts, per visitor + global (unchanged semantics) |
| Standing Interview | `agent/si_budget.py` | `si` | per-endpoint answers/day, per visitor + global (unchanged semantics) |

**Enforcement point.** `reasoning_gateway.call()` reserves *before* the
provider is contacted. A refusal returns `model_called=False` and
`denial_reason="BUDGET_<STATUS>: ..."`. The reservation is the worst-case
estimate (input chars/3 at the input price + full `max_tokens` at the output
price; an unpriced model reserves a flat `GATEWAY_UNPRICED_RESERVE_USD`). It is
**settled to the measured cost** from the provider's usage on success, and
**left at the estimate if the call raises**, because a failed call can still be
billed.

**How they persist.** Every reservation is a row in
`budget_ledger` (`ts`, UTC `day`, `scope`, `visitor`, `run_id`, `usd`,
`settled`). Counts and sums are computed from rows, so there is no in-memory
counter to lose. Path: `BUDGET_DB_PATH`, default `agent/.budget/budget.sqlite3`
(gitignored). `agent/ci_python_tests.py` points it at a temp dir.

**One source of truth?** Two layers, deliberately, with separate scopes that
never share a counter: the endpoint policies answer "is this *visitor* being
fair / has this *page* hit its N per day" (request counts); the gateway answers
"has the *platform* spent / called too much" (dollars and rate). A Triage click
reserves in both; whichever limit is hit first refuses. The event ledger
(Postgres) stays the audit record of what was spent; it is not the enforcement
state because it is best-effort/spooled and cannot do a synchronous atomic
check without a network.

**Knobs** (malformed value → default, never a lifted cap; `0` refuses):
`GATEWAY_DAILY_USD_CAP` (5.00), `GATEWAY_PER_RUN_USD_CAP` (1.00),
`GATEWAY_PER_REQUEST_USD_CAP` (0.50), `GATEWAY_RATE_LIMIT_CALLS` (20),
`GATEWAY_RATE_WINDOW_SECONDS` (60), `GATEWAY_UNPRICED_RESERVE_USD` (0.05),
plus the existing `TRIAGE_*` variables. These defaults are **policy values, not
measured spend.**

**/usage.** A "Remaining budget" panel reads `GET /api/budget` (caps and counts
only, no visitor identities).

## 2. LiteLLM proxy option (off by default)

Files: `infra/litellm/config.yaml`, `infra/litellm/docker-compose.yml`,
`infra/litellm/.env.example`, `agent/litellm_route.py`.

Enable locally:

```bash
cd infra/litellm
cp .env.example .env          # set ANTHROPIC_API_KEY and LITELLM_MASTER_KEY (sk-...)
docker compose up -d          # proxy on 127.0.0.1:4000 only
export LITELLM_PROXY_URL=http://127.0.0.1:4000
export LITELLM_API_KEY=<same value as LITELLM_MASTER_KEY>
```

With `LITELLM_PROXY_URL` set, `reasoning_gateway` builds its Anthropic SDK client
with `base_url=<proxy>` (POST `<proxy>/v1/messages`), so calls never go to
`api.anthropic.com` from the gateway process; the Anthropic key lives only in
the proxy container. There is **no fallback**: a missing key or non-http URL is
a refusal, not a silent direct call. The budget gate runs first, so the proxy
sits behind the platform's caps. Unset the variable and today's direct path is
used. Provider stays Anthropic (`claude-sonnet-5`); the second route
`stub-echo` is a LiteLLM `mock_response` stub for a routing test, not a provider.

Verified: unit tests prove routing to a loopback stand-in proxy and the direct
path when disabled (no container needed in CI). Separately, once, on this
branch: real `litellm 1.110.2` loaded `config.yaml`, served `stub-echo`
through `/v1/messages`, and `reasoning_gateway.call(model="stub-echo")` reached
it. Not exercised: the compose file itself (no Docker in the authoring
environment), and any live Anthropic call through the proxy. The Anthropic SDK
2.12 sends the key as `Authorization: Bearer` when `base_url` is overridden;
LiteLLM accepts that. LiteLLM's mock route reports synthetic token usage.

## 3. Honest limits

- **Coverage:** only calls through `reasoning_gateway.call()` are capped. On this
  branch `agent_loop.py`, `backend_planning.py` and `main.py` still call
  Anthropic directly and are **not covered** until the separate migration PR
  lands. JD Match keeps its own in-process cooldown/daily cap (reset on
  restart, as its page says); its model calls are covered by the gateway cap.
- **Durable on one host's disk.** Railway without a persistent volume replaces
  the file on deploy; set `BUDGET_DB_PATH` to a mounted volume to get that
  durability. Separate replicas do not share counters. Postgres-backed
  `transaction()` is not built.
- **Dollars are estimates until settled** (worst-case reservations), and an
  unpriced model is a flat reserve. SI's `$0.023` per answer remains a measured
  average ($1.4353 / 63 requests, 2026-09-29), not a quote.
- `si_budget.check()` / `record_answer()` are separate transactions; concurrent
  requests can overshoot the SI count by the number in flight (the gateway cap
  is atomic and still applies).
- **Visitor key is a client-supplied header** (`X-Forwarded-For`) and can be
  spoofed; the global daily caps are what hold.
- **Local LiteLLM is a personal proxy**: one container, one master key, no HA,
  no per-team budgets, no SSO, no spend DB. It is not Kraken-scale and not a
  company gateway.
- No second production provider exists.
