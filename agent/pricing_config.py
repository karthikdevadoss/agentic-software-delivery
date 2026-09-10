"""
Versioned Anthropic API pricing configuration — the single source of truth
for converting REAL captured token usage (never estimated post-run) into an
actual USD cost. Prices are stored per-token (official $/MTok divided by
1,000,000) so call sites never do unit conversion themselves.

Verified directly against the official Anthropic pricing page
(https://www.anthropic.com/pricing, which redirects to
https://claude.com/pricing) on PRICING_VERIFIED_DATE — not recalled from
training data. Prices change over time: re-verify against the live page
before trusting an existing PRICING_VERSION for a new task; add a new
dated entry/version rather than silently editing this one in place, so a
past run's persisted pricing_version always points at the numbers that
were actually used to calculate its cost.
"""

PRICING_VERSION = "anthropic-2026-09-10-v1"
PRICING_VERIFIED_DATE = "2026-09-10"
PRICING_SOURCE = "https://claude.com/pricing (official Anthropic pricing page; www.anthropic.com/pricing redirects here)"

# cache_write below is the 5-minute-TTL rate — the only cache TTL this
# codebase's agent_loop.py ever configures (no 1-hour cache_control anywhere
# in this repo as of PRICING_VERIFIED_DATE). If a 1-hour cache is ever
# introduced, add a separate rate rather than overloading this one.
_PRICING_TABLE = {
    ("anthropic", "claude-sonnet-5"): {
        "input": 2.00 / 1_000_000,
        "output": 10.00 / 1_000_000,
        "cache_write": 2.50 / 1_000_000,
        "cache_read": 0.20 / 1_000_000,
    },
}


def get_pricing(provider: str, model: str):
    """Returns the per-token rate dict for (provider, model), or None if
    this exact pair has no verified entry — never falls back to a guess."""
    return _PRICING_TABLE.get((provider, model))


def calculate_cost(provider, model, input_tokens=0, output_tokens=0,
                    cache_read_tokens=0, cache_write_tokens=0) -> dict:
    """Returns {'available': True, 'total_usd': ..., ...provenance} for a
    known (provider, model), or {'available': False, 'reason': ...} for an
    unknown one. Never fabricates a price for a model not in the table —
    an unpriceable model must show as unpriceable, not as $0.00."""
    pricing = get_pricing(provider, model)
    if pricing is None:
        return {
            "available": False,
            "reason": f"No verified pricing entry for provider={provider!r} model={model!r}",
            "pricing_version": PRICING_VERSION,
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
        "pricing_version": PRICING_VERSION,
        "pricing_verified_date": PRICING_VERIFIED_DATE,
        "pricing_source": PRICING_SOURCE,
        "provider": provider,
        "model": model,
    }
