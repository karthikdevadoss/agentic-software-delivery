"""Deterministic, explainable optimisation recommendations.

No model is called: every recommendation is a rule over recorded events and
outcomes, so it costs nothing to compute and the same data always gives the
same advice. Each one carries the evidence, why it matters, a suggested
action, an estimated benefit (computed from the data and labelled as an
estimate), a confidence level that depends on sample size, its limitations,
and whether an evaluation is needed before acting. Nothing here changes
routing or budgets: recommendations are advice for a person.
"""
from __future__ import annotations

import statistics
from collections import defaultdict

import pricing_config

from .analytics import leaves
from .events import UsageEvent
from .outcomes import Outcome


def _confidence(n: int) -> str:
    return "high" if n >= 50 else "medium" if n >= 15 else "low"


def _prompt(e: UsageEvent) -> int | None:
    parts = [e.input_tokens, e.cache_read_tokens, e.cache_write_tokens]
    return sum(p for p in parts if p is not None) if any(p is not None for p in parts) else None


def _rec(kind, title, *, evidence, why, action, benefit, confidence, limitations, needs_evaluation, scope):
    return {"kind": kind, "title": title, "scope": scope, "evidence": evidence, "why_it_matters": why,
            "suggested_action": action, "potential_benefit": benefit, "confidence": confidence,
            "limitations": limitations, "requires_evaluation": needs_evaluation}


def excessive_context(events, min_tokens=20_000, factor=3.0):
    recs = []
    by_cat = defaultdict(list)
    for e in leaves(events):
        p = _prompt(e)
        if p is not None and e.activity_category:
            by_cat[e.activity_category].append((e, p))
    for cat, rows in by_cat.items():
        if len(rows) < 10:
            continue
        med = statistics.median(p for _, p in rows)
        big = [(e, p) for e, p in rows if p >= max(min_tokens, factor * med)]
        if not big:
            continue
        excess_cost = sum((e.cost_estimated or 0) * (1 - med / p) for e, p in big)
        recs.append(_rec("excessive_context", f"Unusually large prompts in '{cat}'", scope={"activity_category": cat},
                         evidence={"requests": len(rows), "median_prompt_tokens": round(med),
                                   "large_requests": len(big), "threshold_tokens": round(max(min_tokens, factor * med)),
                                   "examples": [e.event_id for e, _ in big[:3]]},
                         why="Every extra prompt token is paid on every call; long histories and broad retrieval "
                             "grow quietly and can also dilute answer quality.",
                         action="Check what fills these prompts (history, retrieved context, tool output). Consider "
                                "summarising history, tighter retrieval, or prompt caching for stable prefixes.",
                         benefit={"estimated_usd": round(excess_cost, 4),
                                  "basis": "ESTIMATE: cost of the tokens above the category median in the flagged requests"},
                         confidence=_confidence(len(rows)),
                         limitations="Size alone does not prove the context was unnecessary; some tasks need it.",
                         needs_evaluation=True))
    return recs


