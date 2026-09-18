"""
Versioned Anthropic API pricing configuration — the single source of truth
for converting REAL captured token usage (never estimated post-run) into an
actual USD cost. Prices are stored per-token (official $/MTok divided by
1,000,000) so call sites never do unit conversion themselves.

Verified directly against the official Anthropic pricing page
(https://www.anthropic.com/pricing, which redirects to
https://claude.com/pricing) on each entry's effective_date — not recalled
from training data. Prices change over time: re-verify against the live
page before trusting an existing entry for a new task; add a NEW dated
entry to the relevant (provider, model) list rather than editing an
existing one in place (Owner instruction, task-level AI cost accounting,
2026-09-18: a past run's persisted pricing_version must always point at
the numbers that were actually used to calculate its cost, and a future
price change must never silently rewrite historical cost). The current/
latest entry per (provider, model) is what get_pricing()/calculate_cost()
use by default; pass as_of=<ISO date> to select whichever entry was
effective on a specific past date instead.
"""

# cache_write below is the 5-minute-TTL rate — the only cache TTL this
# codebase's agent_loop.py ever configures (no 1-hour cache_control anywhere
# in this repo as of the entries below). If a 1-hour cache is ever
# introduced, add a separate rate rather than overloading this one.
#
# Each (provider, model) maps to a list of dated entries, OLDEST FIRST.
# Never mutate an existing entry once it has ever been used to calculate a
# real cost — append a new one instead.
_PRICING_HISTORY: dict[tuple[str, str], list[dict]] = {
    ("anthropic", "claude-sonnet-5"): [
        {
            "effective_date": "2026-09-10",
            "version": "anthropic-2026-09-10-v1",
            "source": "https://claude.com/pricing (official Anthropic pricing page; www.anthropic.com/pricing redirects here)",
            "input": 2.00 / 1_000_000,
            "output": 10.00 / 1_000_000,
            "cache_write": 2.50 / 1_000_000,
            "cache_read": 0.20 / 1_000_000,
        },
    ],
}

# Backward-compatible module-level constants describing the CURRENT/latest
# entry for this codebase's one actively-used model — existing callers
# that read these directly (rather than through get_pricing/calculate_cost)
# keep working unchanged. If a second (provider, model) pair is ever added,
# these stay pointed at claude-sonnet-5 specifically; prefer
# get_pricing(provider, model) for anything not hardcoded to that model.
_LATEST_ANTHROPIC_SONNET_5 = _PRICING_HISTORY[("anthropic", "claude-sonnet-5")][-1]
PRICING_VERSION = _LATEST_ANTHROPIC_SONNET_5["version"]
PRICING_VERIFIED_DATE = _LATEST_ANTHROPIC_SONNET_5["effective_date"]
PRICING_SOURCE = _LATEST_ANTHROPIC_SONNET_5["source"]


def get_pricing(provider: str, model: str, as_of: str | None = None):
    """Returns the per-token rate dict for (provider, model) effective on
    `as_of` (an ISO date string; None means "the current/latest entry"),
    or None if no entry qualifies -- never falls back to a guess. If
    as_of predates every known entry for this (provider, model), returns
    None rather than incorrectly applying a later rate to an earlier
    date."""
    history = _PRICING_HISTORY.get((provider, model))
    if not history:
        return None
    if as_of is None:
        return history[-1]
    candidates = [e for e in history if e["effective_date"] <= as_of]
    if not candidates:
        return None
    return max(candidates, key=lambda e: e["effective_date"])


def calculate_cost(provider, model, input_tokens=0, output_tokens=0,
                    cache_read_tokens=0, cache_write_tokens=0, as_of=None) -> dict:
    """Returns {'available': True, 'total_usd': ..., ...provenance} for a
    known (provider, model) [effective on `as_of`, or the current/latest
    entry if as_of is None], or {'available': False, 'reason': ...} for an
    unknown one. Never fabricates a price for a model not in the table —
    an unpriceable model must show as unpriceable, not as $0.00. The
    returned pricing_version/pricing_verified_date/pricing_source always
    describe the SPECIFIC entry actually used, so a caller recalculating a
    historical run's cost with as_of=<that run's date> gets back the real
    rate that applied then, not today's rate mislabeled with an old
    version string."""
    pricing = get_pricing(provider, model, as_of=as_of)
    if pricing is None:
        return {
            "available": False,
            "reason": f"No verified pricing entry for provider={provider!r} model={model!r}"
                      + (f" as_of={as_of!r}" if as_of else ""),
        }
    total_usd = (
        (input_tokens or 0) * pricing["input"]
        + (output_tokens or 0) * pricing["output"]
        + (cache_read_tokens or 0) * pricing["cache_read"]
        + (cache_write_tokens or 0) * pricing["cache_write"]
    )
    return {
        "available": True,
        "total_usd": round(total_usd, 6),
        "pricing_version": pricing["version"],
        "pricing_verified_date": pricing["effective_date"],
        "pricing_source": pricing["source"],
        "provider": provider,
        "model": model,
    }
