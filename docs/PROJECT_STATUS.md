# Project
Agentic Software Delivery System

# Final Goal
A full web-based Agentic Software Delivery Platform. Natural-language
software requirement
→ understand business intent
→ understand the actual application/repositories
→ retrieve relevant code/docs/architecture/engineering rules
→ plan impact
→ choose/delegate to appropriate agents
→ modify code
→ compile/build
→ run tests
→ inspect failures
→ self-correct
→ security/review checks
→ visually/runtime verify where possible
→ prepare PR
→ human approval only for meaningful decisions/risk/production actions
→ CI/CD/deployment
→ observe result
→ feed failures/learnings back into the system.

Human involvement moves toward product/business decisions, ambiguous
requirements, architecture/risk decisions, security-sensitive actions,
production approval, and final review where appropriate. Routine
investigation, implementation, testing, diagnosis, retry, verification,
and documentation/state updates increasingly move to agents.

# Current architecture

Customer target application:
- Spring Boot 4.1.1
- Java 17 target
- CustomerController
- CustomerService
- CustomerRepository
- Customer entity
- H2 in-memory DB
- browser UI at /
- GET /customers/{id}
- POST /customers
- Update Email deliberately not implemented yet

AI application:
- Python
- Anthropic Python SDK
- Claude Sonnet 5
- python-dotenv
- requirement file → Claude → implementation plan
- agent/main.py supports --mode v2 (static repo context) and --mode v3 (default: controlled tool-using agent, now including semantic retrieval)
- official-SDK-based MCP adapter (agent/mcp_server.py, `mcp` package) exposing the same read-only tools
- fastembed-based local, incremental RAG index (agent/rag_index.py, agent/embeddings.py)
- agent/metrics.py: minimal structured metrics hooks for tools/RAG

# Completed versions

V1:
- ticket-only planner
- real Anthropic API call works
- robust TextBlock extraction
- max_tokens 6000
- discovered that without repository context Claude guessed plausible but nonexistent components

V2:
- repository-aware planner
- agent/repo_context.py scans actual Java repository
- extracts real packages/classes/controller endpoints/service/repository/entity information
- includes docs/ARCHITECTURE.md
- includes docs/ENGINEERING_RULES.md
- excludes .env, .git, target/build outputs and secrets
- planner distinguishes:
  EXISTING
  REQUIRED
  RECOMMENDED
- Claude says "not found in repository context" instead of inventing components
- verified successfully against requirements/sample_requirement.txt
- still available today via: python agent/main.py <ticket> --mode v2

V3:
- controlled, read-only tool-using planning agent (agent/tools.py, agent/agent_loop.py)
- Claude decides what to inspect itself instead of receiving a prebuilt context bundle
- read-only tools: list_repository_files, read_file, search_code
- no write_file, no shell/subprocess, no Maven execution, no Git writes, no MCP
- thinking + tool_use round-tripping verified correct (response.content replayed
  to the API exactly as returned, never filtered/reordered/rebuilt) — covered by
  agent/test_agent_loop.py
- tool-call budget is strictly bounded and accurately named/logged
  (MAX_TOOL_CALLS = individual tool calls actually executed, never exceeded
  even when Claude requests multiple tools in one turn — excess calls in the
  same turn are skipped, not executed)
- forced finalization after the budget is reached clearly labels unverified
  claims as "unable to verify — tool budget exhausted"
- safe trace to stderr per tool call: tool name, sanitized input, success/error,
  result size, truncation flag only — never file contents or secrets
- security: path traversal (..) and absolute paths rejected, symlinks rejected
  outright (lexical-vs-resolved path comparison), .git/target/.mvn/build output
  excluded, .env and secret/credential-like filenames blocked, deterministic
  redaction of obvious credential-shaped values before any tool result reaches
  Claude or a log line
- is the default mode: python agent/main.py <ticket>  (equivalent to --mode v3)
- independently verified against requirements/sample_requirement.txt, including
  a live demonstration of the strict tool-call cap and the max_tokens
  stop-reason edge case being handled correctly

