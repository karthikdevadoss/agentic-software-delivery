# Agentic Software Delivery System

## Session startup
Before modifying anything:
1. Read docs/PROJECT_STATE.json.
2. Read docs/PROJECT_STATUS.md.
3. Read docs/DECISIONS.md when architectural context is needed.
4. Run git status --short.
5. Run git log -5 --oneline.
6. Inspect only files relevant to the next task.
7. Report current version, current ticket, verified state and exact next action.
8. Do not modify code until explicitly asked.

## Durable-state rules
- Repository files and Git are authoritative; conversation history is supplementary.
- Never guess what an earlier session did. Verify filesystem and Git.
- Workflow:
  implement → inspect diff → compile/test/run → verify → update state → commit.
- Keep PROJECT_STATE.json synchronized after meaningful verified work.
- Update PROJECT_STATUS.md for meaningful project progress.
- Record important architecture decisions and WHY in DECISIONS.md.
- Never expose, print, stage or commit agent/.env or API keys.
- Never weaken tests/verification just to make something pass.
- Before stopping or when context is becoming constrained, leave a verified checkpoint and explicit next_action.

Useful commands:
Planner:
python agent/main.py requirements/sample_requirement.txt

Spring compile:
cd app
.\mvnw.cmd compile

Spring app:
cd app
.\mvnw.cmd spring-boot:run

UI:
http://localhost:8080
