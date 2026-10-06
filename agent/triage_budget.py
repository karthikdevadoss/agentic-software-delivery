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

Honest limits: counters are in process memory, so a restart or a second
replica starts from zero. The daily cap bounds spend per process per day; it
is not an accounting system.
"""
import os
import threading
import time

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


_lock = threading.Lock()
_day = None
_total = 0
_per_visitor: dict = {}
_last_at: dict = {}


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _seconds_until_utc_midnight() -> int:
    now = time.time()
    return int(86400 - (now % 86400)) + 1


def _roll_day_locked() -> None:
    global _day, _total
    today = _today()
    if _day != today:
        _day, _total = today, 0
        _per_visitor.clear()
        _last_at.clear()


def check_and_reserve(visitor: str, *, exempt_from_visitor_limits: bool = False) -> dict:
    """Reserve one model call or refuse. Returns
    {"allowed": True} or {"allowed": False, "status", "message", "retry_after"}."""
    global _total
    lim = limits()
    with _lock:
        _roll_day_locked()
        if _total >= lim["daily_max"]:
            return {"allowed": False, "status": "DAILY_CAP_REACHED",
                    "message": "The Triage Lab's model steps have reached today's limit. "
                               "The recorded evidence page shows a full run; please try again tomorrow.",
                    "retry_after": _seconds_until_utc_midnight()}
        if not exempt_from_visitor_limits:
            now = time.monotonic()
            last = _last_at.get(visitor)
            if last is not None and now - last < lim["per_visitor_min_seconds"]:
                wait = int(lim["per_visitor_min_seconds"] - (now - last)) + 1
                return {"allowed": False, "status": "COOLDOWN",
                        "message": f"Please wait {wait}s before running another model step.",
                        "retry_after": wait}
            if _per_visitor.get(visitor, 0) >= lim["per_visitor_daily_max"]:
                return {"allowed": False, "status": "VISITOR_DAILY_CAP_REACHED",
                        "message": "You have reached today's limit for model steps in the Triage Lab.",
                        "retry_after": _seconds_until_utc_midnight()}
            _last_at[visitor] = now
            _per_visitor[visitor] = _per_visitor.get(visitor, 0) + 1
        _total += 1
        return {"allowed": True}


def status() -> dict:
    with _lock:
        _roll_day_locked()
        return {"day_utc": _day, "calls_today": _total, **limits()}


def _reset_for_tests() -> None:
    global _day, _total
    with _lock:
        _day, _total = None, 0
        _per_visitor.clear()
        _last_at.clear()
