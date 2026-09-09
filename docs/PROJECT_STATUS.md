# Project
Agentic Software Delivery System

# Final Goal
Natural-language software requirement
→ understand actual repository
→ retrieve relevant architecture/code/engineering context
→ plan
→ coding agent modifies files
→ compile/test
→ diagnose failures
→ self-correct
→ review/security checks
→ prepare GitHub PR
→ human approval
→ deployment.

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
- agent/main.py supports --mode v2 (static repo context) and --mode v3 (default: controlled tool-using agent)

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

# Important learning
V2 is NOT RAG. V3 is NOT RAG either.
V2 gathers selected repository context directly and injects it into the Claude prompt.
V3 lets Claude request repository information on demand through controlled,
read-only tools instead of receiving a prebuilt bundle — this is client-side
tool use, not retrieval-augmented generation.
No embeddings/vector DB/semantic retrieval exist yet.

# Browser visual baseline
- Find Customer works
- Create Customer works
- Update Email visibly says:
  "Not implemented yet — current agent ticket"
This is intentionally our before-state so future agent-driven code changes can be seen visually.

# Git history

```
c40d1e8 Add controlled tool-using V3 agent
bf9f747 Add durable project session state
162c8a4 Add project status checkpoint
943648e Make planner repository-aware
a979075 Add customer app browser UI
4ef1aef Scaffold ticket-to-implementation-plan agent
```

# Secrets
- agent/.env contains the Anthropic API key
- .env must NEVER be committed
- never print or copy the key into docs/logs/prompts
- old exposed key was rotated

# What does NOT exist yet
- RAG
- embeddings
- vector DB
- MCP integration in our product
- code-writing / file-modifying agent (V3 can only read the repository, never write)
- test agent
- reviewer agent
- autonomous file modification by our Python system
- compile/test/self-correction loop
- GitHub PR automation
- CI/CD
- production hosting

# Exact next development step
Do NOT implement anything automatically after reading this file.

Next planned phase:
V4 — controlled code-writing agent with a compile feedback loop.

Goal:
Let the agent propose an actual code change (starting with the Update Email
ticket) as a reviewable diff, apply it only under tight, explicit controls,
then run a controlled compile tool (no arbitrary shell/Maven access) to
verify the change and support self-correction — still with no autonomous
Git writes, PR creation, or deployment at this stage.

Next action:
Design V4's write-tool boundaries (propose-diff-then-apply pattern, explicit
human approval before any file write, restricted target paths) and a
controlled compile tool, before implementing V4 against the Update Email
ticket. Do not implement V4 yet.

# Useful commands

Run planner from project root (V3, default — controlled tool-using agent):
python agent/main.py requirements/sample_requirement.txt

Run the previous static-context planner for comparison:
python agent/main.py requirements/sample_requirement.txt --mode v2

Run V3 explicitly:
python agent/main.py requirements/sample_requirement.txt --mode v3

Run the focused V3 correctness tests:
python agent/test_agent_loop.py

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
