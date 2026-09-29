"""Spend protection for the public Standing Interview endpoint.

WHY THIS EXISTS
`/api/standing-interview/ask` is a public POST with no auth, and every request
triggers a real, billed model call. The Workbench already has a cooldown and a
daily cap; this endpoint had neither. At the measured $0.023 an answer, a
script looping on that URL would spend $20 in about ninety seconds, and the
first the Owner would know is an empty balance -- which is exactly how the
2026-09-29 outage was discovered.

WHAT IT DOES
Two independent limits, because they stop different things:

  * A DAILY BUDGET, expressed in dollars and converted to a request count
    using the real measured cost per answer. This is the backstop: whatever
    else happens, one day cannot cost more than SI_DAILY_USD_BUDGET.
  * A PER-VISITOR limit -- a minimum gap between questions, and a daily
    ceiling. This stops one client consuming the whole day's budget, so a
    single bot cannot lock out every genuine recruiter.

Both are checked BEFORE the model call, never after.

HONEST LIMITATIONS, stated rather than discovered later
  1. State is in-process memory. A container restart resets both counters, so
     the daily budget is "per container-day", not a hard ledger-backed cap.
     That is the same tradeoff the existing trainer cooldown makes. It is a
     large improvement on nothing and it is NOT a guarantee -- a crash-looping
     container could exceed the budget. The durable version would count
     against the event ledger; that is a bigger change and is not this.
  2. The visitor key is the client IP as the platform reports it. Behind a
     proxy that rewrites it, or for a determined attacker rotating addresses,
     the per-visitor limit degrades. The DAILY BUDGET is the limit that still
     holds in that case, which is why it exists separately.
  3. SI_USD_PER_ANSWER is a real measured average ($1.4353 across 63 real
     production requests, 2026-09-29), not a quote. A long answer costs more
     than a short one, so the dollar figure is an ESTIMATE and the request
     count is the thing actually enforced.
"""

from __future__ import annotations

import hmac
import os
import threading
import time

# --- the knobs, in one place so they can be changed without reading code ----

# The most this endpoint may cost in one day. Deliberately small: this is a
# portfolio surface for recruiters, not a product under load.
SI_DAILY_USD_BUDGET = 1.00

# Real measured average: $1.4353 / 63 production requests, 2026-09-29.
SI_USD_PER_ANSWER = 0.023

# Derived, so changing the budget is the only edit needed.
SI_DAILY_MAX_ANSWERS = int(SI_DAILY_USD_BUDGET / SI_USD_PER_ANSWER)

# One visitor's minimum gap between questions. A person reads an answer before
# asking again; a loop does not.
SI_PER_VISITOR_MIN_SECONDS = 5

# One visitor's ceiling for a day. Well above a real interview conversation,
# well below the daily budget, so one client cannot consume everyone's.
SI_PER_VISITOR_DAILY_MAX = 25

# OPERATOR EXEMPTION.
#
# Found the hard way, 2026-09-30: a deploy runs the acceptance gate twice (15
# questions before upload, 15 against the deployed host) = 30 requests. The
# per-visitor ceiling is 25 and the whole daily budget is 43. So the cap I
# wrote made this project's own deploy verification IMPOSSIBLE TO RUN -- not
# just once, but on every future deploy. A control that blocks the thing that
# proves the product works is not a good control.
#
# The gate is operator traffic, not a visitor, so it identifies itself.
#
# FAILS CLOSED, deliberately: when SI_OPERATOR_TOKEN is unset or empty there is
# no exemption and no way to obtain one, so a misconfigured deploy loses its
# exemption rather than the public endpoint silently losing its cap. The token
# is compared with compare_digest and is never logged, echoed or included in
# any response.
_OPERATOR_HEADER = "x-si-operator"


def is_operator(headers) -> bool:
    """True only for a request carrying the configured operator token."""
    expected = os.environ.get("SI_OPERATOR_TOKEN") or ""
    if not expected:
        return False                      # fail closed
    try:
        supplied = headers.get(_OPERATOR_HEADER, "") or ""
    except Exception:
        return False
    return bool(supplied) and hmac.compare_digest(supplied, expected)


# --- state ------------------------------------------------------------------
_lock = threading.Lock()
_day: str | None = None
_answers_today = 0
_visitor_count: dict[str, int] = {}
_visitor_last_at: dict[str, float] = {}


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _roll_day_locked() -> None:
    global _day, _answers_today
    now = _today()
    if _day != now:
        _day = now
        _answers_today = 0
        _visitor_count.clear()
        _visitor_last_at.clear()


def check(visitor: str) -> dict:
    """May this visitor be answered right now?

    Returns {"allowed": True} or {"allowed": False, "status": ..., "message":
    ..., "retry_after": seconds}. The message is written for a visitor to
    read; it never mentions dollars, budgets or the Owner's account.
    """
    visitor = visitor or "unknown"
    with _lock:
        _roll_day_locked()

        if _answers_today >= SI_DAILY_MAX_ANSWERS:
            return {
                "allowed": False,
                "status": "DAILY_CAP",
                "retry_after": _seconds_until_utc_midnight(),
                "message": (
                    "This interview has answered as many questions as it takes "
                    "in a day. It resets at midnight UTC — please come back "
                    "then, or reach me directly in the meantime."),
            }

        last = _visitor_last_at.get(visitor)
        if last is not None:
            gap = time.monotonic() - last
            if gap < SI_PER_VISITOR_MIN_SECONDS:
                return {
                    "allowed": False,
                    "status": "COOLDOWN",
                    "retry_after": int(SI_PER_VISITOR_MIN_SECONDS - gap) + 1,
                    "message": (
                        "One question at a time — give me a moment to answer "
                        "the last one."),
                }

        if _visitor_count.get(visitor, 0) >= SI_PER_VISITOR_DAILY_MAX:
            return {
                "allowed": False,
                "status": "VISITOR_CAP",
                "retry_after": _seconds_until_utc_midnight(),
                "message": (
                    "That's a lot of questions for one day — more than a real "
                    "interview would cover. Please pick this up tomorrow, or "
                    "reach me directly."),
            }

        return {"allowed": True}


def record_answer(visitor: str) -> None:
    """Count a request that actually reached the model.

    Called only on the billed path. A refusal that never reaches the model
    costs nothing and must not consume anyone's allowance -- otherwise asking
    two private questions would lock a real recruiter out.
    """
    visitor = visitor or "unknown"
    with _lock:
        _roll_day_locked()
        global _answers_today
        _answers_today += 1
        _visitor_count[visitor] = _visitor_count.get(visitor, 0) + 1
        _visitor_last_at[visitor] = time.monotonic()


def _seconds_until_utc_midnight() -> int:
    now = time.gmtime()
    return max(1, 86400 - (now.tm_hour * 3600 + now.tm_min * 60 + now.tm_sec))


def status() -> dict:
    """For the Owner, not for visitors. Real counts, and the dollar figure
    labelled as the estimate it is."""
    with _lock:
        _roll_day_locked()
        return {
            "day_utc": _day,
            "answers_today": _answers_today,
            "daily_max_answers": SI_DAILY_MAX_ANSWERS,
            "daily_usd_budget": SI_DAILY_USD_BUDGET,
            "estimated_spend_today_usd": round(_answers_today * SI_USD_PER_ANSWER, 4),
            "estimate_basis": "measured average $1.4353/63 real requests 2026-09-29",
            "distinct_visitors_today": len(_visitor_count),
        }


def _reset_for_tests() -> None:
    global _day, _answers_today
    with _lock:
        _day = None
        _answers_today = 0
        _visitor_count.clear()
        _visitor_last_at.clear()
