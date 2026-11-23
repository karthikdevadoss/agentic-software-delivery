from django.contrib.admin.views.decorators import staff_member_required
from django.db import DatabaseError
from django.db.models import Count, Sum
from django.shortcuts import render

from . import sources
from .models import LedgerEvent


@staff_member_required
def index(request):
    return render(request, "ledger/index.html")


@staff_member_required
def spend(request):
    """Aggregates over the real cost_usd / token columns only. Older rows that
    kept cost only inside payload JSONB are NOT counted here (see README)."""
    ctx = {"error": None, "by_model": [], "totals": None, "event_count": 0}
    try:
        qs = LedgerEvent.objects.all()
        ctx["event_count"] = qs.count()
        ctx["by_model"] = list(
            qs.values("provider", "model").annotate(
                events=Count("event_id"), input_tokens=Sum("input_tokens"),
                output_tokens=Sum("output_tokens"), cost_usd=Sum("cost_usd"),
            ).order_by("provider", "model"))
        ctx["totals"] = qs.aggregate(input_tokens=Sum("input_tokens"),
                                     output_tokens=Sum("output_tokens"), cost_usd=Sum("cost_usd"))
    except DatabaseError as exc:
        ctx["error"] = f"Ledger not reachable or table missing: {exc.__class__.__name__}"
    return render(request, "ledger/spend.html", ctx)


@staff_member_required
def budgets(request):
    return render(request, "ledger/budgets.html", {
        "in_memory": sources.in_memory_budgets(), "durable": sources.durable_budget_store()})


@staff_member_required
def evals(request):
    return render(request, "ledger/evals.html", {
        "snapshot": sources.eval_snapshot(), "history": sources.eval_history()})
