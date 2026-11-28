"""Normalized usage event model with field-level measurement provenance.

Design rules (each one is tested):
  * UNKNOWN IS NOT ZERO. A measurement a provider did not report is None
    with source UNAVAILABLE -- never silently 0, so averages and totals
    can say "n of m events reported this" instead of lying.
  * EVERY MEASUREMENT HAS A SOURCE. `provenance` maps each measured field to
    one of Source.*; analytics surface it, the UI shows it.
  * ONE REQUEST, ONE ROW. event_id is derived from (provider, request_id,
    attempt) when a provider request id exists, so recording the same model
    call twice (a retry of the *write*, a re-import) is a no-op downstream
    (the ledger inserts with ON CONFLICT DO NOTHING). A genuine provider
    retry is a different attempt and a different row, flagged is_retry.
  * ONLY LEAVES CARRY TOKENS. request_type "model_call" rows hold tokens and
    cost; "agent_execution" / "workflow" rows are containers that point to
    their children via parent_event_id and carry none, so nested agent runs
    can never be double-counted.
  * NORMALIZED TOKEN MEANING (provider differences are resolved here, once):
      input_tokens        uncached input, billed at the full input rate
      cache_read_tokens   input served from a provider cache
      cache_write_tokens  input written to a provider cache
      output_tokens       all output, INCLUDING reasoning tokens
      reasoning_tokens    the reasoning subset of output (informational)
"""
from __future__ import annotations

import dataclasses
import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum


class Source(str, Enum):
    PROVIDER_REPORTED = "provider_reported"   # the provider's own response/usage object
    APP_MEASURED = "app_measured"             # measured by this application (timers, counters)
    ESTIMATED = "estimated"                   # computed estimate (e.g. chars/3, list price x tokens)
    IMPORTED = "imported"                     # from an exported file / external system
    MANUAL = "manual"                         # typed in by a person
    DEMO = "demo"                             # fictional demonstration data
    UNAVAILABLE = "unavailable"               # not reported by anyone


class BillingCategory(str, Enum):
    METERED_API = "metered_api"                       # pay-per-token API usage
    SUBSCRIPTION = "subscription"                     # flat subscription fee (seat)
    SUBSCRIPTION_ALLOWANCE = "subscription_allowance" # usage counted against a plan allowance
    EQUIVALENT_API_VALUE = "equivalent_api_value"     # what it WOULD cost at API list price
    UNKNOWN = "unknown"


class RequestType(str, Enum):
    MODEL_CALL = "model_call"           # leaf: one provider request; the only type with tokens
    TOOL_CALL = "tool_call"             # leaf: a tool invocation (no tokens)
    AGENT_EXECUTION = "agent_execution" # container
    WORKFLOW = "workflow"               # container


TOKEN_FIELDS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "reasoning_tokens")


