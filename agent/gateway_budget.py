"""Platform-wide spend and rate policy, enforced inside reasoning_gateway.

Every call that goes through reasoning_gateway.call() with the real provider
client reserves against four limits BEFORE the provider is contacted:

  1. per-request cap  -- the call's worst-case cost estimate may not exceed
                         GATEWAY_PER_REQUEST_USD_CAP;
  2. per-run cap      -- reservations sharing a run_id may not exceed
                         GATEWAY_PER_RUN_USD_CAP (skipped when no run_id given);
  3. daily cap        -- all reservations in the UTC day may not exceed
                         GATEWAY_DAILY_USD_CAP;
  4. rate limit       -- at most GATEWAY_RATE_LIMIT_CALLS reservations per
                         GATEWAY_RATE_WINDOW_SECONDS.

The reservation is written first (durably, see budget_store.py) and is the
WORST-CASE estimate: input tokens ~ characters/3 at the input price plus the
full max_tokens at the output price. When the provider returns real usage the
row is settled to the measured cost; when the call raises, the estimate stays,
because a failed call can still be billed. A model with no verified price in
pricing_config is reserved at GATEWAY_UNPRICED_RESERVE_USD rather than at 0.

HOW THIS RELATES TO triage_budget AND si_budget
Those two remain as PER-ENDPOINT, per-visitor request-count policies (fairness
between visitors, and a hard "N answers a day" for a public page). They now
store their counters in the same durable file, in their own scopes ('triage',
'si'), so they also survive a restart. This module is the PLATFORM backstop in
the 'gateway' scope. A Triage click therefore reserves in both: the endpoint
policy first (cheap, request-count) and the gateway policy second (dollars and
rate). They do not share a counter, so they cannot disagree about one number;
whichever limit is hit first refuses the call.

COVERAGE, honestly: every billed path through reasoning_gateway -- call() AND
converse() (agent_loop.py, backend_planning.py) -- reserves here before the
provider is contacted. Calls with an injected create_fn (a test double) are not
metered unless enforce_budget=True is passed. A long agent_loop conversation is
estimated from its whole message history, so it can be refused by the
per-request cap (GATEWAY_PER_REQUEST_USD_CAP) even when the daily cap has room.

Defaults are policy values, not measured spend. Override with the env vars
above; a malformed value falls back to the default (a typo must not lift a
cap) and 0 refuses everything.
"""
from __future__ import annotations

import math
import os
import time

import budget_store
import pricing_config

SCOPE = "gateway"

DEFAULT_DAILY_USD_CAP = 5.00
DEFAULT_PER_RUN_USD_CAP = 1.00
DEFAULT_PER_REQUEST_USD_CAP = 0.50
DEFAULT_RATE_CALLS = 20
DEFAULT_RATE_WINDOW_SECONDS = 60
DEFAULT_UNPRICED_RESERVE_USD = 0.05


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if math.isfinite(value) and value >= 0 else default


def limits() -> dict:
    return {
        "daily_usd_cap": _env_float("GATEWAY_DAILY_USD_CAP", DEFAULT_DAILY_USD_CAP),
        "per_run_usd_cap": _env_float("GATEWAY_PER_RUN_USD_CAP", DEFAULT_PER_RUN_USD_CAP),
        "per_request_usd_cap": _env_float("GATEWAY_PER_REQUEST_USD_CAP", DEFAULT_PER_REQUEST_USD_CAP),
        "rate_limit_calls": int(_env_float("GATEWAY_RATE_LIMIT_CALLS", DEFAULT_RATE_CALLS)),
        "rate_window_seconds": max(1, int(_env_float("GATEWAY_RATE_WINDOW_SECONDS", DEFAULT_RATE_WINDOW_SECONDS))),
        "unpriced_reserve_usd": _env_float("GATEWAY_UNPRICED_RESERVE_USD", DEFAULT_UNPRICED_RESERVE_USD),
    }


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _seconds_until_utc_midnight() -> int:
    return int(86400 - (time.time() % 86400)) + 1


def estimate_usd(provider: str, model: str, system_prompt: str, user_message: str,
                 max_tokens: int) -> dict:
    """Worst-case cost of one call. An ESTIMATE, labelled as such."""
    pricing = pricing_config.get_pricing(provider, model)
    if pricing is None:
        return {"usd": limits()["unpriced_reserve_usd"], "basis": "unpriced-model-flat-reserve"}
    in_tokens = math.ceil((len(system_prompt or "") + len(user_message or "")) / 3)
    usd = in_tokens * pricing["input"] + max(int(max_tokens), 0) * pricing["output"]
    return {"usd": round(usd, 6), "basis": "chars/3 input + full max_tokens output"}


