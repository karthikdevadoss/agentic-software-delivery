# Resource Registry (non-secret)

Canonical registry of operational resources. **Never place actual
credentials/passwords/tokens here** — see docs/SECRETS_REGISTRY.md for
secret *names* only. Every entry's `LAST VERIFIED` date is when the
`STATUS` was actually checked, not when the entry was written — treat an
old date as due for re-verification, not as current truth.

## Git repository

- **NAME:** agentic-software-delivery (local repo name)
- **PURPOSE:** Source of truth for all code, docs, and durable state.
- **PROVIDER:** Local Git only.
- **REMOTE:** **NONE CONFIGURED** — `git remote -v` returns empty.
- **DEFAULT BRANCH:** `master`
- **STATUS:** CURRENT (local), **NOT DURABLE** (no remote)
- **LAST VERIFIED:** 2026-09-10
- **NOTES:** This is the single most important gap this registry records.
  All commits exist only on this laptop until a remote is configured and
  pushed to. See docs/PROJECT_STATE.json's `next_action` for current status.

## Existing personal portfolio site

- **NAME:** karthikdevadoss.com
- **PURPOSE:** Creator's existing personal/portfolio site — predates this
  project.
- **PROVIDER:** Unknown hosting (not this project's Vercel account, not
  managed by this repository).
- **URL:** https://karthikdevadoss.com
- **STATUS:** CURRENT — HTTP 200 confirmed.
- **LAST VERIFIED:** 2026-09-10
- **NOTES:** **Protected** — do not modify without a separate explicit
  task (see docs/COMPANY_VISION.md). May contain older AI-related claims
  needing a future credibility review (see docs/IDEAS.md).

## Agentic Delivery public evidence site (Dashboard + Sessions snapshot)

- **NAME:** agentic-software-delivery (Vercel project)
- **PURPOSE:** Public static snapshot of the Dashboard and Sessions
  surfaces.
- **PROVIDER:** Vercel, team `karthikdkas-projects`.
- **ENVIRONMENT:** Production.
- **URL:** https://agentic-software-delivery.vercel.app
- **STATUS:** CURRENT — confirmed reachable this session.
- **LAST VERIFIED:** 2026-09-10
- **SECRET NAMES REQUIRED:** none known (static site, no server secrets).
- **NOTES:** Static snapshot only — does not auto-update without a
  redeploy (see docs/PROJECT_STATE.json `next_phase`). Separate Vercel
  project from `karthikdevadoss.com`; that existing personal site was not
  touched.

## Actual Customer (target) application

- **NAME:** agentic-delivery-customer-app
- **PURPOSE:** The real Spring Boot target application the Workbench
  proposes and verifies changes against.
- **PROVIDER:** Railway, project ID `e19ceaff-846f-4d4a-b840-ce1248dd3325`,
  environment ID `4cdb03ff-1557-46d0-b0af-0a92457785ac`.
- **ENVIRONMENT:** Production (Railway's only configured environment for
  this project).
- **URL:** https://agentic-delivery-customer-app-production.up.railway.app
- **STATUS:** CURRENT — confirmed `Online` and HTTP 200 this session.
- **LAST VERIFIED:** 2026-09-10
- **SECRET NAMES REQUIRED:** none known beyond Railway's own CLI
  authentication (device-flow, not stored in this repo).
- **NOTES:** Storage is H2 in-memory — customer data resets on every
  redeploy. `server.port=${PORT:8080}` is required for Railway's dynamic
  port assignment (see docs/DECISIONS.md).

## Durable engineering event ledger (Railway PostgreSQL)

