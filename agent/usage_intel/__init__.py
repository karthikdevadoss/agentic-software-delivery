"""AI Usage, Cost & Value Intelligence (2026-11-28).

Builds on what the platform already had -- the delivery_events ledger
(agent/event_ledger.py), versioned pricing (agent/pricing_config.py), the
single model gateway with budgets (agent/reasoning_gateway.py,
agent/gateway_budget.py, agent/budget_store.py) and OpenTelemetry spans
(agent/tracing.py) -- and adds what was missing: attribution (org, team,
user, project, task, workflow, agent), field-level measurement provenance,
outcome/value measurement, learning efficiency, explainable recommendations,
model comparison and an isolated demonstration dataset.

Modules:
  events      normalized UsageEvent, provenance and billing categories,
              provider normalizers, deterministic (dedupe-safe) event ids
  pricing     multi-provider cost calculation on top of pricing_config
  analytics   pure aggregation over events + outcomes (no I/O)
  outcomes    outcome records and value metrics
  learning    AI-assisted learning efficiency (evidence-based mastery)
  recommend   deterministic, explainable optimisation recommendations
  compare     model comparison by task category
  access      roles and organisation isolation
  demo        fictional, clearly labelled demonstration dataset (never stored)
  store       reading/writing live data in the existing Postgres ledger
"""
