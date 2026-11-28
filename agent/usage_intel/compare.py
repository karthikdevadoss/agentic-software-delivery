"""Model comparison by task category, and a routing SUGGESTION.

For each (activity category, model): requests, cost, tokens, latency, error
and retry rates, verified success rate and cost per verified success. The
suggestion is the cheapest model that meets a quality bar (verified success
rate within `tolerance` of the best observed, with at least `min_tasks`
tasks). It is advice only: production routing is never changed from here.
"""
from __future__ import annotations

from collections import defaultdict

from .analytics import leaves, totals
from .events import UsageEvent
from .outcomes import Outcome


def compare(events: list[UsageEvent], outcomes: list[Outcome], min_tasks: int = 10,
            tolerance: float = 0.03) -> list[dict]:
    out_by_task = {o.task_id: o for o in outcomes}
    groups = defaultdict(list)
    for e in leaves(events):
        if e.activity_category and e.model:
            groups[(e.activity_category, e.model)].append(e)
    by_cat = defaultdict(list)
    for (cat, model), evs in groups.items():
        t = totals(evs)
        tasks = {e.task_id for e in evs if e.task_id in out_by_task}
        ver = sum(out_by_task[x].verified_success for x in tasks)
        rate = ver / len(tasks) if tasks else None
        tok, k = 0, 0
        for e in evs:
            if e.total_tokens is not None:
                tok += e.total_tokens
                k += 1
        by_cat[cat].append({"model": model, "requests": t["requests"], "tasks": len(tasks),
                            "cost_estimated": t["cost_estimated"], "avg_tokens": round(tok / k) if k else None,
                            "avg_latency_ms": t["avg_latency_ms"], "error_rate": t["error_rate"],
                            "retry_rate": t["retry_rate"], "verified_success_rate": round(rate, 4) if rate is not None else None,
                            "cost_per_verified_success": round(t["cost_estimated"] / ver, 6) if (ver and t["cost_estimated"] is not None) else None})
    result = []
    for cat, rows in by_cat.items():
        eligible = [r for r in rows if r["tasks"] >= min_tasks and r["verified_success_rate"] is not None
                    and r["cost_per_verified_success"] is not None]
        suggestion = None
        if len(eligible) >= 2:
            best = max(r["verified_success_rate"] for r in eligible)
            ok = [r for r in eligible if r["verified_success_rate"] >= best - tolerance]
            pick = min(ok, key=lambda r: r["cost_per_verified_success"])
            suggestion = {"model": pick["model"],
                          "reason": (f"lowest cost per verified success among models within {tolerance:.0%} of the best "
                                     f"verified success rate ({best:.0%}), each with >= {min_tasks} tasks"),
                          "advisory_only": True,
                          "caveat": "Observational data, not a controlled evaluation; run an A/B evaluation before changing routing."}
        result.append({"activity_category": cat, "models": sorted(rows, key=lambda r: r["cost_per_verified_success"] or 9e9),
                       "suggestion": suggestion})
    return sorted(result, key=lambda r: r["activity_category"])
