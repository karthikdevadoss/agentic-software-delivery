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

## Local Workbench execution engine + Cloudflare Quick Tunnel

- **NAME:** Local Starlette server (`agent/web_server.py`) + `cloudflared`
  Quick Tunnel.
- **PURPOSE:** Runs the Control Plane/Workbench/Dashboard/Sessions
  locally, optionally exposed publicly via an ephemeral tunnel for demos.
- **PROVIDER:** This laptop (server), Cloudflare (Quick Tunnel, free/
  account-less tier).
- **URL:** Local: `http://127.0.0.1:8420`. Last known public tunnel URL:
  `https://fallen-pest-ecology-walter.trycloudflare.com` — **EXPIRED**
  ("Unauthorized: Tunnel not found" as of this session).
- **STATUS:** CURRENT (local only) / **EXPIRED** (public tunnel)
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
