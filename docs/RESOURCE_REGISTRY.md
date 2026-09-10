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

## Agentic Software Delivery platform backend (persistent cloud hosting)

- **NAME:** `agentic-platform-backend` — a Railway service running
  `agent/web_server.py` from a Docker image built from the repo-root
  `Dockerfile`. Runs Workbench/Dashboard/Usage/Learn/Profile (and the
  internal-only Control Plane at `/control-plane`) 24x7, independent of
  the creator's laptop.
- **PROVIDER:** Railway. Deliberately placed as a **second service inside
  the existing `agentic-delivery-events` project** (service ID
  `c69e2076-a9ae-458f-bda7-c601bcf739bd`), NOT a new project — the free
  plan's project-count limit was hit when creating a genuinely new
  project (`Free plan resource provision limit exceeded`, verified by
  trying), while adding a new *service* to an already-provisioned project
  was not blocked. The naming mismatch (platform backend living in the
  "events" project) is a known, deliberate tradeoff — not an accident.
- **PUBLIC URL (persistent, Railway-provided):**
  `https://agentic-platform-backend-production.up.railway.app`
- **STATUS:** LIVE — **verified publicly reachable, independent of any
  laptop**: `/`, `/workbench`, `/dashboard`, `/usage`, `/learn`,
  `/profile` all return real HTTP 200 pages with correct titles/nav
  through this exact URL; `/trainer`/`/sessions` return 308 redirects.
  The deployed backend independently confirmed reachable to the real
  event ledger (`/api/dashboard`'s `event_ledger.status` = `REACHABLE`,
  346 real events at verification time). A full real Workbench
  acceptance run (`Add a small "Powered by Agentic Delivery" footer line
  to the page`) was submitted and completed **through this public URL**,
  reaching `NO_CHANGE_NEEDED` (genuinely non-mutating — read-only
  repository investigation only, no compile/commit/deploy triggered).
- **RUNTIME CAPABILITY:** the image includes `git`, a JDK (for
  `app/mvnw`), and the Railway CLI (`v5.50.2`, statically-linked musl
  binary) — real infrastructure for the Workbench's full bounded-autonomy
  path (investigate → propose → apply → build/test → commit →
  deploy → verify), not just static page serving. `ANTHROPIC_API_KEY`
  and `EVENT_LEDGER_DATABASE_URL` are set as Railway service variables
  (never printed/logged/committed at any point — copied via a script that
  redirected values directly between `agent/.env` and `railway variable
  set --stdin`).
- **KNOWN GAP:** `railway up`/`railway status` from *inside* this
  container (the trainer's real auto-deploy-the-Customer-app step) has
  NOT been exercised — it needs its own `RAILWAY_TOKEN` (a
  project-scoped Railway token, confirmed as a real supported env var by
  extracting the literal string from the installed CLI binary itself),
  which requires generating a token from the Railway dashboard (a
  browser action, not available via any CLI subcommand as of CLI 5.50.2
  — confirmed by inspecting `railway --help`'s full command list). The
  acceptance test performed above deliberately used an
  already-satisfied requirement specifically so this gap didn't block
  proving the rest of the pipeline — a genuine code-change requirement
  would currently fail at the deploy step until `RAILWAY_TOKEN` is added.
- **LAST VERIFIED:** 2026-09-10
- **NOTES:** This supersedes the local-laptop + tunnel approach (both
  Cloudflare Quick Tunnel and `ngrok`) as the trainer/recruiter-facing
  URL — see docs/DECISIONS.md for the full detour history and why each
  was abandoned. **CANONICAL FINAL URL (not live yet):**
  `https://agentic.karthikdevadoss.com` — a CNAME record was generated
  and is ready (`agentic` → `r1bbjhwh.up.railway.app`, confirmed via
  `railway domain agentic.karthikdevadoss.com`) but NOT applied: adding
  it requires the creator's own action at wherever `karthikdevadoss.com`'s
  DNS is managed, which this session has no access to. Do not claim that
  domain is live until this entry is updated after the creator adds the
  CNAME and it verifies.
- **TARGET DOMAIN (not live yet):** `https://app.karthikdevadoss.com` for
  the Customer app — not touched this task, unchanged from prior status.

## Local Workbench execution engine (development/debug only)

- **NAME:** Local Starlette server (`agent/web_server.py`) run directly
  on the creator's laptop, `http://127.0.0.1:8420`.
- **PURPOSE:** Local development/debugging only. The public-facing
  deployment above is now the trainer/recruiter-facing surface — this
  local instance is no longer the primary way to reach the platform.
- **STATUS:** Available on demand (`python agent/web_server.py` from
  `agent/`), not continuously running.
- **NOTES:** Any earlier `ngrok`/Cloudflare Quick Tunnel processes
  fronting this local instance should be considered retired — the
  Railway deployment above is the durable answer to "one URL I can send
  my trainer," not a laptop-dependent tunnel.

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
