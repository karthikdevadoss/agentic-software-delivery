"""Default-deny for any test suite that would spend real provider money.

WHY A MODULE AND NOT A PROMPT (Sprint 17, 2026-09-30)
-----------------------------------------------------
This project has two real, recorded spend incidents. The one this module is
actually shaped by is 2026-09-18: a real EUR40 pay-as-you-go balance was
exhausted in under seven minutes, and the mechanism was not a single expensive
call -- it was an already-large session context multiplied by a high turn rate
with nothing pausing it. The second, Sprint 15, exhausted credit such that every
grounded question on the live Standing Interview returned HTTP 500.

Both were prevented afterwards by writing rules down. Rules written down are
worth having and they are not a mechanism: the instruction "spend zero on
provider calls" lives in a prompt, and a prompt does not execute. This module
executes. It is the mechanical half.

THE CONTRACT
------------
A paid suite runs only when BOTH of these are true:

  1. ALLOW_PAID_TESTS is set to an affirmative value, AND
  2. PAID_TEST_BUDGET_USD parses as a number strictly greater than zero.

Either alone is not enough, and that is the whole point. A single switch gets
flipped once "just to see" and left on; a budget alone can be set by a config
file nobody reread. Requiring an explicit intent AND an explicit ceiling means
the default state of a fresh shell, a fresh CI runner and a fresh container is
REFUSE -- not because anything was configured, but because nothing was.

The refusal happens BEFORE the provider is reached. `require_paid_tests_allowed`
is called at import/collection time by any paid suite, so it raises while the
API client is still unconstructed. A guard that checks after the call has
already gone out is not a guard, it is a receipt.

FAIL-CLOSED ON MALFORMED INPUT, deliberately. `PAID_TEST_BUDGET_USD=abc` is a
refusal, not a fallback to some default. An unparseable ceiling is an unknown
ceiling, and CLAUDE.md is explicit that unknown must never quietly become a
number.

WHAT THIS DOES NOT DO
---------------------
It does not meter spend and it does not stop a suite mid-run once it has been
allowed. It is an authorization gate, not a budget enforcer -- the budget value
is an explicit declaration of intent that must be present and positive, which is
what makes the second condition meaningful, not a limit this module polices.
Metering real spend against a declared ceiling is real work and is recorded as
backlog rather than implied here (see docs/BACKLOG.json, Agent Eval Architecture
V2).

Sprint 17 itself never set ALLOW_PAID_TESTS. Its recorded paid application-model
call count is 0.
"""

from __future__ import annotations

import os

ALLOW_ENV = "ALLOW_PAID_TESTS"
BUDGET_ENV = "PAID_TEST_BUDGET_USD"

# Matched case-insensitively. "0", "", "false", "no", anything unrecognised and
# any absence all mean NO -- only these exact words mean yes.
_AFFIRMATIVE = {"1", "true", "yes", "on"}


class PaidTestsNotAuthorized(Exception):
    """Raised instead of making a provider call. The message names BOTH
    conditions every time, so a reader who set one and not the other is told
    which half is missing rather than left to guess."""


def _allow_flag_set(env=None) -> bool:
    env = os.environ if env is None else env
    return (env.get(ALLOW_ENV) or "").strip().lower() in _AFFIRMATIVE


def _budget(env=None):
    """Returns the declared budget as a float, or None when it is absent or
    unparseable. None and 0.0 are both refusals but they are different
    diagnoses, so they are not collapsed here."""
    env = os.environ if env is None else env
    raw = (env.get(BUDGET_ENV) or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def paid_tests_status(env=None) -> dict:
    """The full decision, as data. Never raises; use it to REPORT the state
    (a matrix, a selector's JSON, a runner's header) without making the
    decision itself. `require_paid_tests_allowed` is what enforces."""
    env = os.environ if env is None else env
    allowed_flag = _allow_flag_set(env)
    budget = _budget(env)
    budget_ok = budget is not None and budget > 0
    reasons = []
    if not allowed_flag:
        reasons.append(
            f"{ALLOW_ENV} is not set to an affirmative value "
            f"(one of {sorted(_AFFIRMATIVE)}); got {env.get(ALLOW_ENV)!r}"
        )
    if budget is None:
        reasons.append(
            f"{BUDGET_ENV} is absent or does not parse as a number; got "
            f"{env.get(BUDGET_ENV)!r}. An unparseable ceiling is an unknown "
            f"ceiling, and unknown must never become a number by default."
        )
    elif budget <= 0:
        reasons.append(f"{BUDGET_ENV} is {budget}, which is not greater than zero")
    return {
        "authorized": allowed_flag and budget_ok,
        "allow_flag_set": allowed_flag,
        "declared_budget_usd": budget,
        "max_paid_budget": budget if budget_ok else 0.00,
        "refusal_reasons": reasons,
    }


def require_paid_tests_allowed(suite_name: str, env=None) -> float:
    """Call this FIRST, before constructing any provider client.

    Returns the declared budget when authorized. Raises PaidTestsNotAuthorized
    otherwise -- deliberately an exception rather than sys.exit, so a test
    collector reports it as a real error rather than a silent empty run (this
    repo's own false-green defect class: an exit code that means "nothing ran"
    read as "nothing wrong").
    """
    status = paid_tests_status(env)
    if status["authorized"]:
        return float(status["declared_budget_usd"])
    detail = "\n".join(f"  - {r}" for r in status["refusal_reasons"])
    raise PaidTestsNotAuthorized(
        f"REFUSED before any provider call: paid suite {suite_name!r} is not authorized.\n"
        f"{detail}\n"
        f"Both are required, never either alone:\n"
        f"  {ALLOW_ENV}=1 {BUDGET_ENV}=<a real number greater than 0>\n"
        f"No model API call was made."
    )


if __name__ == "__main__":
    import json
    import sys

    status = paid_tests_status()
    print(json.dumps(status, indent=2))
    sys.exit(0 if status["authorized"] else 3)
