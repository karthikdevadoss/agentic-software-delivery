# Secrets Registry (metadata only — NEVER actual values)

This file records secret **names and purposes only**. No actual
credential, password, token, or key value may ever be written here or
anywhere in this repository. Real values live in `agent/.env`
(gitignored, confirmed via `.gitignore` and `git check-ignore`) or the
environment at runtime — never in Git history.

**SECRET MANAGER: NOT YET STANDARDIZED.** There is no dedicated remote
secret manager (e.g. a vault or cloud secrets service) in use today —
this is a tracked roadmap gap, not an oversight. See docs/ROADMAP.md.

## ANTHROPIC_API_KEY

- **PURPOSE:** Authenticates all Anthropic Claude API calls (agent
  reasoning, tool-calling, code proposals).
- **USED BY:** `agent/main.py`, and transitively every module that
  invokes `run_agent_loop` (`agent/agent_loop.py`,
  `agent/execution_agent.py`, `agent/web_server.py`).
- **STORED IN:** `agent/.env` locally (gitignored). No remote secret
  manager configured yet.
- **ENVIRONMENTS:** Local development only — the deployed Customer app
  (Railway) and the static Dashboard/Sessions site (Vercel) do not need
  or hold this key; only the local Workbench execution engine does.
- **NEVER LOG:** YES — `agent/tools.py`'s trace/observability layer is
  designed to never emit raw secrets (see docs/DECISIONS.md).
- **LAST VERIFIED/ROTATED:** Not tracked — no rotation process exists
  yet (roadmap gap).

## EVENT_LEDGER_DATABASE_URL

- **PURPOSE:** Connection string for the durable, append-only engineering
  event ledger (agent/event_ledger.py) — Postgres, `delivery_events` table.
  This is the P0 "no more lost engineering events" foundation: real
  Workbench run/tool/model/build/test/deploy events are write-through
  persisted here as they happen, not batched to run-end.
- **USED BY:** `agent/event_ledger.py` (all connect/insert/query
  functions), transitively `agent/web_server.py` (Run.emit() write-through
  wiring, metrics.py model-usage sink) and `agent/dashboard_data.py` (the
  live "event_ledger" proof key in `/api/dashboard`).
- **STORED IN:** `agent/.env` locally (gitignored). No remote secret
  manager configured yet (same gap as ANTHROPIC_API_KEY above).
- **ENVIRONMENTS:** Local development only — this connects to a Railway
  Postgres instance over its PUBLIC TCP PROXY (see docs/RESOURCE_REGISTRY.md)
  because the local Workbench execution engine runs on this laptop, not
  inside Railway's own private network.
- **NEVER LOG:** YES — never printed to any tool output or committed
  anywhere during this credential's creation; every script that touched it
  redirected raw output directly to a file and printed only confirmation
  messages, never the value.
- **LAST VERIFIED/ROTATED:** 2026-09-10 (created and connectivity-verified
  this session). No rotation process exists yet (same roadmap gap as
  ANTHROPIC_API_KEY).

## VOYAGE_API_KEY

- **PURPOSE:** Would authenticate Voyage AI's `voyage-code-4` embedding
  API, an alternative RAG embedding provider.
- **USED BY:** `agent/embeddings.py` (`_embed_voyage()`), only if
  `RAG_EMBEDDING_PROVIDER=voyage` is set.
- **STORED IN:** Not configured anywhere — this provider is implemented
  but currently unused; the key does not exist in any environment.
- **ENVIRONMENTS:** None (unused).
- **NEVER LOG:** YES (same trace discipline as above, untested since
  unused).
- **LAST VERIFIED/ROTATED:** N/A — never configured.

## Not a secret (listed here only to avoid confusion)

- `CLAUDE_MODEL` — optional config override for which Claude model to
  call (default `claude-sonnet-5`). Not sensitive; safe to log.
- `RAG_EMBEDDING_PROVIDER` — optional config selecting `local` (default)
  or `voyage`. Not sensitive; safe to log.

## Deployment-provider authentication (not app secrets)

- **Railway CLI** — authenticated via device-flow OAuth (`railway login`)
  on this laptop; no token is stored in this repository. Session-based,
  not an app-level secret.
- **Vercel CLI** — authenticated via an existing trusted session on this
  laptop; no token is stored in this repository.

Both of the above are **operator/deployment credentials**, distinct in
kind from application secrets like `ANTHROPIC_API_KEY` — they authenticate
*this laptop's* ability to deploy, not the running application itself.
Neither is currently backed by anything more durable than this laptop's
local CLI session state — a real gap if this laptop is lost (see
docs/RECOVERY.md).