def reserve(provider: str, model: str, system_prompt: str, user_message: str,
            max_tokens: int, run_id: str | None = None) -> dict:
    """Fail closed: if the budget store cannot be reached, refuse the call.
    A cap that cannot be checked counts as reached (see budget_store.py)."""
    try:
        return _reserve(provider, model, system_prompt, user_message, max_tokens, run_id)
    except budget_store.StoreUnavailable as exc:
        return {"allowed": False, "status": "BUDGET_STORE_UNAVAILABLE",
                "message": f"{exc}; refusing the call rather than running it unchecked",
                "retry_after": 30}


def _reserve(provider: str, model: str, system_prompt: str, user_message: str,
             max_tokens: int, run_id: str | None = None) -> dict:
    """Atomically check every limit and, if all pass, record the reservation.
    Returns {"allowed": True, "reservation_id", "reserved_usd"} or
    {"allowed": False, "status", "message", "retry_after"}."""
    lim = limits()
    est = estimate_usd(provider, model, system_prompt, user_message, max_tokens)
    day, ts = _today(), budget_store.now()

    def refuse(status, message, retry_after):
        return {"allowed": False, "status": status, "message": message,
                "retry_after": retry_after}

    with budget_store.transaction() as tx:
        if est["usd"] > lim["per_request_usd_cap"]:
            return refuse("REQUEST_CAP_REACHED",
                          f"estimated worst-case cost ${est['usd']:.4f} exceeds the per-request cap "
                          f"${lim['per_request_usd_cap']:.2f}; lower max_tokens or shorten the prompt", 0)
        if lim["rate_limit_calls"] <= 0 or tx.count_since(
                SCOPE, ts - lim["rate_window_seconds"]) >= lim["rate_limit_calls"]:
            return refuse("RATE_LIMITED",
                          f"rate limit of {lim['rate_limit_calls']} calls per "
                          f"{lim['rate_window_seconds']}s reached", lim["rate_window_seconds"])
        if tx.usd(SCOPE, day) + est["usd"] > lim["daily_usd_cap"]:
            return refuse("DAILY_CAP_REACHED",
                          f"daily gateway spend cap ${lim['daily_usd_cap']:.2f} reached "
                          f"(reserved+settled today ${tx.usd(SCOPE, day):.4f})",
                          _seconds_until_utc_midnight())
        if run_id is not None and tx.usd(SCOPE, day, run_id=run_id) + est["usd"] > lim["per_run_usd_cap"]:
            return refuse("RUN_CAP_REACHED",
                          f"per-run cap ${lim['per_run_usd_cap']:.2f} reached for run {run_id!r}", 0)
        rid = tx.insert(SCOPE, day, ts, run_id=run_id, usd=est["usd"])
    return {"allowed": True, "reservation_id": rid, "reserved_usd": est["usd"]}


def settle(reservation_id: int, actual_usd: float) -> None:
    """Replace a reservation's estimate with the measured cost. If the store
    is unreachable the worst-case reservation simply stays in place: spend is
    over-reported, never under-reported, and the paid call is not failed."""
    try:
        with budget_store.transaction() as tx:
            tx.settle(reservation_id, round(float(actual_usd), 6))
    except budget_store.StoreUnavailable:
        pass


def status() -> dict:
    """Remaining platform budget for /usage. Spent = settled actuals plus
    outstanding/failed-call reservations, so it never under-reports."""
    lim, day = limits(), _today()
    try:
        return _status(lim, day)
    except budget_store.StoreUnavailable as exc:
        return {"day_utc": day, "store_available": False, "error": str(exc),
                "daily_usd_cap": lim["daily_usd_cap"], "per_run_usd_cap": lim["per_run_usd_cap"],
                "per_request_usd_cap": lim["per_request_usd_cap"],
                "rate_limit_calls": lim["rate_limit_calls"],
                "rate_window_seconds": lim["rate_window_seconds"],
                "figures_are": "unavailable: billed calls are being refused until the store is reachable"}


def _status(lim: dict, day: str) -> dict:
    with budget_store.transaction() as tx:
        spent = tx.usd(SCOPE, day)
        calls = tx.count(SCOPE, day)
        recent = tx.count_since(SCOPE, budget_store.now() - lim["rate_window_seconds"])
    return {
        "day_utc": day,
        "calls_today": calls,
        "spent_or_reserved_usd": round(spent, 6),
        "daily_usd_cap": lim["daily_usd_cap"],
        "remaining_usd": round(max(lim["daily_usd_cap"] - spent, 0.0), 6),
        "per_run_usd_cap": lim["per_run_usd_cap"],
        "per_request_usd_cap": lim["per_request_usd_cap"],
        "rate_limit_calls": lim["rate_limit_calls"],
        "rate_window_seconds": lim["rate_window_seconds"],
        "rate_calls_remaining": max(lim["rate_limit_calls"] - recent, 0),
        "figures_are": "reserved worst-case estimates until a call settles to its measured cost",
    }


def _reset_for_tests() -> None:
    budget_store.clear_scope(SCOPE)
