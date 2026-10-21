"""Spend and abuse limits for the public one-click Workbench (2026-10-21).

WHY THIS EXISTS
Owner rule, 21 Oct 2026 18:19: a visitor's click on the public Workbench runs
the change at once. There is no approval queue for visitors. The click itself
is the human decision. Because anyone on the internet can click, the click
path needs its own limits, checked BEFORE any work is done.

WHAT A CLICK COSTS TODAY
A visitor click runs a deterministic catalogue edit on a sandbox copy of the
Customer App page (see web_server._run_visitor_sandbox). It makes no model
call, so the real model cost is $0.00 per click. The dollar budget below is
still enforced, so if a future change adds a paid step, one day still cannot
cost more than WORKBENCH_DAILY_USD_BUDGET.

LIMITS (same shape as si_budget.py, the Standing Interview $1/day cap)
  * DAILY USD BUDGET: total recorded spend per UTC day.
  * DAILY CLICK CAP: total clicks per UTC day, whatever they cost (CPU guard).
  * PER-VISITOR (per IP): a minimum gap between clicks and a daily ceiling.

HONEST LIMITS
  1. State is in-process memory, so a container restart resets the counters
     (same tradeoff as si_budget and the triage caps).
  2. The visitor key is the client IP as the platform sees it. A client that
     rotates addresses gets around the per-visitor limit; the daily caps
     still hold in that case.
"""

from __future__ import annotations

import threading
import time

# --- the knobs ---------------------------------------------------------------
WORKBENCH_DAILY_USD_BUDGET = 1.00      # like the Standing Interview cap
WORKBENCH_USD_PER_CLICK = 0.00         # measured: a click makes no model call
WORKBENCH_DAILY_MAX_CLICKS = 500       # all visitors together, per UTC day
WORKBENCH_PER_VISITOR_MIN_SECONDS = 3  # gap between two clicks from one IP
WORKBENCH_PER_VISITOR_DAILY_MAX = 30   # clicks per IP per UTC day

# --- state -------------------------------------------------------------------
_lock = threading.Lock()
_day: str | None = None
_clicks_today = 0
_spend_today_usd = 0.0
_visitor_count: dict[str, int] = {}
_visitor_last_at: dict[str, float] = {}


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _roll_day_locked() -> None:
    global _day, _clicks_today, _spend_today_usd
    now = _today()
    if _day != now:
        _day = now
        _clicks_today = 0
        _spend_today_usd = 0.0
        _visitor_count.clear()
        _visitor_last_at.clear()


def _seconds_until_utc_midnight() -> int:
    now = time.gmtime()
    return max(1, 86400 - (now.tm_hour * 3600 + now.tm_min * 60 + now.tm_sec))


def check(visitor: str) -> dict:
    """May this visitor run one click now? Never mentions dollars to visitors."""
    visitor = visitor or "unknown"
    with _lock:
        _roll_day_locked()
        if (_spend_today_usd + WORKBENCH_USD_PER_CLICK > WORKBENCH_DAILY_USD_BUDGET
                or _clicks_today >= WORKBENCH_DAILY_MAX_CLICKS):
            return {"allowed": False, "status": "DAILY_CAP",
                    "retry_after": _seconds_until_utc_midnight(),
                    "message": "The demo has done as many runs as it does in one day. "
                               "It opens again at midnight UTC."}
        last = _visitor_last_at.get(visitor)
        if last is not None:
            gap = time.monotonic() - last
            if gap < WORKBENCH_PER_VISITOR_MIN_SECONDS:
                return {"allowed": False, "status": "COOLDOWN",
                        "retry_after": int(WORKBENCH_PER_VISITOR_MIN_SECONDS - gap) + 1,
                        "message": "One moment, please. Your last run just finished."}
        if _visitor_count.get(visitor, 0) >= WORKBENCH_PER_VISITOR_DAILY_MAX:
            return {"allowed": False, "status": "VISITOR_CAP",
                    "retry_after": _seconds_until_utc_midnight(),
                    "message": "You have used all of today's demo runs. Please come back tomorrow."}
        return {"allowed": True}


def record_click(visitor: str, cost_usd: float = WORKBENCH_USD_PER_CLICK) -> None:
    """Count one click that actually ran, with its real cost."""
    global _clicks_today, _spend_today_usd
    visitor = visitor or "unknown"
    with _lock:
        _roll_day_locked()
        _clicks_today += 1
        _spend_today_usd += max(0.0, float(cost_usd or 0.0))
        _visitor_count[visitor] = _visitor_count.get(visitor, 0) + 1
        _visitor_last_at[visitor] = time.monotonic()


def limits() -> dict:
    """Public, plain description of the limits (no counts, no visitor data)."""
    return {
        "daily_usd_budget": WORKBENCH_DAILY_USD_BUDGET,
        "usd_per_click": WORKBENCH_USD_PER_CLICK,
        "model_calls_per_click": 0,
        "daily_max_clicks": WORKBENCH_DAILY_MAX_CLICKS,
        "per_visitor_min_seconds": WORKBENCH_PER_VISITOR_MIN_SECONDS,
        "per_visitor_daily_max": WORKBENCH_PER_VISITOR_DAILY_MAX,
    }


def status() -> dict:
    with _lock:
        _roll_day_locked()
        return {"day_utc": _day, "clicks_today": _clicks_today,
                "spend_today_usd": round(_spend_today_usd, 4),
                "distinct_visitors_today": len(_visitor_count), **limits()}


def _reset_for_tests() -> None:
    global _day, _clicks_today, _spend_today_usd
    with _lock:
        _day = None
        _clicks_today = 0
        _spend_today_usd = 0.0
        _visitor_count.clear()
        _visitor_last_at.clear()
