# Pydantic AI slice (platform upgrade item 8)

**Scope: one path, not a platform rewrite.** Incident Triage Lab Scenario A's
`triage_execution.diagnose()` now runs on Pydantic AI with a typed, validated
output. Everything else (candidate-patch generation, Scenarios B/C,
`backend_planning`, `agent_loop`) is unchanged.

## What was wrapped
- `agent/pydantic_ai_gateway.py`
  - `GatewayModel` — a custom `pydantic_ai.models.Model` whose `request()` calls
    `reasoning_gateway.call()` and nothing else. Pydantic AI never contacts
    Anthropic itself, so the purpose check (`ADVISORY_PURPOSES`), the
    `LLM_MODE=DISABLED` kill switch, key handling, cost/usage recording and the
    injectable `create_fn` all still apply exactly as before.
  - `Diagnosis` — Pydantic model: `hypothesis`, `root_cause`,
    `affected_component` (str) and `confidence` (`HIGH|MEDIUM|LOW`).
  - `run_typed_diagnosis()` — `Agent(GatewayModel, output_type=PromptedOutput(Diagnosis),
    retries={"output": 0})`. Prompted output was chosen because the gateway
    returns text; the JSON schema is appended to the instructions by Pydantic AI.
    Output retries are 0 so malformed output fails honestly instead of causing a
    second billed call.
- `triage_execution.diagnose()` calls it and keeps its existing return shape.
  Denials (`GatewayDenied`) return `model_called: False` with the gateway's
  reason; a schema-invalid answer returns `model_called: True`, null fields and an
  explanation containing "did not return valid JSON matching the typed Diagnosis
  schema". The output stays advisory; compile/test verification and the human
  approval gate are unchanged.

## Official docs followed (fetched 2026-11-23)
- https://ai.pydantic.dev/ → redirects (301) to https://pydantic.dev/docs/ai/
- Models overview (custom `Model` subclass): https://pydantic.dev/docs/ai/models/overview/
- Output / structured output / `PromptedOutput`: https://pydantic.dev/docs/ai/core-concepts/output/
- Neither page states a version or last-updated date. Package: `pydantic-ai-slim`
  (the official core package without provider extras), latest on PyPI at the time
  of work: 2.71.0; pinned as `pydantic-ai-slim>=2.71,<3`.

**Docs vs. released package.** The custom-model page only says "subclass `Model`".
The required members (`request`, `model_name`, `system`) and the need to call
`self.prepare_request(...)` inside `request()` (which is what appends the
PromptedOutput schema to `instruction_parts`) were taken from the installed 2.71.0
package (`inspect`, source under site-packages), and verified by test, not from the docs.

## Tests
`agent/test_pydantic_ai_gateway.py` (fake `create_fn`, no network): valid typed output
parsed; fenced JSON parsed; bad enum / missing keys / non-JSON rejected with exactly one
provider call; schema injected into the system prompt; `reasoning_gateway.call` spied;
non-advisory purpose and `LLM_MODE=DISABLED` make zero provider calls; `diagnose()` wiring.
Registered in `agent/ci_python_tests.py`.

## Honest limits
- One path (Scenario A diagnose). `generate_candidate_patch` is free-text Java source, not
  a structured output, so it was not moved.
- Still Anthropic only, via the gateway; no second provider, no streaming, no tool use.
- Pydantic AI's own provider/anthropic integrations, tracing and retries are unused by design.
- Extra keys in the model's JSON are now dropped; before they were passed through.
- `agent/web/triage-evidence.json` hashes `triage_execution.py`; it needs regeneration
  on a machine with JDK 21 (see `publish_triage_results.py`) — not done here because
  regenerating without Java would erase the committed Java test results.