V3 + MCP + RAG foundations (this checkpoint):
- MCP adapter (agent/mcp_server.py) on the **official modelcontextprotocol/python-sdk**
  (`MCPServer`, not the standalone `fastmcp` package first tried this session —
  migrated after re-verifying the official SDK meets every requirement; see
  docs/DECISIONS.md) exposes list_repository_files, read_file, search_code, and
  semantic_repository_search — thin wrappers only, zero duplicated tool/security
  logic; RepoToolError is re-raised as the SDK's ToolError so the *specific*
  failure reason reaches the client, not a generic message
- stdio verified (local dev/demo + in-process Client testing); Streamable HTTP
  is coded/documented for a future hosted platform but not yet run over real
  HTTP (tracked as ACTION_QUEUE ACT-005)
- real local RAG: agent/embeddings.py (fastembed, no API key) + agent/rag_index.py
  (fixed-window chunking, single local JSON index, numpy cosine similarity) —
  verified with live queries returning genuinely relevant files without exact
  keyword overlap (e.g. "H2 database configuration" → application.properties)
- RAG indexing is **incremental** (resolves ACTION_QUEUE ACT-004): content-hash
  based, unchanged files reuse embeddings with zero re-embedding calls, changed/
  new files re-embedded, deleted files removed. Verified live: second build with
  no repo changes → 0 chunks embedded (44s → 72ms); a fixture add/modify/delete
  each triggered exactly the expected single-file change, then cleaned up
- semantic_repository_search added to tools.py as a 4th tool; agent_loop.py
  needed zero core-loop changes to support it — the direct V3 agent
  autonomously chose to call it before reading files, unprompted
- hybrid retrieval enforced: semantic results are explicitly candidates only;
  verified live that an unread semantic hit was reported as unverified rather
  than asserted as fact
- Voyage AI **voyage-code-4** (re-verified current, supersedes voyage-code-3)
  implemented as a swappable future embedding provider but not usable without
  VOYAGE_API_KEY (not configured — see docs/DECISIONS.md)
- 24 automated tests added (resolves ACTION_QUEUE ACT-003): agent/test_rag_index.py
  (13: exclusions, redaction, incremental reuse/change/delete, model/chunking
  mismatch, ranking, corrupt/missing index safety) + agent/test_mcp_server.py
  (7: discovery, invocation, unsafe-path rejection, semantic search, delegation-
  not-reimplementation, specific-error passthrough) + the 4 pre-existing
  agent/test_agent_loop.py tests — all passing
- agent/metrics.py: minimal in-memory structured event hooks (tool calls, RAG
  index builds, retrieval queries) wired into agent_loop.py/mcp_server.py/
  rag_index.py — for a future dashboard to consume without these modules being
  rewritten; verified real events are recorded with correct blocked_unsafe
  classification

V4 write/execution boundary foundation (committed: b724035, 30da5ee):
- agent/write_tools.py: strict propose -> approve -> apply flow (never direct
  writes). Reuses tools._resolve_safe_path for traversal/absolute/symlink/
  secret-name checks (no duplicated security policy); adds a write-only scope
  restriction to app/src/{main,test}/java `.java` files. 14 tests (1 skipped —
  symlink creation not permitted on this Windows account), all else passing
- agent/build_tools.py: allowlist-only compile/test tool (no shell,
  subprocess argv-list only). 6 unit tests (allowlist/injection rejection,
  no-shell confirmation) plus two real manual runs against the actual
  Customer app: `mvnw compile` succeeded (~15.5s), `mvnw test` succeeded
  (~10.9s, 0 tests exist yet)
- found and fixed a real security gap while testing: tools.py's secret-
  filename block only checked files that already existed, silently letting
  a **new** file named e.g. `credentials.java` through. Fixed at the shared
  boundary (benefits read tools + MCP too); all 24 prior tests re-confirmed
  passing after the fix
- write/build tools are not yet wired into the live Claude tool-calling
  loop — this checkpoint is the safety mechanism only, deliberately kept
  separate from first real usage
- Customer application source: unchanged (git diff empty); Update Email
  ticket: still not implemented
- approval-integrity gap found and fixed before commit: PendingEdit's
  `approved` was a plain boolean with nothing binding it to the exact
  (path, content) approved. Fixed via a sha256(path, content) hash captured
  at approval time and re-verified at apply time — target/content
  substitution after approval is now provably rejected

V4.1 live execution wiring (committed: e90eb0c):
- agent_loop.py made generic (tool_schemas/dispatch_fn/system_prompt_suffix
  params, all optional, defaulting to unchanged V3 behavior — re-verified
  identical --mode v2/v3 output)
