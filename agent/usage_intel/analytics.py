"""Pure analytics over UsageEvents and Outcomes. No I/O, so every number can
be checked against hand-computed fixtures.

Rules: only leaf model calls carry tokens and cost (containers never double
count); duplicate event ids count once; every total reports its coverage
("n of m calls reported this"); unknown values are excluded from sums and
averages, never treated as zero.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from .events import UsageEvent
from .outcomes import Outcome, value_metrics

DIMENSIONS = ("org_id", "team_id", "user_id", "project_id", "session_id", "conversation_id", "task_id",
              "workflow_id", "agent_id", "feature", "provider", "model", "activity_category", "billing_category")

RANGES = ("today", "yesterday", "7d", "30d", "month", "custom", "all")


def _day(ts: str | None) -> str | None:
    return ts[:10] if ts else None


def date_range(name: str, *, today: date | None = None, start: str | None = None,
               end: str | None = None) -> tuple[str | None, str | None]:
    """Inclusive [start, end] ISO dates for a named range (UTC days)."""
    today = today or datetime.now(timezone.utc).date()
    if name == "today":
        return today.isoformat(), today.isoformat()
    if name == "yesterday":
        y = today - timedelta(days=1)
        return y.isoformat(), y.isoformat()
    if name == "7d":
        return (today - timedelta(days=6)).isoformat(), today.isoformat()
    if name == "30d":
        return (today - timedelta(days=29)).isoformat(), today.isoformat()
    if name == "month":
        return today.replace(day=1).isoformat(), today.isoformat()
    if name == "custom":
        return start, end
    return None, None


def dedupe(events: list[UsageEvent]) -> list[UsageEvent]:
    seen, out = set(), []
    for e in events:
        if e.event_id in seen:
            continue
        seen.add(e.event_id)
        out.append(e)
    return out


def filter_events(events: list[UsageEvent], *, start: str | None = None, end: str | None = None,
                  **equals) -> list[UsageEvent]:
    out = []
    for e in dedupe(events):
        d = _day(e.timestamp)
        if start and (d is None or d < start):
            continue
        if end and (d is None or d > end):
            continue
        if any(v is not None and (e.model if k == "model" else getattr(e, k, None)) != v for k, v in equals.items()):
            continue
        out.append(e)
    return out


def leaves(events: list[UsageEvent]) -> list[UsageEvent]:
    return [e for e in dedupe(events) if e.is_leaf_model_call]


def _sum_known(values):
    known = [v for v in values if v is not None]
    return (sum(known) if known else None), len(known)


def _avg_known(values):
    known = [v for v in values if v is not None]
    return (sum(known) / len(known) if known else None), len(known)


def totals(events: list[UsageEvent]) -> dict:
    calls = leaves(events)
    n = len(calls)
    out = {"requests": n}
    for f in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "reasoning_tokens"):
        s, k = _sum_known(getattr(e, f) for e in calls)
        out[f] = s
        out[f + "_coverage"] = f"{k} of {n}"
    tot, k = _sum_known(e.total_tokens for e in calls)
    out["total_tokens"], out["total_tokens_coverage"] = tot, f"{k} of {n}"
    cost, k = _sum_known(e.cost_estimated for e in calls)
    out["cost_estimated"] = round(cost, 6) if cost is not None else None
    out["cost_coverage"] = f"{k} of {n} calls priced"
    rep, kr = _sum_known(e.cost_reported for e in calls)
    out["cost_reported"] = round(rep, 6) if rep is not None else None
    out["cost_reported_coverage"] = f"{kr} of {n}"
    known_outcome = [e for e in calls if e.success is not None]
    ok = sum(1 for e in known_outcome if e.success)
    out["successful_requests"] = ok
    out["error_rate"] = round(1 - ok / len(known_outcome), 4) if known_outcome else None
    out["retry_rate"] = round(sum(1 for e in calls if e.is_retry) / n, 4) if n else None
    lat, kl = _avg_known(e.duration_ms for e in calls)
    out["avg_latency_ms"] = round(lat, 1) if lat is not None else None
    out["latency_coverage"] = f"{kl} of {n}"
    out["avg_cost_per_request"] = round(cost / k, 6) if (cost is not None and k) else None
    out["sessions"] = len({e.session_id for e in calls if e.session_id})
    out["tasks"] = len({e.task_id for e in calls if e.task_id})
    out["fallbacks"] = sum(1 for e in calls if e.fallback_from_model)
    out["tool_calls"] = _sum_known(e.tool_calls for e in calls)[0]
    return out


def cost_by(events: list[UsageEvent], key: str) -> dict[str, float | None]:
    acc: dict[str, list] = defaultdict(list)
    for e in leaves(events):
        k = e.model if key == "model" else getattr(e, key, None)
        acc[k or "(unattributed)"].append(e.cost_estimated)
    return {k: (round(s, 6) if s is not None else None) for k, (s, _) in
            ((k, _sum_known(v)) for k, v in acc.items())}


def breakdown(events: list[UsageEvent], key: str, outcomes: list[Outcome] | None = None) -> list[dict]:
    if key not in DIMENSIONS:
        raise ValueError(f"unknown dimension {key!r}")
    groups: dict[str, list[UsageEvent]] = defaultdict(list)
    for e in leaves(events):
        k = e.model if key == "model" else getattr(e, key, None)
        groups[k or "(unattributed)"].append(e)
    rows = []
    for k, evs in groups.items():
        t = totals(evs)
        row = {"key": k, **{f: t[f] for f in ("requests", "cost_estimated", "cost_coverage", "input_tokens",
                                               "output_tokens", "cache_read_tokens", "error_rate", "retry_rate",
                                               "avg_latency_ms")}}
        if outcomes is not None:
            tasks = {e.task_id for e in evs if e.task_id}
            mine = [o for o in outcomes if o.task_id in tasks]
            ver = sum(1 for o in mine if o.verified_success)
            row["verified_successes"] = ver
            row["cost_per_verified_success"] = (round(t["cost_estimated"] / ver, 6)
                                                if (ver and t["cost_estimated"] is not None) else None)
        rows.append(row)
    rows.sort(key=lambda r: -(r["cost_estimated"] or 0))
    return rows


def daily(events: list[UsageEvent], outcomes: list[Outcome] | None = None) -> list[dict]:
    by_day: dict[str, list[UsageEvent]] = defaultdict(list)
    for e in leaves(events):
        by_day[_day(e.timestamp)].append(e)
    ver_by_day: dict[str, int] = defaultdict(int)
    done_by_day: dict[str, int] = defaultdict(int)
    for o in outcomes or []:
        d = _day(o.timestamp)
        if d is None:
            continue  # undated outcomes count in totals, not on the daily chart
        if o.status == "completed":
            done_by_day[d] += 1
        if o.verified_success:
            ver_by_day[d] += 1
    out = []
    for d in sorted(k for k in set(by_day) | set(done_by_day) if k):
        t = totals(by_day.get(d, []))
        ver = ver_by_day.get(d, 0)
        out.append({"day": d, "requests": t["requests"], "cost_estimated": t["cost_estimated"],
                    "total_tokens": t["total_tokens"], "error_rate": t["error_rate"],
                    "avg_latency_ms": t["avg_latency_ms"], "tasks_completed": done_by_day.get(d, 0),
                    "verified_successes": ver,
                    "cost_per_verified_success": (round(t["cost_estimated"] / ver, 6)
                                                  if (ver and t["cost_estimated"] is not None) else None),
                    "models": sorted({e.model for e in by_day.get(d, []) if e.model})})
    return out


def sessions(events: list[UsageEvent]) -> list[dict]:
    groups: dict[str, list[UsageEvent]] = defaultdict(list)
    for e in dedupe(events):
        if e.session_id:
            groups[e.session_id].append(e)
    rows = []
    for sid, evs in groups.items():
        calls = leaves(evs)
        t = totals(evs)
        stamps = sorted(e.timestamp for e in evs if e.timestamp)
        rows.append({"session_id": sid,
                     "purpose": next((e.activity_category for e in evs if e.activity_category), None),
                     "user_id": next((e.user_id for e in evs if e.user_id), None),
                     "requests": t["requests"], "cost_estimated": t["cost_estimated"],
                     "input_tokens": t["input_tokens"], "output_tokens": t["output_tokens"],
                     "models": sorted({e.model for e in calls if e.model}),
                     "retries": sum(1 for e in calls if e.is_retry),
                     "errors": sum(1 for e in calls if e.success is False),
                     "tool_calls": t["tool_calls"],
                     "started": stamps[0] if stamps else None, "ended": stamps[-1] if stamps else None})
    rows.sort(key=lambda r: -(r["cost_estimated"] or 0))
    return rows


def session_detail(events: list[UsageEvent], session_id: str, outcomes: list[Outcome] | None = None) -> dict | None:
    evs = [e for e in dedupe(events) if e.session_id == session_id]
    if not evs:
        return None
    calls = leaves(evs)
    t = totals(evs)
    priced = [e for e in calls if e.cost_estimated is not None]
    top = sorted(priced, key=lambda e: -e.cost_estimated)[:5]
    share = (lambda c: round(c / t["cost_estimated"], 4)) if t["cost_estimated"] else (lambda c: None)
    tasks = {e.task_id for e in evs if e.task_id}
    stamps = sorted(e.timestamp for e in evs if e.timestamp)
    dur = None
    if len(stamps) >= 2:
        f = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
        dur = round((f(stamps[-1]) - f(stamps[0])).total_seconds(), 1)
    return {
        "session_id": session_id, "totals": t,
        "purpose": next((e.activity_category for e in evs if e.activity_category), None),
        "models": sorted({e.model for e in calls if e.model}),
        "duration_seconds": dur,
        "requests": [{**e.to_dict(), "cost_share": share(e.cost_estimated) if e.cost_estimated is not None else None}
                     for e in sorted(calls, key=lambda e: e.timestamp or "")],
        "top_cost_requests": [{"event_id": e.event_id, "model": e.model, "cost_estimated": e.cost_estimated,
                               "cost_share": share(e.cost_estimated), "input_tokens": e.input_tokens,
                               "cache_read_tokens": e.cache_read_tokens,
                               "context_components": e.provenance.get("context_components")} for e in top],
        "outcomes": [o.to_dict() for o in (outcomes or []) if o.task_id in tasks],
    }


def overview(events: list[UsageEvent], outcomes: list[Outcome] | None = None,
             budget: dict | None = None) -> dict:
    t = totals(events)
    outcomes = outcomes or []
    cbt = {}
    for k, v in cost_by(events, "task_id").items():
        if k != "(unattributed)":
            cbt[k] = v
    val = value_metrics(outcomes, cbt)
    out = {**t, "value": val}
    out["avg_cost_per_task"] = val["cost_per_task"]
    out["cost_per_verified_success"] = val["cost_per_verified_success"]
    if budget:
        spent = budget.get("spent") or 0.0
        limit = budget.get("limit")
        out["budget"] = {**budget, "consumed_ratio": round(spent / limit, 4) if limit else None,
                         "remaining": round(max(limit - spent, 0), 6) if limit is not None else None}
    return out