@dataclasses.dataclass
class UsageEvent:
    # identity and attribution
    event_id: str
    timestamp: str
    request_type: str = RequestType.MODEL_CALL.value
    request_id: str | None = None
    trace_id: str | None = None
    parent_event_id: str | None = None
    org_id: str | None = None
    team_id: str | None = None
    user_id: str | None = None
    project_id: str | None = None
    feature: str | None = None
    session_id: str | None = None
    conversation_id: str | None = None
    task_id: str | None = None
    workflow_id: str | None = None
    agent_id: str | None = None
    activity_category: str | None = None
    # model
    provider: str | None = None
    requested_model: str | None = None
    response_model: str | None = None
    reasoning_effort: str | None = None
    fallback_from_model: str | None = None
    attempt: int = 1
    is_retry: bool = False
    streamed: bool = False
    complete: bool = True
    # consumption (None = unknown, never coerced to 0)
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    reasoning_tokens: int | None = None
    duration_ms: float | None = None
    ttft_ms: float | None = None
    tool_calls: int | None = None
    agent_steps: int | None = None
    # money
    billing_category: str = BillingCategory.METERED_API.value
    cost_estimated: float | None = None
    cost_reported: float | None = None
    currency: str = "USD"
    pricing_version: str | None = None
    pricing_effective_date: str | None = None
    cost_method: str | None = None
    # outcome of the request itself (task outcomes live in outcomes.py)
    success: bool | None = None
    error_category: str | None = None
    # where the data came from
    dataset: str = "live"                 # "live" | "demo" -- never mixed in one view
    provenance: dict = dataclasses.field(default_factory=dict)

    @property
    def model(self) -> str | None:
        return self.response_model or self.requested_model

    @property
    def total_tokens(self) -> int | None:
        """Sum of the billable token buckets that were reported; None if none were.
        reasoning_tokens is NOT added: it is already inside output_tokens."""
        parts = [getattr(self, f) for f in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")]
        known = [p for p in parts if p is not None]
        return sum(known) if known else None

    @property
    def is_leaf_model_call(self) -> bool:
        return self.request_type == RequestType.MODEL_CALL.value

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["total_tokens"] = self.total_tokens
        d["model"] = self.model
        return d


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def make_event_id(provider: str | None, request_id: str | None, attempt: int = 1) -> str:
    """Deterministic when the provider gave a request id (dedupe-safe), random otherwise."""
    if request_id:
        raw = f"{provider or '?'}|{request_id}|{attempt}"
        return "ue_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return "ue_" + uuid.uuid4().hex[:24]


def _int_or_none(v):
    return None if v is None else int(v)


def _set(ev: UsageEvent, field: str, value, source: Source) -> None:
    setattr(ev, field, value)
    ev.provenance[field] = (source if value is not None else Source.UNAVAILABLE).value


# --- provider normalizers ------------------------------------------------------
# Each takes the provider's own usage object (as a dict) and fills the
# normalized token fields + provenance. Semantics are documented per provider
# in docs/AI_USAGE_INTELLIGENCE.md with the official source.

def from_anthropic(usage: dict, *, response_model: str | None = None, request_id: str | None = None,
                   attempt: int = 1, **attribution) -> UsageEvent:
    """Anthropic Messages API `usage`: input_tokens EXCLUDES cache reads and
    cache writes, which are reported separately; output_tokens includes any
    extended-thinking tokens (no separate reasoning count is reported)."""
    ev = UsageEvent(event_id=make_event_id("anthropic", request_id, attempt), timestamp=attribution.pop("timestamp", None) or now_iso(),
                    provider="anthropic", request_id=request_id, attempt=attempt, is_retry=attempt > 1,
                    response_model=response_model, **attribution)
    src = Source.PROVIDER_REPORTED
    _set(ev, "input_tokens", _int_or_none(usage.get("input_tokens")), src)
    _set(ev, "output_tokens", _int_or_none(usage.get("output_tokens")), src)
    _set(ev, "cache_read_tokens", _int_or_none(usage.get("cache_read_input_tokens")), src)
    _set(ev, "cache_write_tokens", _int_or_none(usage.get("cache_creation_input_tokens")), src)
    _set(ev, "reasoning_tokens", None, src)  # not reported separately by this API
    # 5-minute vs 1-hour cache writes are priced differently; keep the split when reported.
    split = usage.get("cache_creation") or {}
    if split:
        ev.provenance["cache_write_split"] = {"5m": split.get("ephemeral_5m_input_tokens"),
                                              "1h": split.get("ephemeral_1h_input_tokens")}
    return ev


def from_openai(usage: dict, *, response_model: str | None = None, request_id: str | None = None,
                attempt: int = 1, **attribution) -> UsageEvent:
    """OpenAI Responses API (`input_tokens`, `output_tokens`, *_details) or
    Chat Completions (`prompt_tokens`, `completion_tokens`, *_details). The
    reported input INCLUDES cached reads and cache writes, so the uncached
    part is input - cached - cache_write; output INCLUDES reasoning tokens."""
    ev = UsageEvent(event_id=make_event_id("openai", request_id, attempt), timestamp=attribution.pop("timestamp", None) or now_iso(),
                    provider="openai", request_id=request_id, attempt=attempt, is_retry=attempt > 1,
                    response_model=response_model, **attribution)
    src = Source.PROVIDER_REPORTED
    total_in = usage.get("input_tokens", usage.get("prompt_tokens"))
    out = usage.get("output_tokens", usage.get("completion_tokens"))
    in_details = usage.get("input_tokens_details") or usage.get("prompt_tokens_details") or {}
    out_details = usage.get("output_tokens_details") or usage.get("completion_tokens_details") or {}
    cached = in_details.get("cached_tokens")
    written = in_details.get("cache_write_tokens")
    # Reported input INCLUDES cached reads and cache writes (docs/AI_USAGE_SOURCES.md).
    uncached = None if total_in is None else int(total_in) - int(cached or 0) - int(written or 0)
    _set(ev, "input_tokens", uncached, src)
    _set(ev, "cache_read_tokens", _int_or_none(cached), src)
    _set(ev, "cache_write_tokens", _int_or_none(written), src)
    _set(ev, "output_tokens", _int_or_none(out), src)
    _set(ev, "reasoning_tokens", _int_or_none(out_details.get("reasoning_tokens")), src)
    return ev


def mark_incomplete_stream(ev: UsageEvent, *, received_output_chars: int | None = None) -> UsageEvent:
    """A stream that ended before the provider's final usage message: the
    provider never reported output tokens. Keep what is known, estimate output
    from received characters only if given (chars/4, labelled ESTIMATED)."""
    ev.streamed, ev.complete = True, False
    if ev.output_tokens is None:
        if received_output_chars is not None:
            _set(ev, "output_tokens", max(1, round(received_output_chars / 4)), Source.ESTIMATED)
        else:
            _set(ev, "output_tokens", None, Source.UNAVAILABLE)
    return ev


def container(request_type: RequestType, *, event_id: str | None = None, **attribution) -> UsageEvent:
    """An agent execution or workflow: groups child events, carries no tokens."""
    return UsageEvent(event_id=event_id or make_event_id(None, None), timestamp=attribution.pop("timestamp", None) or now_iso(),
                      request_type=request_type.value, **attribution)