- agent/execution_tools.py wires write_tools.py/build_tools.py into the live
  model-facing tool surface: propose_source_change, apply_approved_source_change,
  run_controlled_compile, run_controlled_tests. approve_edit/reject_edit are
  NOT tool schemas and NOT reachable via dispatch by any name — verified by
  exact set-membership checks (a substring check gave a false positive first;
  corrected, see LESSONS.md)
- agent/execution_agent.py: new CLI entry point (separate from main.py) for
  the write/build-capable agent
- fixed a real crash risk found via testing: input() raises EOFError in a
  non-interactive environment; the approval prompt now fails closed
  (rejects) instead of crashing or silently approving
- full regression: 60 tests total, 59 passed, 1 legitimate skip (Windows
  symlink creation privilege) — across test_agent_loop, test_rag_index,
  test_mcp_server, test_write_tools, test_build_tools, test_execution_tools
- **real live demonstration performed**: agent/execution_agent.py run for
  real (genuine Claude API call) against a safe demo ticket. The agent
  investigated the real repo, proposed exactly the one safe additive file
  requested, and correctly reported the rejection when the approval gate
  failed closed (no interactive terminal available in this environment) —
  unprompted, it stated "I cannot approve my own proposals and there is no
  mechanism to override that decision." The proposed file was confirmed
  never written to disk.
- **IMPORTANT — NOT YET PROVEN**: a genuinely human-approved end-to-end run
  (a real person typing "y" at a real terminal) has NOT happened yet. The
  live demo above proves the boundary holds when no human is present; it
  does not yet prove the full approve-and-apply path with a real approval.
  That is the explicit next action (see PROJECT_STATE.json).
- Customer application source: unchanged; Update Email: still not implemented

# Important learning
V2 is NOT RAG. V3's tool-calling alone was NOT RAG either.
V2 gathers selected repository context directly and injects it into the Claude prompt.
V3 (pre-RAG) let Claude request repository information on demand through
controlled, read-only tools instead of receiving a prebuilt bundle — client-side
tool use, not retrieval-augmented generation.
Real RAG now exists (fastembed + local index + semantic_repository_search),
but it is deliberately non-authoritative: it only narrows candidates, and the
agent still verifies actual current content via read_file/search_code before
relying on anything it returns.

# Browser visual baseline
- Find Customer works
- Create Customer works
- Update Email visibly says:
  "Not implemented yet — current agent ticket"
This is intentionally our before-state so future agent-driven code changes can be seen visually.

# Git history

Do not trust a hardcoded log snapshot here — it goes stale the moment a new
commit is made (this file can't know its own commit's hash in advance).
Run `git log --oneline` for the real current history. For the single fact
that matters most (the last commit containing verified code, as opposed to
docs-only commits), see `last_verified_code_commit` in
`docs/PROJECT_STATE.json`.

# Secrets
- agent/.env contains the Anthropic API key
- .env must NEVER be committed
- never print or copy the key into docs/logs/prompts
- old exposed key was rotated

