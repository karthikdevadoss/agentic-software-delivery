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

V4 write/execution boundary foundation (this checkpoint, not committed yet):
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
- code-writing / file-modifying agent wired into the live tool-calling loop (V4's write/build tools exist and are tested in isolation, but agent_loop.py cannot call them yet)
- any ticket actually implemented through V4 (Update Email remains the planned first proof)
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

Next action:
The V4 write/build safety boundary (propose->approve->apply, scope-
restricted write tool, allowlist-only compile/test tool) is now built and
verified in isolation (see above) — not yet committed, not yet wired into
the live agent loop. Next: wire write_tools/build_tools into
agent_loop.py's TOOL_SCHEMAS/dispatch, then use the Update Email ticket as
the first real end-to-end proof.

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
