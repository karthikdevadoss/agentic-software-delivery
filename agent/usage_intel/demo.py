"""FICTIONAL demonstration dataset for AI Usage Intelligence.

Every organisation, team, person, workflow and number here is invented to
show how a company COULD use the feature. Nothing describes a real customer,
a real deployment, real savings, or anyone's internal architecture.

Isolation: the dataset is generated in memory, deterministically (fixed
seed), every event has dataset="demo" and every measurement's provenance is
"demo". It is never written to the database, so it cannot mix with live
data, and no model is called to produce it.

Model names and list prices ARE real (docs/AI_USAGE_SOURCES.md), so costs
are realistic estimates of what such fictional traffic would cost at list
price -- still fictional traffic.

Scenarios:
  energy_support   electricity-billing support: three models compared on
                   cost and human-verified resolution rate
  software         code generation / review / debugging / repo investigation,
                   verified by tests
  learning         AI-assisted learning sessions (see learning.py)
  agent_retries    an invoice-dispute agent with excessive retries in the
                   first half of the period, fixed in the second half
  subscription     a developer's coding-assistant SUBSCRIPTION sessions: shown
                   as equivalent API value (what the tokens would cost at list
                   price), never added to metered API spend or budgets. It has
                   its own random stream so the other scenarios are unchanged.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone

from . import pricing
from .events import Source, UsageEvent, make_event_id
from .learning import LearningRecord
from .outcomes import Outcome

ORG = "org_demo_fictional_energy"
DEMO_LABEL = ("Fictional demonstration data. Organisations, people, workflows and numbers are "
              "invented; costs are list-price estimates of that invented traffic.")

TEAMS = {"team_support": ["dana", "eli", "farah"], "team_platform": ["gus", "hana"], "team_learning": ["ivo"]}
USER_TEAM = {u: t for t, us in TEAMS.items() for u in us}


def _ts(day: date, minute: int) -> str:
    return datetime(day.year, day.month, day.day, 8, 0, tzinfo=timezone.utc).__add__(
        timedelta(minutes=minute)).isoformat(timespec="seconds").replace("+00:00", "Z")


def _call(rng, *, day, minute, n, model, provider, user, project, feature, category, session, task,
          workflow=None, agent=None, inp, out, cache_read=0, attempt=1, success=True, tools=None,
          parent=None, components=None, error=None, billing="metered_api"):
    ev = UsageEvent(event_id=make_event_id(provider, f"demo-{n}", attempt), timestamp=_ts(day, minute),
                    request_id=f"demo-{n}", provider=provider, requested_model=model, response_model=model,
                    org_id=ORG, team_id=USER_TEAM.get(user), user_id=user, project_id=project, feature=feature,
                    activity_category=category, session_id=session, conversation_id=session, task_id=task,
                    workflow_id=workflow, agent_id=agent, parent_event_id=parent, attempt=attempt,
                    is_retry=attempt > 1, input_tokens=inp, output_tokens=out, cache_read_tokens=cache_read,
                    cache_write_tokens=0, duration_ms=round(rng.uniform(600, 2600) + out * 6, 1),
                    tool_calls=tools, success=success, error_category=error, dataset="demo",
                    billing_category=billing)
    ev.provenance = {f: Source.DEMO.value for f in ("input_tokens", "output_tokens", "cache_read_tokens",
                                                    "cache_write_tokens", "duration_ms", "tool_calls")}
    ev.provenance["reasoning_tokens"] = Source.UNAVAILABLE.value
    if components:
        ev.provenance["context_components"] = {**components, "source": "demo (estimated split)"}
    return pricing.estimate(ev)


def build(today: date | None = None, days: int = 30) -> dict:
    """Return {"events", "outcomes", "learning", "budgets", "label"} for the
    `days` ending on `today` (default: today, so date filters behave)."""
    today = today or datetime.now(timezone.utc).date()
    rng = random.Random(20261128)
    sub_rng = random.Random(20261129)
    events, outcomes, learning = [], [], []
    n = 0

    for d_off in range(days):
        day = today - timedelta(days=days - 1 - d_off)
        second_half = d_off >= days // 2

        # --- energy support: billing questions, three models -----------------------
        for i in range(rng.randint(6, 10)):
            n += 1
            user = rng.choice(TEAMS["team_support"])
            model, provider, ok_p = rng.choice([("claude-haiku-5-5", "anthropic", 0.86),
                                                ("claude-sonnet-5-5", "anthropic", 0.91),
                                                ("gpt-6-luna", "openai", 0.80)])
            task = f"sup-{day.isoformat()}-{i}"
            hist = rng.randint(1500, 9000)
            ev = _call(rng, day=day, minute=i * 7, n=n, model=model, provider=provider, user=user,
                       project="billing-support", feature="support-assistant", category="customer_support",
                       session=f"sup-sess-{day.isoformat()}-{user}", task=task, inp=hist + 900,
                       out=rng.randint(180, 520), cache_read=rng.choice([0, 0, 2500]), tools=1,
                       components={"system": 900, "history": hist, "retrieved": 0, "user_input": 0})
            events.append(ev)
            resolved = rng.random() < ok_p
            outcomes.append(Outcome(f"out-{task}", task, "support_resolution",
                                    "completed" if resolved else "failed", evidence="human",
                                    timestamp=ev.timestamp, org_id=ORG, team_id=ev.team_id, user_id=user,
                                    project_id="billing-support", activity_category="customer_support",
                                    difficulty="simple", attempts=1, corrections=0 if resolved else 1,
                                    human_review_minutes=round(rng.uniform(0.5, 2.0), 1), dataset="demo"))

        # --- software engineering: verified by tests -----------------------------------
        for i, (cat, model, provider) in enumerate([("code_generation", "claude-sonnet-5-5", "anthropic"),
                                                    ("code_review", "claude-haiku-5-5", "anthropic"),
                                                    ("debugging", "claude-opus-5-5", "anthropic"),
                                                    ("repo_investigation", "gpt-6.2-sol", "openai")]):
            if rng.random() < 0.35:
                continue
            user = rng.choice(TEAMS["team_platform"])
            task = f"dev-{day.isoformat()}-{i}"
            calls = rng.randint(1, 4)
            for c in range(calls):
                n += 1
                retrieved = rng.randint(4000, 30000)
                events.append(_call(rng, day=day, minute=200 + i * 30 + c * 4, n=n, model=model, provider=provider,
                                    user=user, project="customer-portal", feature="dev-assistant", category=cat,
                                    session=f"dev-sess-{day.isoformat()}-{user}", task=task,
                                    inp=retrieved + 2500, out=rng.randint(400, 2600), cache_read=rng.choice([0, 6000]),
                                    tools=rng.randint(0, 5),
                                    components={"system": 2500, "history": 0, "retrieved": retrieved, "user_input": 0}))
            passed = rng.random() < {"debugging": 0.82, "code_generation": 0.78, "code_review": 0.93,
                                     "repo_investigation": 0.88}[cat]
            outcomes.append(Outcome(f"out-{task}", task, "code_fix_verified" if cat == "debugging" else "dev_task_completed",
                                    "completed" if passed else "failed", evidence="objective",
                                    timestamp=events[-1].timestamp, org_id=ORG, team_id="team_platform", user_id=user,
                                    project_id="customer-portal", activity_category=cat,
                                    difficulty="complex" if cat == "debugging" else "standard",
                                    attempts=calls, corrections=calls - 1,
                                    time_saved_minutes=rng.choice([None, 15, 25, 40]) if passed else None,
                                    time_saved_source="estimated", dataset="demo"))

        # --- agent with retries, fixed in the second half --------------------------------
        for i in range(rng.randint(3, 5)):
            task = f"agent-{day.isoformat()}-{i}"
            parent = make_event_id(None, f"demo-agent-{task}")
            # Container for this agent run: groups its model calls, carries no tokens itself.
            events.append(UsageEvent(event_id=parent, timestamp=_ts(day, 400 + i * 10), request_type="agent_execution",
                                     org_id=ORG, team_id="team_support", user_id="farah", project_id="billing-support",
                                     feature="invoice-dispute-agent", activity_category="dispute_resolution",
                                     session_id=f"agent-sess-{task}", task_id=task, workflow_id="invoice-dispute",
                                     agent_id="invoice-dispute-agent", dataset="demo"))
            steps = rng.randint(2, 3) if second_half else rng.randint(5, 9)
            for s in range(steps):
                n += 1
                retry = (not second_half) and s >= 2
                events.append(_call(rng, day=day, minute=400 + i * 10 + s, n=n, model="claude-sonnet-5-5",
                                    provider="anthropic", user="farah", project="billing-support",
                                    feature="invoice-dispute-agent", category="dispute_resolution",
                                    session=f"agent-sess-{task}", task=task, workflow="invoice-dispute",
                                    agent="invoice-dispute-agent", inp=rng.randint(6000, 14000),
                                    out=rng.randint(300, 900), attempt=(s if retry else 1) or 1,
                                    success=not (retry and s < steps - 1), tools=rng.randint(1, 3), parent=parent,
                                    error="tool_schema_mismatch" if (retry and s < steps - 1) else None))
            ok = rng.random() < 0.9
            outcomes.append(Outcome(f"out-{task}", task, "workflow_completed", "completed" if ok else "failed",
                                    evidence="human", timestamp=events[-1].timestamp, org_id=ORG, team_id="team_support",
                                    user_id="farah", project_id="billing-support", workflow_id="invoice-dispute",
                                    activity_category="dispute_resolution", difficulty="standard", attempts=1,
                                    corrections=0 if ok else 1, dataset="demo"))

        # --- learning: one session every other day ----------------------------------------
        if d_off % 2 == 0:
            sess = f"learn-{day.isoformat()}"
            section = ["Tokens and embeddings", "Retrieval", "Evaluation", "Agents and tools"][min(d_off // 8, 3)]
            for c in range(3):
                concept = f"{section}: concept {d_off // 2 * 3 + c + 1}"
                n += 1
                events.append(_call(rng, day=day, minute=600 + c * 9, n=n, model="claude-sonnet-5-5", provider="anthropic",
                                    user="ivo", project="ai-engineering-curriculum", feature="learning-coach",
                                    category="learning", session=sess, task=f"learn-{concept}",
                                    inp=rng.randint(3000, 12000), out=rng.randint(500, 1400)))
                learning.append(LearningRecord(sess, section, concept, "introduced", timestamp=events[-1].timestamp,
                                               user_id="ivo", minutes=round(rng.uniform(4, 9), 1), source="demo"))
                attempts = rng.choice([1, 1, 2, 3])
                for a in range(1, attempts + 1):
                    correct = a == attempts and rng.random() < 0.9
                    learning.append(LearningRecord(sess, section, concept, "verification", timestamp=events[-1].timestamp,
                                                   user_id="ivo", correct=correct, attempt=a, evidence="assessment",
                                                   minutes=round(rng.uniform(1, 3), 1), source="demo"))
            if d_off >= 6:
                for c in range(2):
                    learning.append(LearningRecord(sess, section, f"retention check {c + 1}", "retention_test",
                                                   timestamp=_ts(day, 700), user_id="ivo",
                                                   correct=rng.random() < 0.8, evidence="assessment",
                                                   minutes=1.5, source="demo"))

        # --- subscription coding assistant (equivalent API value, not spend) ----------------
        if day.weekday() < 5:
            sess = f"sub-{day.isoformat()}-hana"
            for c in range(sub_rng.randint(3, 8)):
                n += 1
                events.append(_call(sub_rng, day=day, minute=480 + c * 6, n=n, model="claude-opus-5-5",
                                    provider="anthropic", user="hana", project="customer-portal",
                                    feature="coding-assistant-subscription", category="code_generation",
                                    session=sess, task=None, inp=sub_rng.randint(2000, 9000),
                                    out=sub_rng.randint(300, 1800), cache_read=sub_rng.randint(20000, 90000),
                                    tools=sub_rng.randint(1, 6), billing="equivalent_api_value"))

    budgets = [
        {"scope": "org", "scope_id": ORG, "period": "month", "limit": 400.0, "currency": "USD",
         "alert_at": [0.5, 0.8, 1.0], "hard_limit": False, "enforced_by": "application (demo)"},
        {"scope": "project", "scope_id": "billing-support", "period": "month", "limit": 150.0, "currency": "USD",
         "alert_at": [0.8, 1.0], "hard_limit": True, "enforced_by": "application (demo)"},
        {"scope": "workflow", "scope_id": "invoice-dispute", "period": "day", "limit": 5.0, "currency": "USD",
         "alert_at": [1.0], "hard_limit": True, "max_agent_steps": 6, "max_retries": 2,
         "enforced_by": "application (demo)"},
    ]
    return {"events": events, "outcomes": outcomes, "learning": learning, "budgets": budgets, "label": DEMO_LABEL,
            "org_id": ORG, "teams": TEAMS}