- **NAME:** agentic-delivery-events (Railway project), service `Postgres`
- **PURPOSE:** Real, append-only, remote durable storage for observable
  Agentic Software Delivery activity (`delivery_events` table) — the P0
  "no more lost engineering events" foundation. Kept in its OWN Railway
  project, architecturally separate from `agentic-delivery-customer-app`
  (our product's infra vs. the Customer target application).
- **PROVIDER:** Railway, project ID `fda41d23-8c0d-4419-9139-1744e109dd61`,
  environment ID `677ce73d-7341-498a-a0f4-d74afff8c68c` (production),
  service ID `382d39f3-ce91-4269-a760-0c5154a66835`.
- **IMAGE / VOLUME:** `ghcr.io/railwayapp-templates/postgres-ssl:18`,
  volume `postgres-volume` (500MB capacity), region `iad`.
- **CONNECTIVITY:** Railway's default `DATABASE_URL`/`PGHOST` resolve to
  `postgres.railway.internal` — reachable only from inside Railway's own
  private network, NOT from this laptop (where the Workbench execution
  engine actually runs). Solved with a public TCP proxy:
  `shortline.proxy.rlwy.net:51211` → forwards to the service's port 5432.
  This host:port is a non-secret network location; the credentials that
  complete the connection string are in `agent/.env` only (see
  docs/SECRETS_REGISTRY.md's `EVENT_LEDGER_DATABASE_URL`).
- **STATUS:** CURRENT — `Online`, real connectivity verified from this
  laptop (`SELECT version()` returned `PostgreSQL 18.6`), real write/read
  round-trips proven (agent/test_event_ledger.py, 14/14 passing against
  this live instance), 59 real events persisted as of last verification
  (14 from historical backfill of agent/web_run_history.jsonl + live
  write-through events from this session's own work).
- **LAST VERIFIED:** 2026-09-10
- **SECRET NAMES REQUIRED:** `EVENT_LEDGER_DATABASE_URL` — see
  docs/SECRETS_REGISTRY.md.
- **BACKUP STATUS:** Point-in-time recovery (PITR) — **DISABLED** (`railway
  postgres pitr status` confirmed: status disabled, bucket not wired).
  Left disabled deliberately: enabling it provisions billed cloud storage,
  a cost/production decision requiring explicit approval, not something to
  auto-enable. A manual, on-demand portable logical backup exists instead
  (`agent/event_ledger_backup.py` — dumps every row of `delivery_events` to
  a local gitignored JSONL file via the same connection; proven live, 59/59
  rows exported). **A restore has NOT been tested** — per CLAUDE.md, a
  backup is not proven recovery until a restore drill actually happens.
- **NOTES:** `pg_dump`/Postgres client tools are not installed on this
  laptop (only the `psycopg2-binary` Python driver) — the portable backup
  above is a row-level JSON dump via the existing connection, not a true
  `pg_dump` archive. Sufficient to prove exportability; not equivalent to
  Railway-native PITR for production-grade recovery guarantees.

## Local Workbench execution engine + Cloudflare Quick Tunnel

- **NAME:** Local Starlette server (`agent/web_server.py`) + `cloudflared`
  Quick Tunnel.
- **PURPOSE:** Runs Workbench/Dashboard/Usage/Learn/Profile (and the
  internal-only Control Plane at `/control-plane`) locally, optionally
  exposed publicly via an ephemeral tunnel for demos.
- **PROVIDER:** This laptop (server), Cloudflare (Quick Tunnel, free/
  account-less tier).
- **URL:** Local: `http://127.0.0.1:8420` — **CURRENT, fully verified**
  (all 6 public routes return HTTP 200, `/trainer` and `/sessions` return
  308 redirects to `/workbench`/`/usage`). Latest attempted public tunnel
  URL: `https://construct-limousines-venues-hats.trycloudflare.com` —
  **UNCONFIRMED**. `cloudflared` itself reported a successful tunnel
  registration with Cloudflare's edge (`location=txl01`), but the
  hostname did not resolve in DNS after ~10+ minutes across 3 separate
  tunnel creation attempts, confirmed via a direct query to Cloudflare's
  own authoritative resolver (1.1.1.1 DoH), which returned NXDOMAIN with
  a cached negative TTL. This looks like a genuine, transient issue with
  the free/account-less Quick Tunnel DNS provisioning path at the time
  of this session, not a code defect in this project — the identical
  symptom (successful registration, unresolvable hostname) occurred on
  all 3 attempts. **The URL above may or may not become reachable** —
  worth a direct check before relying on it; a fresh
  `cloudflared tunnel --url http://127.0.0.1:8420` attempt (ideally at a
  different time) is the standard recovery step, same as any expired
  Quick Tunnel.
- **STATUS:** CURRENT (local only, fully verified) / **UNCONFIRMED**
  (public tunnel — see above, distinct from the previously EXPIRED one)
- **LAST VERIFIED:** 2026-09-10
- **NOTES:** Quick Tunnel URLs are inherently ephemeral and change on
  every `cloudflared` restart — this is expected behavior, not a defect
  (see docs/PROJECT_STATE.json `open_defects`). A fresh tunnel run is
  needed before the next public Workbench demo. Planned permanent
  replacement: `agentic.karthikdevadoss.com` (see docs/COMPANY_VISION.md)
  — **NOT LIVE**, do not claim otherwise until this entry is updated.

## Model providers actually used

- **NAME:** Anthropic Claude API
- **PURPOSE:** All agent reasoning/tool-calling (planning, investigation,
  code proposals).
- **PROVIDER:** Anthropic.
- **MODEL:** `claude-sonnet-5` (configurable via `CLAUDE_MODEL` env var,
  see `agent/agent_loop.py`).
- **STATUS:** CURRENT — real API calls made and token-usage-verified this
  session (see docs/PROJECT_STATE.json `session_intelligence_mvp`).
- **LAST VERIFIED:** 2026-09-10
- **SECRET NAMES REQUIRED:** `ANTHROPIC_API_KEY` — see docs/SECRETS_REGISTRY.md.

## RAG embedding model

- **NAME:** fastembed local embedding model
- **PURPOSE:** Local semantic repository search, no API key required.
- **PROVIDER:** Local (ONNX runtime via the `fastembed` package), model
  `BAAI/bge-small-en-v1.5`.
- **STATUS:** CURRENT — 21 files / 56 chunks indexed as of last rebuild
  (`agent/.rag_index/index.json`, gitignored, derived data).
- **LAST VERIFIED:** 2026-09-09 (per docs/PROJECT_STATE.json's dashboard
  evidence entry).
- **NOTES:** Voyage AI `voyage-code-4` is implemented as an alternative
  provider (`agent/embeddings.py`) but unusable without `VOYAGE_API_KEY`
  — not currently used.

## Deployment/runtime providers summary

- **Vercel** — static Dashboard/Sessions snapshot hosting (see above).
- **Railway** — actual Customer app hosting (see above).
- **Cloudflare** — ephemeral local-dev tunnel only (see above), not a
  production hosting provider for this project.

## Planned (not yet live) canonical domains

- `https://agentic.karthikdevadoss.com` — planned flagship platform
  domain (Workbench `/`, Dashboard `/dashboard`, Usage `/usage`, Learn
  `/learn`). **PLANNED, NOT LIVE.**
- `https://app.karthikdevadoss.com` — planned Customer app domain.
  **PLANNED, NOT LIVE.**
