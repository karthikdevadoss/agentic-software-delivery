"""Owner-only access for the control-plane endpoints (Automation Sprint 4).

POST /api/runs, /api/runs/mock, /api/runs/{id}/decide and
/api/dev-sessions/start|stop used to accept anyone. They start real agent
runs (model spend, file edits), approve edits, or write records, so they
now need the owner token.

- The token lives only in the OWNER_API_TOKEN environment variable.
- A request proves it with `Authorization: Bearer <token>` or
  `X-Owner-Token: <token>`, compared in constant time.
- FAIL CLOSED: if OWNER_API_TOKEN is unset or empty, nobody is the owner and
  every guarded endpoint answers 401. Forgetting to configure the deploy
  locks the control plane; it never opens it.

The same shape as si_budget.is_operator (the existing operator token for the
Standing Interview gate), kept separate so the two secrets can rotate
independently and Standing Interview code is not touched.
"""
import functools
import hmac
import os

from starlette.responses import JSONResponse

ENV_VAR = "OWNER_API_TOKEN"
HEADER = "x-owner-token"


def _supplied_token(headers) -> str:
    try:
        auth = headers.get("authorization", "") or ""
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return (headers.get(HEADER, "") or "").strip()
    except Exception:  # noqa: BLE001 - a malformed header is simply not the owner
        return ""


def is_configured() -> bool:
    return bool(os.environ.get(ENV_VAR, "").strip())


def is_owner(headers) -> bool:
    expected = os.environ.get(ENV_VAR, "").strip()
    if not expected:
        return False                                   # fail closed
    supplied = _supplied_token(headers)
    return bool(supplied) and hmac.compare_digest(supplied.encode(), expected.encode())


def unauthorized_response() -> JSONResponse:
    return JSONResponse(
        {"error": "owner authorization required",
         "detail": "This endpoint is restricted to the platform owner."},
        status_code=401,
        headers={"WWW-Authenticate": 'Bearer realm="owner"'},
    )


def require_owner(handler):
    """Decorator for a Starlette endpoint: 401 unless the request carries the
    owner token. Checked before the body is read, so an anonymous caller
    cannot make the handler do any work at all."""
    @functools.wraps(handler)
    async def guarded(request):
        if not is_owner(request.headers):
            return unauthorized_response()
        return await handler(request)
    guarded.owner_only = True
    return guarded
