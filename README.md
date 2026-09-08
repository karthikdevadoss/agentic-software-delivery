# Agentic Software Delivery System — Week 1 Baseline

This is the smallest possible baseline for an agentic software delivery
system built around a real Spring Boot application. It contains:

- `app/` — a minimal Spring Boot Customer application.
- `agent/` — a Python script that turns a natural-language requirement
  into an implementation plan using the Anthropic API.
- `requirements/` — sample requirement text used to exercise the agent.
- `docs/` — architecture and engineering rules for the application
  (not yet consumed by the agent — reserved for a future RAG stage).

At this stage the agent only produces a plan. It does not read the
repository, does not modify files, and does not open pull requests.

## Running the Spring Boot application

Prerequisites: Java 17. Maven itself is not required — the project ships
with the Maven Wrapper, which downloads the correct Maven version on
first use.

```bash
cd app
./mvnw spring-boot:run
```

On Windows (Command Prompt or PowerShell):

```powershell
cd app
.\mvnw.cmd spring-boot:run
```

The application starts on `http://localhost:8080` with an in-memory H2
database seeded with one sample customer.

Try it out:

```bash
# Fetch the seeded customer (id 1)
curl http://localhost:8080/customers/1

# Create a new customer
curl -X POST http://localhost:8080/customers \
  -H "Content-Type: application/json" \
  -d '{"name": "Grace Hopper", "email": "grace@example.com"}'
```

The H2 console is available at `http://localhost:8080/h2-console`
(JDBC URL: `jdbc:h2:mem:customerdb`, user: `sa`, no password).

## Running the Python planning agent

Prerequisites: Python 3.10+, an Anthropic API key.

```bash
cd agent
python -m venv venv
source venv/bin/activate   # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Configuring the API key (.env)

The agent loads environment variables from a `.env` file in `agent/`
(via `python-dotenv`). Create one:

```bash
# agent/.env
ANTHROPIC_API_KEY=your-key-here
```

`.env` is listed in `.gitignore` and must never be committed. As an
alternative to `.env`, you can export the variable directly in your
shell instead:

```bash
export ANTHROPIC_API_KEY=your-key-here   # on Windows: set ANTHROPIC_API_KEY=your-key-here
```

If `ANTHROPIC_API_KEY` is missing from both `.env` and the environment,
the agent prints a clear error and exits instead of failing with a raw
stack trace.

### Optional: overriding the model

By default the agent uses `claude-sonnet-5`. To use a different model,
set `CLAUDE_MODEL` (in `.env` or the shell environment):

```bash
# agent/.env
CLAUDE_MODEL=claude-opus-4-8
```

### Running it

```bash
python main.py ../requirements/sample_requirement.txt
```

The agent reads the requirement file, sends it to Claude, and prints a
numbered implementation plan to the terminal. It does not touch the
`app/` source code.

## What's next (not in Week 1)

- Give the agent read access to the repository and `docs/` via RAG.
- Add MCP-controlled tools for the agent to inspect and modify code.
- Add implementation, testing, and review agents with self-correction.
- Add Git/GitHub integration to open pull requests automatically.
- Add a human approval step before deployment.