def expensive_model_for_simple_tasks(events, outcomes, min_tasks=10):
    """Simple tasks (by outcome difficulty) on a model whose input price is at
    least 5x the cheapest model already used for the same category."""
    simple_tasks = {o.task_id: o for o in outcomes if o.difficulty == "simple"}
    by_cat_model = defaultdict(list)
    for e in leaves(events):
        if e.task_id in simple_tasks and e.activity_category and e.model:
            by_cat_model[(e.activity_category, e.provider, e.model)].append(e)
    recs = []
    cats = {c for c, _, _ in by_cat_model}
    for cat in cats:
        models = {(p, m): evs for (c, p, m), evs in by_cat_model.items() if c == cat}
        priced = {k: pricing_config.get_pricing(k[0], k[1]) for k in models}
        priced = {k: v for k, v in priced.items() if v}
        if len(priced) < 2:
            continue
        cheapest = min(priced, key=lambda k: priced[k]["input"])
        for k, evs in models.items():
            if k == cheapest or k not in priced or len({e.task_id for e in evs}) < min_tasks:
                continue
            ratio = priced[k]["input"] / priced[cheapest]["input"]
            if ratio < 5:
                continue
            def rate(ev_list):
                tasks = {e.task_id for e in ev_list}
                rows = [simple_tasks[t] for t in tasks]
                return (sum(o.verified_success for o in rows) / len(rows)) if rows else None
            spend = sum(e.cost_estimated or 0 for e in evs)
            recs.append(_rec("expensive_model", f"'{cat}': simple tasks on {k[1]}", scope={"activity_category": cat, "model": k[1]},
                             evidence={"tasks": len({e.task_id for e in evs}), "spend_usd": round(spend, 4),
                                       "input_price_ratio_vs_cheapest": round(ratio, 1), "cheapest_model_used": cheapest[1],
                                       "verified_success_rate": round(rate(evs), 4) if rate(evs) is not None else None,
                                       "cheapest_verified_success_rate": round(rate(models[cheapest]), 4) if rate(models[cheapest]) is not None else None},
                             why="Simple tasks rarely need the most capable model; price differences of 5x or more compound quickly.",
                             action=f"Run a side-by-side evaluation of {cheapest[1]} on a sample of these tasks before switching.",
                             benefit={"estimated_usd": round(spend * (1 - 1 / ratio), 4),
                                      "basis": "ESTIMATE: spend x (1 - price ratio), IF quality held -- not yet shown"},
                             confidence=_confidence(len(evs)),
                             limitations="Observed success rates come from different task mixes; they do not prove the cheaper "
                                         "model is equally good on these tasks.",
                             needs_evaluation=True))
    return recs


def high_retry_workflows(events, min_requests=10, threshold=0.2):
    groups = defaultdict(list)
    for e in leaves(events):
        if e.workflow_id:
            groups[e.workflow_id].append(e)
    recs = []
    for wf, evs in groups.items():
        if len(evs) < min_requests:
            continue
        retries = [e for e in evs if e.is_retry]
        rate = len(retries) / len(evs)
        if rate < threshold:
            continue
        errors = defaultdict(int)
        for e in evs:
            if e.error_category:
                errors[e.error_category] += 1
        recs.append(_rec("high_retry_rate", f"Workflow '{wf}' retries {rate:.0%} of calls", scope={"workflow_id": wf},
                         evidence={"requests": len(evs), "retries": len(retries), "retry_rate": round(rate, 4),
                                   "error_categories": dict(errors)},
                         why="Retries cost as much as first attempts and usually point at a fixable cause.",
                         action="Look at the most common error category first (prompt, tool schema, context quality, model choice).",
                         benefit={"estimated_usd": round(sum(e.cost_estimated or 0 for e in retries), 4),
                                  "basis": "ESTIMATE: cost of the retry calls in this period"},
                         confidence=_confidence(len(evs)),
                         limitations="Some retries are healthy (transient provider errors).", needs_evaluation=False))
    return recs


def long_agent_runs(events, factor=2.0, min_runs=8):
    by_parent = defaultdict(list)
    agent_of = {}
    for e in leaves(events):
        if e.parent_event_id:
            by_parent[e.parent_event_id].append(e)
            agent_of[e.parent_event_id] = e.agent_id or e.workflow_id
    by_agent = defaultdict(list)
    for pid, evs in by_parent.items():
        by_agent[agent_of[pid]].append((pid, evs))
    recs = []
    for agent, runs in by_agent.items():
        if len(runs) < min_runs:
            continue
        steps = [len(evs) for _, evs in runs]
        med = statistics.median(steps)
        long = [(pid, evs) for pid, evs in runs if len(evs) > factor * med]
        if not long:
            continue
        recs.append(_rec("long_agent_runs", f"Agent '{agent}': runs with over {factor:g}x the usual steps", scope={"agent_id": agent},
                         evidence={"runs": len(runs), "median_steps": med, "long_runs": len(long),
                                   "max_steps": max(steps), "examples": [p for p, _ in long[:3]]},
                         why="Runaway agent loops burn budget and often end in failure anyway.",
                         action="Set a maximum step count for this agent and inspect what the long runs were doing.",
                         benefit={"estimated_usd": round(sum(sum(e.cost_estimated or 0 for e in evs[int(med):]) for _, evs in long), 4),
                                  "basis": "ESTIMATE: cost of steps beyond the median in the long runs"},
                         confidence=_confidence(len(runs)),
                         limitations="A long run may be a hard task done right.", needs_evaluation=True))
    return recs


