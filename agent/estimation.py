"""
Pre-run AI token/cost estimation for Workbench requirements.

A genuine estimate, always clearly labeled ESTIMATED, never a disguised
guess presented as fact. Preferred source: comparable REAL historical
Workbench (trainer) runs sharing the same requirement complexity bucket —
never mock runs (they never call the Anthropic API). Falls back to a
conservative, explicitly-labeled LOW-confidence heuristic when too few
comparable runs exist yet, and only reports ESTIMATE NOT AVAILABLE when
even that heuristic has nothing to key off. Never blocks execution itself —
risk_policy.py alone decides whether a requirement is safe to auto-run;
this module only describes what that run is expected to cost.
"""

import json
from pathlib import Path

import pricing_config

REPO_ROOT = Path(__file__).resolve().parent.parent
RUN_HISTORY_PATH = REPO_ROOT / "agent" / "web_run_history.jsonl"

ESTIMATE_METHOD_VERSION = "estimate-v1-historical-by-complexity"
MIN_HISTORICAL_SAMPLES = 3
DEFAULT_PROVIDER_MODEL = ("anthropic", "claude-sonnet-5")

# Conservative fallback total-token (input+output) ranges, used only when
# fewer than MIN_HISTORICAL_SAMPLES comparable real runs exist yet.
# Deliberately wide — a floor/ceiling guess, not a measurement. In
# practice only TINY/SMALL ever reach here for a real auto-executed run:
# MEDIUM/LARGE are blocked by risk_policy before any execution, so no
# estimate is needed to gate them; the table still covers them so the
# pre-execution assessment view can show a number instead of nothing.
_HEURISTIC_TOTAL_TOKEN_RANGE = {
    "TINY": (3000, 9000),
    "SMALL": (5000, 15000),
    "MEDIUM": (8000, 25000),
    "LARGE": (15000, 45000),
}

# Real historical runs record only combined input+output totals per run,
# not a per-type breakdown by complexity bucket. This assumed split
# (roughly 1/3 input, 2/3 output — investigation + proposal text tends to
# dominate output for this agent) converts a total-token range into an
# approximate cost range. It is an approximation layered on an
# approximation, which is exactly why the result is always labeled
# ESTIMATED, never actual.
_ASSUMED_INPUT_FRACTION = 1 / 3


def _read_history_records() -> list:
    if not RUN_HISTORY_PATH.exists():
        return []
    records = []
    for line in RUN_HISTORY_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _comparable_total_tokens(complexity: str) -> list:
    """Real total (input+output) token counts from past real (non-mock)
    Workbench runs sharing this exact complexity bucket."""
    totals = []
    for r in _read_history_records():
        if r.get("is_mock"):
            continue
        assessment = r.get("risk_assessment") or {}
        usage = r.get("model_usage")
        if assessment.get("complexity") != complexity or not usage:
            continue
        totals.append(usage["input_tokens"] + usage["output_tokens"])
    return totals


def _cost_for_total(total_tokens: int, provider: str, model: str):
    est_input = round(total_tokens * _ASSUMED_INPUT_FRACTION)
    est_output = total_tokens - est_input
    result = pricing_config.calculate_cost(provider, model, input_tokens=est_input, output_tokens=est_output)
    return result["total_usd"] if result["available"] else None


def estimate_run(assessment: dict) -> dict:
    """`assessment` is risk_policy.classify()'s return dict. Returns an
    always-truthful estimate dict — never raises, never fabricates false
    precision. Callers must only invoke this for requirements that will
    actually be executed (decision == 'auto'); it is not a gating
    decision itself."""
    complexity = assessment.get("complexity", "N/A")
    provider, model = DEFAULT_PROVIDER_MODEL

    historical = _comparable_total_tokens(complexity)
    if len(historical) >= MIN_HISTORICAL_SAMPLES:
        low, high = min(historical), max(historical)
        if low == high:  # guard against a degenerate zero-width range
            high = round(low * 1.2) or 1
        confidence = "HIGH" if len(historical) >= 6 else "MEDIUM"
        basis = f"{len(historical)} real historical Workbench run(s) with complexity={complexity}"
    elif complexity in _HEURISTIC_TOTAL_TOKEN_RANGE:
        low, high = _HEURISTIC_TOTAL_TOKEN_RANGE[complexity]
        confidence = "LOW"
        basis = (
            f"conservative heuristic — only {len(historical)} comparable historical run(s) found, "
            f"fewer than the {MIN_HISTORICAL_SAMPLES} needed for a history-based estimate"
        )
    else:
        return {
            "available": False,
            "reason": "ESTIMATE NOT AVAILABLE — requirement complexity not recognized and no comparable history exists.",
            "method_version": ESTIMATE_METHOD_VERSION,
        }

    cost_low = _cost_for_total(low, provider, model)
    cost_high = _cost_for_total(high, provider, model)

    return {
        "available": True,
        "complexity": complexity,
        "risk": assessment.get("risk"),
        "estimated_total_tokens_range": [low, high],
        "estimated_cost_range_usd": [cost_low, cost_high] if cost_low is not None and cost_high is not None else None,
        "confidence": confidence,
        "method_version": ESTIMATE_METHOD_VERSION,
        "basis": basis,
        "pricing_version": pricing_config.PRICING_VERSION,
        "provider": provider,
        "model": model,
    }
