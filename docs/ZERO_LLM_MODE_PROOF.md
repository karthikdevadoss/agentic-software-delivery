# Zero-LLM Mode — Proof, Not Assertion

Section 3 of the Owner's "DETERMINISTIC INTELLIGENCE COMPLETION"
continuation: a hard acceptance criterion that the platform provides
substantial engineering value with `LLM_MODE=DISABLED`, evidenced by a
real run, not a mocked metric.

## The real run

```
LLM_MODE=DISABLED python -c "... vc.build_plan/print_plan/execute against a real 2-file Java diff ..."
```

Real input: the actual historical diff from commit `2155a8a`
(`ContractPlanService.java` + `ContractPlanServiceTest.java`, the real
plan-enrollment idempotency fix) — real file contents currently in this
repository, run through the real deterministic pipeline (`agent/
change_risk.py` → `agent/test_impact_analysis.py` → real `mvnw test`).

**Real output, captured verbatim:**

```
Overall classification: risk=MEDIUM  blast_radius=MODULE
  ContractPlanService.java: risk=MEDIUM blast_radius=MODULE (business logic change)
  ContractPlanServiceTest.java: risk=LOW blast_radius=LOCAL (test-only change)

Selected:
  Java: ['ContractPlanControllerIntegrationTest', 'ContractPlanServiceTest']

=== REAL EXECUTION EVIDENCE ===
  always-on-smoke: exit_code=0 duration=26.9s
  java-selected: exit_code=0 duration=31.0s
overall_exit_code: 0

=== MODEL USAGE DURING THIS ENTIRE RUN ===
AI calls: 0
input tokens: 0
output tokens: 0
LLM_MODE: DISABLED
```

**Not mocked**: `metrics.reset()` was called before the run and
`metrics.get_model_usage_events()` was queried after — an empty list
means no code path in this entire pipeline (`change_risk.py`,
`test_impact_analysis.py`, `verify_change.py`, the real `mvnw` subprocess)
ever recorded a model call, because none of them make one. This is the
same real metrics-recording mechanism the live Workbench uses to report
actual (never estimated) AI spend — if a call had happened, it would show
here.

## What this real pipeline provides with zero model involvement

- Real risk/blast-radius classification, from an ordered rule table over
  real changed file paths (not a guess).
- Real, deterministic test selection — the exact two test classes that
  actually cover the changed file (not "run everything," not "run
  nothing").
- Real compiled/executed evidence: two genuine `mvnw test` invocations
  against the real Spring Boot application, real exit codes, real
  durations.
- A written evidence artifact (`agent/.verify_change_evidence/*.json`,
  gitignored) for every such run — durable, inspectable, replayable.

## Comparison: where this session's real AI-assisted work added value the above could not

Rather than spend a new, redundant paid API call solely to illustrate this
comparison, this cites **already-real, already-recorded evidence** from
this project's own history (`docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml`,
`docs/PROJECT_STATUS.md`) — spending money again just to re-prove a point
already proven would be exactly the kind of unjustified LLM use this
directive argues against.

| Real AI-assisted example | What the model was asked to do | Could the deterministic pipeline above do this instead? |
|---|---|---|
| Triage `generate_candidate_patch()` (this project's real Scenario A/B/C candidate fixes) | Write an actual, novel code fix given a real defective file and real evidence | No — `change_risk.py`/`test_impact_analysis.py` can classify and select tests for a change that *already exists*; neither can *author* a new one. This is genuinely generative work, correctly gated `NOVEL_IMPLEMENTATION_PROPOSAL` and never trusted without the real compile+test verification this session added (commit `72dbe4d`) |
| A real, documented Workbench acceptance run (`docs/PROJECT_STATUS.md`'s "JOB-SEARCH LIVE DEMO P0" section): a real natural-language requirement submitted through the public Workbench, real 3-call/13,557-token usage, real calculated cost `$0.029602` | Interpret a natural-language requirement and decide what it actually asks for | No — `demo_catalogue.py`'s deterministic matcher only recognizes requirements against its fixed catalogue; genuinely novel phrasing needs real semantic interpretation, which is exactly why the Workbench's LLM-assisted path exists alongside the fixed-catalogue fast path |

## Honest conclusion

The deterministic pipeline is not a toy fallback — it is what actually
decides risk, test scope, and pass/fail for **every** real code change in
this repository already, LLM or not (the gateway's advisory outputs never
gate any of this). What the model adds, in the one real generative call
site this session hardened (Triage candidate generation), is writing code
that doesn't exist yet from a natural-language description of a defect —
a task no rule table or test selector can perform. That is a specific,
narrow, evidenced justification, not a blanket one, and it is exactly why
`agent/reasoning_gateway.py` exists: to make sure that narrow justification
is checked every time, not assumed.
