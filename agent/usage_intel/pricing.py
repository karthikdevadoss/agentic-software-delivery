"""Cost estimation for UsageEvents on top of agent/pricing_config.py.

The price table lives in pricing_config (one versioned source of truth, dated
entries, never edited in place). This module adds what a per-request
estimate needs and says exactly how each number was produced:

  * the price in force ON THE EVENT'S DATE (pricing_config as_of), so a price
    change never rewrites history;
  * 1-hour cache writes at their own rate when the provider reported the split;
  * long-context tiers (e.g. Claude Haiku 5.5 over 100,000 prompt tokens, where
    prompt length counts cache reads and writes);
  * partial costs when a bucket is unknown (e.g. an interrupted stream), and
    no cost at all for a model with no verified price -- never $0.00.

The result is an ESTIMATED API EXPENDITURE at list price. It is not an
invoice and not the provider's internal cost.
"""
from __future__ import annotations

import pricing_config

from .events import Source, UsageEvent


def _rates_for(entry: dict, prompt_tokens: int) -> tuple[dict, bool]:
    threshold = entry.get("long_context_threshold")
    if threshold is not None and prompt_tokens > threshold:
        return {**entry, **entry["long_context"]}, True
    return entry, False


def estimate(ev: UsageEvent) -> UsageEvent:
    """Fill ev.cost_estimated / pricing_version / pricing_effective_date /
    cost_method in place and return ev. Containers and tool calls cost nothing
    themselves (their children do)."""
    if not ev.is_leaf_model_call:
        return ev
    as_of = (ev.timestamp or "")[:10] or None
    entry = pricing_config.get_pricing(ev.provider or "", ev.model or "", as_of=as_of)
    back_applied = False
    if entry is None:
        # No price verified as in force on that date. If a later verified price
        # exists, apply the EARLIEST one and say so: an estimate, explicitly
        # assuming the price had not changed. pricing_config itself stays strict.
        history = pricing_config._PRICING_HISTORY.get((ev.provider or "", ev.model or ""))  # noqa: SLF001
        if history:
            entry, back_applied = history[0], True
    if entry is None:
        ev.cost_estimated = None
        ev.cost_method = f"unpriced: no verified list price for {ev.provider}/{ev.model} on {as_of}"
        ev.provenance["cost_estimated"] = Source.UNAVAILABLE.value
        return ev

    buckets = {f: getattr(ev, f) for f in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")}
    prompt = sum(v or 0 for k, v in buckets.items() if k != "output_tokens")
    rates, long_ctx = _rates_for(entry, prompt)

    split = (ev.provenance or {}).get("cache_write_split") or {}
    w1h = split.get("1h") or 0
    w_total = buckets["cache_write_tokens"] or 0
    w5m = max(w_total - w1h, 0)

    usd = ((buckets["input_tokens"] or 0) * rates["input"]
           + (buckets["output_tokens"] or 0) * rates["output"]
           + (buckets["cache_read_tokens"] or 0) * rates["cache_read"]
           + w5m * rates["cache_write"]
           + w1h * rates.get("cache_write_1h", rates["cache_write"]))
    unknown = [k for k, v in buckets.items() if v is None and k in ("input_tokens", "output_tokens")]

    ev.cost_estimated = round(usd, 8)
    ev.pricing_version = entry["version"]
    ev.pricing_effective_date = entry["effective_date"]
    parts = ["list price x tokens", f"version {entry['version']}"]
    if long_ctx:
        parts.append(f"long-context tier (prompt {prompt} > {entry['long_context_threshold']})")
    if w1h:
        parts.append(f"{w1h} cache-write tokens at the 1-hour rate")
    if unknown:
        parts.append("PARTIAL: " + ", ".join(unknown) + " unknown, not priced")
    if back_applied:
        parts.append(f"BACK-APPLIED: earliest verified price (effective {entry['effective_date']}) "
                     f"used for an event dated {as_of}; the price on that date was not verified")
    ev.cost_method = "; ".join(parts)
    if any(ev.provenance.get(k) == Source.DEMO.value for k in ("input_tokens", "output_tokens")):
        ev.provenance["cost_estimated"] = Source.DEMO.value
    elif unknown:
        ev.provenance["cost_estimated"] = "estimated_partial"
    elif back_applied:
        ev.provenance["cost_estimated"] = "estimated_back_applied"
    else:
        ev.provenance["cost_estimated"] = Source.ESTIMATED.value
    return ev
