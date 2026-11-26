"""Spend cap for the Incident Triage Lab's model calls (Automation Sprint 4).

POST /api/triage/scenario-{a,b,c}/diagnose and /generate-candidate-patch each
make one paid model call, and until this sprint any visitor could repeat them
without limit. Every such request now passes through check_and_reserve()
BEFORE the model is called:

- per visitor: at most one call every TRIAGE_PER_VISITOR_MIN_SECONDS and at
  most TRIAGE_PER_VISITOR_DAILY_MAX calls per UTC day;
- globally: at most TRIAGE_DAILY_MAX_MODEL_CALLS calls per UTC day across
  all visitors (this one does not depend on identity, so a spoofed
  X-Forwarded-For cannot get past it).

A call is counted when it is reserved, not when it succeeds, because a model
call that fails half-way can still be billed. Setting the daily maximum to 0
switches the model steps off entirely.

Counters live in the durable SQLite store (agent/budget_store.py, scope
'triage'), so a restart no longer resets them. Relationship to the gateway
policy (agent/gateway_budget.py): this is the per-endpoint, per-visitor
request-count policy; the gateway applies a platform-wide dollar/rate cap to
the same call afterwards. They use separate scopes and never share a counter.

Honest limits: durable on one host's filesystem only (a replica with its own
disk, or a host whose disk is replaced on deploy without BUDGET_DB_PATH on a
persistent volume, starts empty). The daily cap bounds call count; it is not
an accounting system.
"""
import os
import time

import budget_store

SCOPE = "triage"

DEFAULT_DAILY_MAX = 40
DEFAULT_PER_VISITOR_DAILY_MAX = 10
# 0 by default on purpose: one click on the Triage page makes TWO model calls
# back to back (diagnose, then generate-candidate-patch), so any cooldown
# would refuse the second half of every normal run. The per-visitor and
# global DAILY caps are what bound spend; the cooldown is there for an
# operator who wants it (set TRIAGE_PER_VISITOR_MIN_SECONDS).
DEFAULT_PER_VISITOR_MIN_SECONDS = 0


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default                       # a typo must not remove the cap
    return max(value, 0)


def limits() -> dict:
    return {
        "daily_max": _env_int("TRIAGE_DAILY_MAX_MODEL_CALLS", DEFAULT_DAILY_MAX),
        "per_visitor_daily_max": _env_int("TRIAGE_PER_VISITOR_DAILY_MAX", DEFAULT_PER_VISITOR_DAILY_MAX),
        "per_visitor_min_seconds": _env_int("TRIAGE_PER_VISITOR_MIN_SECONDS", DEFAULT_PER_VISITOR_MIN_SECONDS),
    }


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _now() -> float:
    return budget_store.now()


def _seconds_until_utc_midnight() -> int:
    now = time.time()
    return int(86400 - (now % 86400)) + 1


def check_and_reserve(visitor: str, *, exempt_from_visitor_limits: bool = False) -> dict:
    """Reserve one model call or refuse. Returns
    {"allowed": True} or {"allowed": False, "status", "message", "retry_after"}.
    The check and the reservation are one atomic transaction."""
    try:
        return _check_and_reserve(visitor, exempt_from_visitor_limits)
    except budget_store.StoreUnavailable:
        return {"allowed": False, "status": "STORE_UNAVAILABLE",
                "message": "The Triage Lab's model steps are paused for a moment. Please try again shortly.",
                "retry_after": 30}


def _check_and_reserve(visitor: str, exempt_from_visitor_limits: bool) -> dict:
    lim = limits()
    day, now = _today(), _now()
    with budget_store.transaction() as tx:
        if tx.count(SCOPE, day) >= lim["daily_max"]:
            return {"allowed": False, "status": "DAILY_CAP_REACHED",
                    "message": "The Triage Lab's model steps have reached today's limit. "
                               "The recorded evidence page shows a full run; please try again tomorrow.",
                    "retry_after": _seconds_until_utc_midnight()}
        if exempt_from_visitor_limits:
            tx.insert(SCOPE, day, now)          # counted globally, not per visitor
            return {"allowed": True}
        last = tx.last_ts(SCOPE, visitor)
        if last is not None and now - last < lim["per_visitor_min_seconds"]:
            wait = int(lim["per_visitor_min_seconds"] - (now - last)) + 1
            return {"allowed": False, "status": "COOLDOWN",
                    "message": f"Please wait {wait}s before running another model step.",
                    "retry_after": wait}
        if tx.count(SCOPE, day, visitor) >= lim["per_visitor_daily_max"]:
            return {"allowed": False, "status": "VISITOR_DAILY_CAP_REACHED",
                    "message": "You have reached today's limit for model steps in the Triage Lab.",
                    "retry_after": _seconds_until_utc_midnight()}
        tx.insert(SCOPE, day, now, visitor=visitor)
        return {"allowed": True}


def status() -> dict:
    day = _today()
    try:
        with budget_store.transaction() as tx:
            return {"day_utc": day, "calls_today": tx.count(SCOPE, day), **limits()}
    except budget_store.StoreUnavailable:
        return {"day_utc": day, "calls_today": None, "store_available": False, **limits()}


def _reset_for_tests() -> None:
    budget_store.clear_scope(SCOPE)
