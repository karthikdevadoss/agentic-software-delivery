"""Request handling for /api/ai-usage/* -- pure functions, no web framework.

Who sees what:
  * Anyone (no owner token) is a `demo_viewer`: dataset=demo only. Asking for
    dataset=live returns 403, never a silent fallback to demo.
  * The owner token (owner_auth) is the `owner`: live data and data entry.
Every response says which dataset it is, carries the demo label when it is
demo, and lists how each kind of number was measured.
"""
from __future__ import annotations

import functools
import uuid
from datetime import date, datetime, timezone

from . import access, analytics, compare, demo, learning, recommend
from .outcomes import OUTCOME_TYPES, Evidence, Outcome

PROVENANCE_LEGEND = {
    "provider_reported": "Reported by the AI provider in its own usage data.",
    "app_measured": "Measured by this application (timers, counters).",
    "estimated": "Computed estimate; the method is shown next to the number.",
    "estimated_partial": "Estimate with some inputs unknown (e.g. an interrupted stream).",
    "estimated_back_applied": "Estimated with the earliest verified price, assuming it had not changed.",
    "imported": "Imported from an exported file or local transcript.",
    "manual": "Entered by a person.",
    "demo": "Fictional demonstration data.",
    "unavailable": "Not reported by anyone; shown as unknown, never as zero.",
}
BILLING_LEGEND = {
    "metered_api": "Pay-per-token API usage. Cost shown is the list-price ESTIMATE, not an invoice.",
    "subscription": "Flat subscription fee.",
    "subscription_allowance": "Usage counted against a plan allowance (rarely exposed by providers).",
    "equivalent_api_value": "What subscription usage WOULD cost at API list price. Not money spent.",
    "unknown": "Not known.",
}
FILTERS = ("org_id", "team_id", "user_id", "project_id", "provider", "model", "feature", "activity_category",
           "workflow_id", "billing_category")


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def principal_for(is_owner: bool) -> access.Principal:
    return access.Principal("owner") if is_owner else access.Principal("demo_viewer")


@functools.lru_cache(maxsize=4)
def _demo_for(day: str) -> dict:
    return demo.build(today=date.fromisoformat(day))


def _today() -> date:
    return datetime.now(timezone.utc).date()


def load(principal: access.Principal, dataset: str, live_loader=None) -> dict:
    """{"events", "outcomes", "learning", "budgets", "label"} scoped to the principal."""
    if dataset not in ("demo", "live"):
        raise ApiError(400, "dataset must be demo or live")
    if dataset == "live":
        if not principal.may_see_live:
            raise ApiError(403, "live data needs the owner token; the public view is the demo dataset")
        data = (live_loader or _live)()
        label = None
    else:
        data = _demo_for(_today().isoformat())
        label = data["label"]
    return {"events": access.scope(principal, data["events"]),
            "outcomes": access.scope(principal, data["outcomes"]),
            "learning": data["learning"] if (dataset == "demo" or principal.role == "owner") else [],
            "budgets": data.get("budgets", []), "label": label, "dataset": dataset}


def _live() -> dict:
    from . import store
    return {"events": store.load_events(), "outcomes": store.load_outcomes(), "learning": store.load_learning(),
            "budgets": []}


def _window(params: dict) -> tuple[str | None, str | None]:
    rng = params.get("range") or "30d"
    if rng not in analytics.RANGES:
        raise ApiError(400, f"range must be one of {analytics.RANGES}")
    start, end = analytics.date_range(rng, today=_today(), start=params.get("start"), end=params.get("end"))
    for v in (start, end):
        if v:
            try:
                date.fromisoformat(v)
            except ValueError as exc:
                raise ApiError(400, "start/end must be YYYY-MM-DD") from exc
    return start, end


def _filtered(principal, params, data):
    try:
        access.check_filters(principal, org_id=params.get("org_id"), team_id=params.get("team_id"),
                             user_id=params.get("user_id"))
    except access.Forbidden as exc:
        raise ApiError(403, str(exc)) from exc
    start, end = _window(params)
    eq = {k: params.get(k) for k in FILTERS if params.get(k)}
    events = analytics.filter_events(data["events"], start=start, end=end, **eq)
    task_ids = {e.task_id for e in events if e.task_id}
    outcomes = [o for o in data["outcomes"] if o.task_id in task_ids]
    return events, outcomes, start, end


def _envelope(data, start, end, body: dict) -> dict:
    return {"dataset": data["dataset"], "demo_label": data["label"], "window": {"start": start, "end": end},
            "provenance_legend": PROVENANCE_LEGEND, "billing_legend": BILLING_LEGEND, **body}


def overview(principal, params, live_loader=None) -> dict:
    data = load(principal, params.get("dataset", "demo"), live_loader)
    events, outcomes, start, end = _filtered(principal, params, data)
    budget = None
    org_budget = next((b for b in data["budgets"] if b["scope"] == "org"), None)
    if org_budget:
        month_events = analytics.filter_events(data["events"], start=_today().replace(day=1).isoformat(),
                                               end=_today().isoformat())
        spent = analytics.totals(month_events)["cost_estimated"] or 0.0
        budget = {**org_budget, "spent": round(spent, 6)}
    return _envelope(data, start, end, {
        "overview": analytics.overview(events, outcomes, budget),
        "daily": analytics.daily(events, outcomes),
        "by_billing_category": analytics.breakdown(events, "billing_category"),
        "budgets": data["budgets"],
        "filters_available": {k: sorted({str(getattr(e, k) if k != "model" else e.model) for e in data["events"]
                                         if (e.model if k == "model" else getattr(e, k))}) for k in
                              ("team_id", "user_id", "project_id", "provider", "model", "activity_category")}})


