# Model Selection Policy

This project has, to date, used **one model consistently** (Claude Sonnet 5,
via the Anthropic API) across every role — planner, builder, and (via the
`qa-evaluator` subagent) evaluator. This document records the actual
reasoning behind that choice and the policy for when/how that would change,
rather than presenting a multi-model comparison this project has not
actually run.

## Why one model, one provider, so far

- **Model/vendor neutrality is an explicit architectural principle**
  (docs/CONSTITUTION.md §10) — Claude is a current implementation detail,
  not a claimed dependency lock-in. The system is built so a different
  provider could be substituted behind the same tool-calling loop
  (`agent/agent_loop.py`'s `dispatch_fn`/`tool_schemas` abstraction) without
  a redesign.
- **A single-operator project with one real workload profile.** There was
  no genuine business need yet to route different task types to different
  models — every task so far (planning, implementation, evaluation) has
  been well within one capable model's range, and introducing multiple
  providers before there's a measured reason to would have been
  optimizing a problem that doesn't exist yet.
- **Builder/evaluator separation was achieved architecturally, not by model
  diversity.** The independent-evaluator property this project needs (a
  process that cannot share the builder's blind spots) comes from running
  the evaluator as a structurally separate subagent context with its own
  tool calls and its own fresh evidence-gathering — not from using a
  different model for evaluation. Using a different *model* for the
  evaluator might add value later (see "Future roles" below), but it isn't
  what makes builder/evaluator separation real today.

## When this project WOULD add a second model/provider

1. **A measured cost or latency problem** where a smaller/cheaper model is
   demonstrably sufficient for a specific, bounded task class (e.g., a
   pure classification/routing step) — decided from real
   `estimation.py`/usage-ledger data, not intuition.
2. **A genuinely adversarial evaluator role**, where using the SAME
   provider/model family for builder and evaluator is itself a risk worth
   mitigating (shared training-data blind spots, shared failure modes) —
   this is a real, documented concern in multi-agent AI system design, not
   yet something this project's evidence has required addressing.
3. **A specific capability gap** a different model demonstrably closes
   (e.g., a much larger context window need, or a specialized code model)
   — verified by an actual eval (agent/eval_runner.py's pattern), never
   adopted on reputation alone.

## Model comparison data model (prepared, not yet populated)

docs/PROJECT_STATE.json documents the intended schema for recording future
multi-model runs once there is a real reason to compare:

```
provider, model/version, role (PLANNER / BUILDER / EVALUATOR / CLASSIFIER),
reason_selected, prompt_version, context_size (where available),
tools_available, first_pass_result, defects, rework_count, tokens,
latency, cost
```

No comparison data exists yet — this project has one model's worth of real
evidence, which is exactly what the AI Engineering Quality Ledger and the
Usage/economics ledger already capture in detail. This schema exists so
that future runs accumulate comparable structured data automatically rather
than requiring a redesign when a second model is eventually introduced.

## Practical selection heuristic used today

For every task this project runs through the agentic pipeline: use the one
configured model, verify the result deterministically (compile/test/
production assertion), and let the AI Engineering Quality Ledger's
`recurrence_status` field tell you, over time, whether a given defect class
is a genuine model-capability limitation (worth reconsidering model choice)
or a one-off gap in this project's own harness (worth fixing in code
instead). So far, every defect in the ledger has been the latter.
