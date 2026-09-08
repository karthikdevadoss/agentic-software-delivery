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

# Important learning
V2 is NOT RAG.
It currently gathers selected repository context directly and injects it into the Claude prompt.
No embeddings/vector DB/semantic retrieval exist yet.

# Browser visual baseline
- Find Customer works
- Create Customer works
- Update Email visibly says:
  "Not implemented yet — current agent ticket"
This is intentionally our before-state so future agent-driven code changes can be seen visually.

# Git history

```
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
- coding agent
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
V3 — controlled tool-using agent.

Goal:
Allow our own AI application to inspect actual repository files through controlled tools and make an implementation decision dynamically, instead of only receiving a pre-built static repository summary.

Before modifying code in V3, review the architecture and discuss whether to introduce direct tool calling first or MCP abstraction first.

# Useful commands

Run planner from project root:
python agent/main.py requirements/sample_requirement.txt

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