def breakdown(principal, params, live_loader=None) -> dict:
    by = params.get("by", "model")
    if by not in analytics.DIMENSIONS:
        raise ApiError(400, f"by must be one of {analytics.DIMENSIONS}")
    data = load(principal, params.get("dataset", "demo"), live_loader)
    events, outcomes, start, end = _filtered(principal, params, data)
    return _envelope(data, start, end, {"by": by, "rows": analytics.breakdown(events, by, outcomes)})


def sessions(principal, params, live_loader=None) -> dict:
    data = load(principal, params.get("dataset", "demo"), live_loader)
    events, _, start, end = _filtered(principal, params, data)
    rows = analytics.sessions(events)
    return _envelope(data, start, end, {"sessions": rows[:200], "total_sessions": len(rows)})


def session_detail(principal, params, session_id, live_loader=None) -> dict:
    data = load(principal, params.get("dataset", "demo"), live_loader)
    d = analytics.session_detail(data["events"], session_id, data["outcomes"])
    if d is None:
        raise ApiError(404, "no such session in this view")
    return _envelope(data, None, None, {"session": d})


def recommendations(principal, params, live_loader=None) -> dict:
    data = load(principal, params.get("dataset", "demo"), live_loader)
    events, outcomes, start, end = _filtered(principal, params, data)
    return _envelope(data, start, end, {"recommendations": recommend.all_recommendations(events, outcomes),
                                        "note": "Deterministic rules over recorded data; no model is called. "
                                                "Advice only: routing and budgets are never changed automatically."})


def models(principal, params, live_loader=None) -> dict:
    data = load(principal, params.get("dataset", "demo"), live_loader)
    events, outcomes, start, end = _filtered(principal, params, data)
    return _envelope(data, start, end, {"categories": compare.compare(events, outcomes)})


def learning_view(principal, params, live_loader=None) -> dict:
    data = load(principal, params.get("dataset", "demo"), live_loader)
    events, _, start, end = _filtered(principal, params, data)
    records = [r for r in data["learning"] if not start or (r.timestamp or "")[:10] >= start]
    cost = {k: v for k, v in analytics.cost_by(events, "session_id").items() if k != "(unattributed)"}
    return _envelope(data, start, end, {"learning": learning.metrics(records, cost)})


# --- owner-only writes ------------------------------------------------------------

def record_outcome(principal, body: dict, saver=None) -> dict:
    if not principal.may_write:
        raise ApiError(403, "recording outcomes needs the owner token")
    required = ("task_id", "outcome_type", "status", "evidence")
    missing = [k for k in required if not body.get(k)]
    if missing:
        raise ApiError(400, f"missing fields: {missing}")
    if body["status"] not in ("completed", "failed", "abandoned", "in_progress"):
        raise ApiError(400, "status must be completed, failed, abandoned or in_progress")
    if body["evidence"] not in {e.value for e in Evidence}:
        raise ApiError(400, f"evidence must be one of {[e.value for e in Evidence]}")
    if body.get("time_saved_minutes") is not None and body.get("time_saved_source") not in ("measured", "estimated"):
        raise ApiError(400, "time_saved_minutes needs time_saved_source: measured or estimated")
    allowed = {f for f in Outcome.__dataclass_fields__} - {"outcome_id", "dataset", "timestamp"}
    extra = set(body) - allowed
    if extra:
        raise ApiError(400, f"unknown fields: {sorted(extra)}")
    o = Outcome(outcome_id="oc_" + uuid.uuid4().hex[:20], **body)
    (saver or _save_outcome)(o, "owner")
    return {"recorded": o.to_dict()}


def _save_outcome(o, actor):
    from . import store
    store.save_outcome(o, actor)


def record_learning(principal, body: dict, saver=None) -> dict:
    if not principal.may_write:
        raise ApiError(403, "recording learning needs the owner token")
    try:
        if "import" in body:
            imp = body["import"] or {}
            records = learning.parse_import(imp.get("text", ""), imp.get("format", ""), user_id="owner")
        else:
            rows = body.get("records") or []
            for r in rows:
                if not isinstance(r, dict) or {"source", "user_id"} & set(r):
                    raise ValueError("records may not set source or user_id; the server assigns them")
            records = [learning.LearningRecord(**{**r, "user_id": "owner", "source": "manual"}) for r in rows]
    except (ValueError, TypeError) as exc:
        raise ApiError(400, str(exc)) from exc
    if not records:
        raise ApiError(400, "no records")
    n = (saver or _save_learning)(records, "owner")
    return {"recorded": n, "source": records[0].source}


def _save_learning(records, actor):
    from . import store
    return store.save_learning(records, actor)


def meta() -> dict:
    return {"outcome_types": OUTCOME_TYPES, "evidence": [e.value for e in Evidence],
            "learning_events": list(learning.EVENTS), "learning_evidence": ["assessment", "reviewed_exercise",
                                                                          "self_report", "ai_explanation"],
            "provenance_legend": PROVENANCE_LEGEND, "billing_legend": BILLING_LEGEND,
            "ranges": list(analytics.RANGES), "dimensions": list(analytics.DIMENSIONS)}