# What does NOT exist yet
- MCP write/build/deploy tools (only read-only tools exposed, by design)
- MCP Streamable HTTP actually run (stdio is what's verified; HTTP path is coded/documented for a future hosted platform)
- production-grade code embeddings (Voyage AI implemented but blocked on VOYAGE_API_KEY; fastembed is what's actually verified)
- vector DB at scale (current index is local JSON + numpy, sized for this repo)
- a genuinely human-approved live execution cycle (V4.1 is wired into the live loop and proven to fail closed without a real human; a real person has not yet typed a real approval)
- any ticket actually implemented through V4/V4.1 (Update Email remains the planned first proof, after the human-approved cycle above)
- test agent
- reviewer agent
- autonomous file modification by our Python system (the mechanism exists behind an approval gate; nothing calls it autonomously)
- compile/test/self-correction loop (compile/test tool exists; no failure-feedback loop wired yet)
- GitHub PR automation
- CI/CD
- production hosting

# Exact next development step
Do NOT implement anything automatically after reading this file.

MCP + RAG foundations are now complete and verified (see above) — this did
not change the plan, only unblocked it: V4 can now use semantic_repository_search
and MCP-exposed tools without needing to build them from scratch.

Next planned phase:
V4 — controlled code-writing agent with a compile feedback loop.

Goal:
Let the agent propose an actual code change (starting with the Update Email
ticket) as a reviewable diff, apply it only under tight, explicit controls,
then run a controlled compile tool (no arbitrary shell/Maven access) to
verify the change and support self-correction — still with no autonomous
Git writes, PR creation, or deployment at this stage.

Next action (exact, small, first when resuming):
V4 and V4.1 are both committed and verified in isolation/simulation, but a
genuinely human-approved live run has NOT happened yet — the one live demo
this session correctly failed closed with no real terminal attached. First
action on return: personally run
`python agent/execution_agent.py <a safe fixture ticket>` at a real
interactive terminal, using a harmless fixture/test target (NOT Update
Email), and personally type the real approval. Prove: investigation ->
proposal -> pause -> real APPROVE -> exact approved change applies ->
compile/test -> verified result. Clean the fixture afterward. Only after
that proof should the next MVP be chosen — expected to be a small
browser-based control UI (Requirement -> Start -> status/evidence -> View
Diff -> Approve/Reject -> build/test -> result), then a small dashboard MVP
using only real telemetry — but re-prioritize if the live proof shows
otherwise.

# Useful commands

Run planner from project root (V3, default — controlled tool-using agent):
python agent/main.py requirements/sample_requirement.txt

Run the previous static-context planner for comparison:
python agent/main.py requirements/sample_requirement.txt --mode v2

Run V3 explicitly:
python agent/main.py requirements/sample_requirement.txt --mode v3

Run all automated tests (24 total: agent loop, RAG index, MCP server):
python -m unittest test_agent_loop test_rag_index test_mcp_server -v   (from the agent/ directory)

Build/rebuild the RAG index (incremental — safe and cheap to run any time, only changed/new/deleted content is re-embedded):
python agent/rag_index.py

Run the MCP server (stdio, for a local MCP client like Claude Desktop/Code):
python agent/mcp_server.py

Run the MCP discovery/invocation demo (independent client, in-process):
python agent/mcp_demo.py

Run Spring app:
cd app
.\mvnw.cmd spring-boot:run

Browser:
http://localhost:8080

Compile:
cd app
.\mvnw.cmd compile

# Working rule
For every meaningful phase:
implement → inspect diff → compile/test/run → verify → commit.
Never continue with a broken/uncommitted baseline.

# Current Reality (2026-09-10)

**Public Trainer Workbench run visibility:** resilient. SSE remains the
fast path; `agent/web/trainer.js` now always runs an HTTP poll of the
authoritative `GET /api/runs/{id}` state alongside it, so a silent
transport failure (proven real via the current Cloudflare Quick Tunnel —
see knowledge/sessions/2026-09-10-trainer-idempotency-fix.md) costs at
most one poll interval of UI latency, never total blindness. Verified:
focused Node test suite (14/14, including a test proven to actually
catch the duplicate-render class of bug) + full Python regression suite
(74/74, 1 pre-existing skip) + two live runs through the public tunnel
(one real fix deployed, one genuine no-op with zero mutation/commit/deploy).

**Still requires creator visual verification:** the actual rendered
browser experience (stage checklist, transport badge, timers) — verified
here via curl/Node-harness evidence, not a real browser.

**Railway deployment status truthfulness:** fixed and regression-protected.
`_run_controlled()` now decodes subprocess output as real UTF-8 (confirmed
byte-for-byte to be the actual defect — Railway's "●" bullet, U+25CF,
contains byte `0x8F`, undefined in cp1252). Deployment outcome is now
decided by `_decide_deployment_outcome()`: independent production
verification (a direct HTTP check of the real public URL) is the primary
evidence, Railway CLI polling only corroborates, and a genuine
`DEPLOYMENT_STATUS_UNKNOWN` outcome exists for when neither confirms
anything — never silently folded into FAILED. Verified: 9 new focused
tests (encoding + decision logic, each proven to fail against the old
behavior) + full regression suite (85/85 Python, 14/14 JS) + read-only
confirmation against real Railway status and the live production URL
(footer correctly reads "Powered by DOSS Agentic Delivery", matching the
creator's own visual confirmation). The historical false-FAILED run
(`trainer-e8ed222c`) is preserved exactly as recorded — it is evidence,
not an error to erase.

**Known open items:**
- The Cloudflare Quick Tunnel itself remains ephemeral (it expired again
  during this fix, unrelated to the code change) and ties the public
  Trainer URL to this laptop staying on — the polling-resilience fix
  makes the UI tolerant of a live tunnel dropping mid-stream, but doesn't
  make the tunnel durable or prevent it from expiring outright. A fresh
  `cloudflared` run is needed to get a new public URL; deliberately not
  done as part of this fix (out of scope).

# Current Reality (2026-09-10, continued): durable remote event ledger

**This repository is now public** on GitHub
(https://github.com/karthikdevadoss/agentic-software-delivery.git) — the
entire reachable Git history was scanned for real secrets first (zero
found), and local/remote HEAD equality was independently verified via a
fresh `git fetch`, not just trusted from the push output.

**P0 "no more lost engineering events" is implemented and verified.**
Before this work, every observable Workbench event (model calls, tool
calls, proposals, approvals, builds, tests, commits, deployments) lived
only in this process's memory (`Run.events`) and, at best, a single
end-of-run JSON line appended to a local, gitignored file
(`agent/web_run_history.jsonl`) — a crash mid-run, or losing this laptop,
meant losing everything about that run. That gap is now closed:

- **Real remote store:** Railway PostgreSQL, its own project
  (`agentic-delivery-events`, separate from the Customer app's Railway
  project), reached over a public TCP proxy since the default
  Railway-internal `DATABASE_URL` isn't reachable from this laptop. See
  docs/RESOURCE_REGISTRY.md.
- **Write-through, not batch-at-end:** `agent/event_ledger.py`'s
  `record_event()` is called the moment each event happens — wired
  directly into `web_server.py`'s `Run.emit()` (every stage/tool/
  proposal/approval/commit/deployment event) and into `metrics.py`'s real
  Anthropic API usage capture via a new `set_usage_sink()` hook.
- **Outage-safe:** if the remote insert fails for any reason, the event
  is appended to a local spool file instead of being dropped, and
  `sync_spool()` retries later — idempotently (`ON CONFLICT DO NOTHING`
  on `event_id`), so a retried sync never creates a duplicate row.
- **Historical evidence preserved, not overwritten:** `agent/
  web_run_history.jsonl` was left untouched; a one-time, safely re-runnable
  backfill imported all 15 of its existing rows into the ledger, clearly
  tagged as reconstructed history (`backfill_source=historical_backfill`),
  never mixed with live-observed events.
- **Genuinely tested, not just inserted once:** `agent/test_event_ledger.py`
  (14 tests) runs against the real live database — normal insert+query,
  event ordering, duplicate-retry idempotency, full run-trajectory
  reconstruction from `run_id` alone, real token-field round-trip, outage
  spooling, spool sync on recovery, pre-terminal-crash durability,
  historical-failure preservation, and secret redaction before storage
  (both remote and spool paths). Full regression suite re-run clean: 99
  Python tests (98 pass + 1 pre-existing platform-limited skip) + 14/14
  Node trainer-frontend tests.
- **Minimal live proof, not a redesign:** `/api/dashboard`'s existing JSON
  gained one small `event_ledger` key (status, event count, last event) —
  the Dashboard/Usage pages themselves were deliberately not touched.

**Explicitly NOT done, and why:**
- **PITR (point-in-time recovery) is disabled** on the event ledger's
  Postgres instance. Enabling it provisions billed cloud storage — a
  cost/production decision that needs explicit approval, not something to
  auto-enable. A manual, on-demand portable logical backup exists instead
  (`agent/event_ledger_backup.py`, proven live: 59/59 rows exported), but
  **no restore has been tested** — a backup is not proven recovery until
  a restore drill actually happens.
- **Claude Code development-activity capture (a distinct source from
  Workbench runtime telemetry) was investigated but not wired.** Hook
  event names were verified directly from the installed Claude Code
  v2.1.263 binary's own strings (not just documentation), confirming
  `SessionStart`/`SessionEnd` and others are genuinely supported. It was
  not implemented this task because a hook that performs real network I/O
  against a sometimes-slow TCP-proxied database connection would add
  latency/reliability risk to every future Claude Code session in this
  repo — a different risk class than this task's own scope. Documented as
  the next ingestion source; the event schema already accommodates it.

**Next single priority:** wire Dashboard and Usage's actual displayed data
to query the now-durable `delivery_events` table directly, replacing
their current reliance on the local JSONL log / in-memory process
counters — see `next_phase`/`next_action` in docs/PROJECT_STATE.json.

# Current Reality (2026-09-10, continued): Claude Code development telemetry + operator attention

**Our own development process (via Claude Code) is now observable in the
same durable event ledger** — a distinct source (`source="claude_code"`,
`activity_class="PRODUCT_DEVELOPMENT"`) from Workbench runtime activity
(`activity_class="PRODUCT_RUNTIME"`), sharing one table by design.

- **Fast by construction:** `agent/claude_code_hook.py` never makes a
  network call synchronously — it appends to the local spool
  (`event_ledger.spool_only()`, measured ~1.3ms) and triggers a detached
  background sync. Measured real end-to-end hook invocation: 0.27s, all
  Python interpreter startup, zero network latency.
- **Verified against the actual binary, not documentation:** every hook
  name wired (`SessionStart`, `SessionEnd`, `UserPromptSubmit`,
  `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PermissionRequest`,
  `Notification`, `Stop`, `SubagentStart`, `SubagentStop`) was confirmed
  as a literal string in the installed Claude Code v2.1.263 binary itself
  — a prior subagent's answer to the same question included several
  plausible but unverifiable names cited to a GitHub issue, which this
  approach avoided building on.
- **Windows attention notifications:** a native toast + sound + best-effort
  taskbar-flash notifier (`agent/claude_notify.ps1`, zero new module
  installs) was tested live. The toast popup was confirmed by the creator.
  Sound and taskbar flash were **not** affirmatively confirmed in that
  same test — reported honestly rather than assumed working (Focus Assist
  can mute toast sound; `FlashWindowEx` is documented to no-op against an
  already-foregrounded window, which the terminal was during that test).
- **Real historical backfill:** 157 genuine events (3 real human prompts +
  154 real tool invocations) were imported from this project's own actual
  Claude Code session transcript for the previous P0 task's real time
  window — not fabricated, not estimated; proven idempotent on rerun.
- **Reduced prompt fatigue, narrowly:** `.claude/settings.local.json`
  (never committed — this repo is public now) gained allow-rules for only
  the exact safe, read-only, local commands actually used this session
  (`git status`/`diff`/`log`/`show`/`rev-parse`, `ls`,
  `python -m unittest`, the Node test harness) — no blanket `Bash(*)` or
  `Bash(git *)`, no `--dangerously-skip-permissions`.
- **Honest about what's not proven:** Claude Code hooks load at session
  start, so true end-to-end confirmation that Claude Code itself invokes
  them requires observing a fresh session — this could not be done
  mid-session and is recorded as an open verification item, not claimed
  complete. Full regression re-run clean: 115 Python tests (114 pass + 1
  pre-existing platform skip) + 14/14 Node, zero regressions.

**Durable memory also updated this task:** the public product surface
decision now includes a 5th surface, **Profile** (docs/COMPANY_VISION.md),
and docs/CONSTITUTION.md §17 gained the "capture broadly with provenance,
interpret later" principle plus the bounded future-evals/training-data
direction.

# Current Reality (2026-09-10, continued): TRAINER PREVIEW V1 — one public product experience

**All five public surfaces now exist and are locally verified**:
Workbench, Dashboard, Usage, Learn, Profile — one shared shell/nav
(`agent/web/style.css`), consistent across all pages.

- **Workbench** (`agent/web/workbench.html/js/css`, formerly the public
  Trainer demo, files renamed via `git mv` — history preserved) reuses
  the existing bounded-autonomy execution path unchanged. Larger
  requirements now show "This change requires Owner Authorization.
  Larger authorized builds are not enabled in this preview yet." with
  clickable safe alternatives. A verified successful deploy now shows a
  prominent "PRODUCTION CHANGE VERIFIED" banner with an "[ OPEN
  PRODUCTION APP ]" link plus run ID/commit/build/test/deploy evidence.
- **Dashboard** and **Usage** (formerly Sessions) got new nav +
  terminology only — Usage additionally gained one small, additive
  "Event Ledger (live)" section showing real recent events with their
  real `PRODUCT_DEVELOPMENT`/`PRODUCT_RUNTIME` source. Neither was
  redesigned.
- **Learn V1** is a real, data-driven, searchable index — 127 topics
  across 15 areas, each with a concise real definition and an honest
  evidence-status tag only where this project genuinely has that
  evidence. Deeper content (interview answers, mechanics, etc.) is
  intentionally not built yet — the data model has room for it.
- **Profile V1** is a static, evidence-backed page drawing only from
  `docs/EXPERIENCE_EVIDENCE.md`'s already-verified capability table and
  the creator's own stated experience — explicitly not copying claims
  from the pre-existing `karthikdevadoss.com` site.
- The former Control Plane (`agent/web/control-plane.html`, formerly
  `index.html`) is fully functional at `/control-plane` — kept, not
  deleted, just removed from public navigation.

**A real Workbench acceptance run was performed end-to-end** through the
actual running server: "Add a small \"Powered by Agentic Delivery\"
footer line to the page" → assessed TINY/LOW/auto → real commit `37e569c`
→ real Railway deploy → production verification HTTP 200 → COMPLETED.
Independently re-verified afterward by directly curling the live
production URL: the real footer text is now "Powered by Agentic
Delivery," confirming genuine success. One honest anomaly, not hidden:
the run's own `deployment` event reported
`content_changed_from_baseline=false` despite the change being genuinely
live moments later — most likely a timing race between that event's
own before/after fetch and Railway's redeploy propagation, not a masked
failure (the independent post-hoc check confirmed the real outcome).

**Public reachability: UNCONFIRMED, not a code defect.** A stale
`python.exe` process was found holding port 8420 from earlier in this
session and stopped before starting a fresh server with the current
code. Three separate `cloudflared tunnel --url` attempts each reported
successful tunnel registration with Cloudflare's edge, but in every case
the assigned `*.trycloudflare.com` hostname never resolved in public DNS
even after 10+ minutes — confirmed via direct queries to Cloudflare's own
authoritative resolver (1.1.1.1 DoH), which returned NXDOMAIN with a
cached negative TTL on every attempt. This is consistent with a genuine,
transient issue in Cloudflare's free/account-less Quick Tunnel DNS
provisioning at the time of this session. See
docs/RESOURCE_REGISTRY.md for the current attempted URL and next steps.

Full regression suite: clean (all existing Python/Node tests still pass;
no new focused test file was added this task since the changes are
primarily frontend/routing — verified instead by direct HTTP checks
against every route and the one real acceptance run above).

# Current Reality (2026-09-10, continued): PERSISTENT cloud hosting — no more laptop/tunnel dependency

**The platform is now hosted independently of the creator's laptop.**
ngrok (the prior task's fix) technically worked but was correctly
rejected as unsuitable for a recruiter-facing link — it shows a provider
interstitial warning page and goes dark the instant the laptop or tunnel
process stops. Both that and the earlier failed Cloudflare Quick Tunnel
are now superseded.

**New persistent URL:** `https://agentic-platform-backend-production.up.railway.app`
— a Railway service (`agentic-platform-backend`) running the exact same
`agent/web_server.py`, packaged as a Docker image (new repo-root
`Dockerfile`), reusing the same providers already trusted for the
Customer app and event ledger rather than introducing a new one.

- **Why Railway, not Vercel-frontend-split:** `web_server.py` is a
  long-running process with in-memory run state, SSE streams, and
  background threads, and its real execution path shells out to `git`,
  `app/mvnw` (needs a JDK), and the `railway` CLI — none of which fits a
  serverless function. One Docker image on Railway was the correct,
  minimal-risk fit for the actual, inspected requirements — not a
  redesign.
- **Where it lives:** inside the *existing* `agentic-delivery-events`
  Railway project (as a second service), not a new project — creating a
  genuinely new project hit a real, verified free-plan resource limit.
- **Verified, not assumed:** all 5 public surfaces return correct pages
  through the real public URL; the deployed backend independently
  confirmed reachable to the real event ledger; a full real Workbench
  acceptance run was submitted *and completed* through the public URL
  itself, reaching `NO_CHANGE_NEEDED`.
- **A real bug was found and fixed via actual testing:** the first
  deploy's acceptance run failed with a `mvnw` permission-denied error —
  Docker's `COPY` from this Windows build host doesn't preserve a POSIX
  executable bit. Fixed with an explicit `chmod +x`, redeployed, and the
  identical requirement then succeeded cleanly (see docs/LESSONS.md).
- **Custom domain: DNS_CONFIGURED_CERTIFICATE_PROVISIONING_PENDING.** The
  creator has added both the CNAME record (`agentic` →
  `r1bbjhwh.up.railway.app`) and the Railway domain-ownership TXT record
  at Namecheap for `agentic.karthikdevadoss.com`. DNS-side setup is done;
  Railway's own TLS certificate provisioning has not been polled or
  confirmed as part of any task — do not claim the domain is serving live
  traffic until that is independently checked.
- **One known functional gap:** the deployed backend doesn't yet have its
  own `RAILWAY_TOKEN`, so it can't (yet) run `railway up` to auto-deploy
  the Customer app from inside itself — only generatable via the Railway
  dashboard, a creator action. The already-satisfied acceptance path
  proven above doesn't need it; a genuine code-change requirement
  submitted today would currently stop at the deploy step.

# Current Reality (2026-09-10, continued): Claude Code hooks disappearance — root-caused and fixed

**Real incident, not a hypothetical:** Claude Code development-telemetry
was believed implemented after an earlier task, but the actual hooks
configuration was later found empty — zero real `dev_session_started`
events existed across multiple subsequent tasks, even though the hook
script itself had passing tests the whole time.

**Root cause, confirmed by direct reproducible test, not guessed:**
Claude Code's own permission-remember mechanism — the thing that quietly
appends a rule to `permissions.allow` whenever a tool action gets
approved — rewrites the *entire* content of `.claude/settings.local.json`
on every such grant, and that rewrite does not preserve unmanaged keys.
A `hooks` section placed there gets silently dropped the very next time
any permission is auto-remembered. Proven twice: added a `hooks` key plus
a marker key, ran one ordinary novel command, watched both vanish from
the rewritten file. `~/.claude/settings.json` (user-level) was tested the
same way in parallel and stayed untouched across the same triggers.

**Fix:** hooks now live in `~/.claude/settings.json` (user-level), which
is not managed by that rewrite path. A secret-free git-tracked template
(`.claude/hooks-template.json`) and a runnable verification command
(`python agent/verify_claude_hooks_config.py`) make this durable and
independently re-checkable, with its own test suite (including a test
that checks this machine's *real* current configuration, not just a
mock). `docs/RECOVERY.md` rewritten accordingly.

**Not yet proven:** whether Claude Code itself actually invokes these
hooks in a real session — that requires a session restart, since hooks
load at process start and this session was never restarted after the fix
landed. Config-level verification (`verify_claude_hooks_config.py`
passing) is real evidence of one layer; it is not the same claim as "the
real producer emitted an event and the ledger has it." Full regression
suite re-run clean: 129 Python tests (128 pass + 1 pre-existing skip) +
14/14 Node — one pre-existing test was found to have over-broadened
"force push" into a bare "push" match, incorrectly flagging a real,
legitimate `Bash(git push *)` rule; fixed to match the original
instruction exactly.

**Permanent rule now recorded in docs/CONSTITUTION.md:** a telemetry
capability is verified only when the real producer emits an event and the
durable remote store contains it — never from script-level tests alone.

# Current Reality (2026-09-10, continued): Claude Code dev telemetry — true end-to-end confirmation closed out

**The one remaining open item from the hooks-config incident is now closed.**
A fresh Claude Code session was started in this repo per the queued
`next_action` and this session's own real hook events were independently
confirmed directly in the live remote Postgres ledger — not the local
spool, not a test fixture: a direct SQL query for this session's
`session_id` (`6bf306ac-a280-41df-b869-9f208ec2ca0d`) returned a genuine
`dev_session_started` row at `2026-09-10T18:32:37Z`, a real
`user_prompt_submitted` row capturing the actual prompt that started this
session, and a live sequence of `tool_call_started`/`tool_call_completed`/
`tool_call_failed` rows tracking the real Read/Bash tool calls made during
this verification — including one genuine `PostToolUseFailure` for an
actual failed command, not a synthetic one. This satisfies the permanent
rule from the incident above: the real producer emitted events and the
durable store has them, confirmed independently rather than assumed from
passing tests. See `verification_state.claude_code_hooks_config_incident_fix`
in `docs/PROJECT_STATE.json` for the full evidence trail.