def low_value_spend(events, outcomes, min_tasks=10):
    cost = defaultdict(float)
    for e in leaves(events):
        if e.task_id and e.cost_estimated is not None:
            cost[e.task_id] += e.cost_estimated
    rows = [(o, cost[o.task_id]) for o in outcomes if o.task_id in cost]
    if len(rows) < min_tasks:
        return []
    q3 = statistics.quantiles([c for _, c in rows], n=4)[2]
    bad = [(o, c) for o, c in rows if c >= q3 and not o.verified_success]
    if not bad:
        return []
    by_cat = defaultdict(list)
    for o, c in bad:
        by_cat[o.activity_category or "(uncategorised)"].append(c)
    worst = max(by_cat, key=lambda k: sum(by_cat[k]))
    return [_rec("low_value_spend", "Expensive tasks without a verified result", scope={"activity_category": worst},
                 evidence={"tasks_considered": len(rows), "top_quartile_cost_usd": round(q3, 4),
                           "expensive_unverified_tasks": len(bad), "spend_usd": round(sum(c for _, c in bad), 4),
                           "largest_category": worst},
                 why="Spend that never leads to a verified outcome is the clearest waste signal.",
                 action=f"Review a sample of '{worst}' tasks: were they abandoned, failed, or just never verified?",
                 benefit={"estimated_usd": None, "basis": "Depends on why they failed; not estimated."},
                 confidence=_confidence(len(rows)),
                 limitations="'Unverified' can mean nobody recorded the outcome, not that it failed.",
                 needs_evaluation=False)]


def successful_optimisation(events, outcomes, min_tasks=8):
    """A workflow whose cost per verified success fell by >= 20% from the first
    half of the period to the second, while its verified success rate did not
    drop by more than 5 percentage points."""
    by_wf = defaultdict(list)
    for e in leaves(events):
        if e.workflow_id and e.timestamp:
            by_wf[e.workflow_id].append(e)
    out_by_task = {o.task_id: o for o in outcomes}
    recs = []
    for wf, evs in by_wf.items():
        stamps = sorted(e.timestamp for e in evs)
        mid = stamps[len(stamps) // 2]
        halves = []
        for part in ([e for e in evs if e.timestamp < mid], [e for e in evs if e.timestamp >= mid]):
            tasks = {e.task_id for e in part if e.task_id in out_by_task}
            ver = sum(out_by_task[t].verified_success for t in tasks)
            cost = sum(e.cost_estimated or 0 for e in part)
            halves.append({"tasks": len(tasks), "verified": ver, "cost": cost,
                           "rate": ver / len(tasks) if tasks else None, "cpv": cost / ver if ver else None})
        a, b = halves
        if min(a["tasks"], b["tasks"]) < min_tasks or not a["cpv"] or not b["cpv"]:
            continue
        drop = 1 - b["cpv"] / a["cpv"]
        if drop >= 0.2 and (b["rate"] - a["rate"]) >= -0.05:
            recs.append(_rec("successful_optimisation", f"Workflow '{wf}' got {drop:.0%} cheaper per verified success",
                             scope={"workflow_id": wf},
                             evidence={"before": {k: round(v, 4) if isinstance(v, float) else v for k, v in a.items()},
                                       "after": {k: round(v, 4) if isinstance(v, float) else v for k, v in b.items()}},
                             why="Shows a change that cut cost without hurting verified quality; worth keeping and reusing.",
                             action="Record what changed (prompt, tools, step limit, model) and apply it to similar workflows.",
                             benefit={"estimated_usd": None, "basis": "Already realised in this period."},
                             confidence=_confidence(a["tasks"] + b["tasks"]),
                             limitations="Before/after comparison, not a controlled experiment: task mix may have changed.",
                             needs_evaluation=False))
    return recs


def all_recommendations(events: list[UsageEvent], outcomes: list[Outcome]) -> list[dict]:
    recs = (excessive_context(events) + expensive_model_for_simple_tasks(events, outcomes)
            + high_retry_workflows(events) + long_agent_runs(events) + low_value_spend(events, outcomes)
            + successful_optimisation(events, outcomes))
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(recs, key=lambda r: (order[r["confidence"]], -((r["potential_benefit"] or {}).get("estimated_usd") or 0)))
