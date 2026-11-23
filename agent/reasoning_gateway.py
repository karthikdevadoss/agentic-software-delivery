"""
Central Reasoning Gateway (Base Architecture V3, Phase 3).

Phase 1's Intelligence Placement Audit (docs/INTELLIGENCE_PLACEMENT_V3.md)
found 4 direct Anthropic API call sites in this codebase (agent/main.py,
agent/agent_loop.py, agent/backend_planning.py, agent/triage_execution.py),
each already independently disciplined (injectable create_fn for tests,
honest "no API key" handling, real usage recorded via metrics.py) but with
no single structural boundary enforcing the directive's Phase 3 policy:
every model call must be purpose-gated, advisory-only, and independently
verified by the caller -- never trusted as authority.

Scope (updated by the gateway-all-calls change): EVERY billed model call
in agent/ now goes through this module, through one of two entry points:
  - call(): single-shot advisory text (triage_execution, jd_match,
    standing_interview, main.py, ...).
  - converse(): a caller-owned multi-turn / tool-calling / structured-output
    conversation. The gateway performs ONE request per converse() call and
    returns the raw, unmodified response (thinking + tool_use blocks intact);
    the caller keeps its own loop and message history. Used by
    agent_loop.run_agent_loop (tool loop) and
    backend_planning.analyze_with_llm (structured JSON contract).
Both run the same purpose check, LLM_MODE kill switch, API-key check and
usage/cost recording. agent/test_reasoning_gateway_enforcement.py fails the
build if any other agent/ or scripts/ file imports a provider SDK, constructs
a client, or calls .messages.create. Honest limits: only Anthropic is
supported (no second provider, no LiteLLM); budgets are not durable; the scan
covers agent/ and scripts/ Python files, not code outside the repo or
non-Python services.

Non-negotiable rules enforced here (Phase 3 of the directive):
  - DEFAULT DENIED: `purpose` must be one of ADVISORY_PURPOSES or the call
    is rejected before any network request, not after.
  - AUTHORITY IS ALWAYS ADVISORY: the returned dict never grants
    authorization, never gates a workflow transition -- callers must
    independently verify anything returned here (exactly as
    agent/triage_execution.py's diagnose()/generate_candidate_patch()
    already did before this gateway existed: diagnosis is display-only,
    candidates are compile+test verified before promotion eligibility).
  - LLM_MODE=DISABLED IS HONORED: Phase 17's zero-LLM-mode kill switch --
    when set, this function makes zero network calls and returns a
    structured, honest denial, not a crash or a silent fallback.
"""

import json
import os
import time

import gateway_budget
import litellm_route
import pricing_config
import tracing

# The 6 categories the directive names as POSSIBLE candidates for real
# semantic/generative value -- listed, not automatically allowed; every
# call must still name one explicitly. Adding a 7th category here is a
# deliberate architectural decision, not something a caller can bypass by
# passing an arbitrary string.
ADVISORY_PURPOSES = frozenset({
    "SEMANTIC_REQUIREMENT_INTERPRETATION",
    "GENUINE_AMBIGUITY_ANALYSIS",
    "NOVEL_ROOT_CAUSE_HYPOTHESES",
    "NOVEL_IMPLEMENTATION_PROPOSAL",
    "SEMANTIC_ADVERSARIAL_TEST_IDEAS",
    "HUMAN_EXPLANATION",
    # Sprint 13 / BL-097 (Owner-authorised 7th purpose): JD Match's two
    # advisory calls -- extract requirements from an untrusted job
    # description, and propose a status per requirement from a code-built
    # shortlist. Every proposal is validated by code before it is shown.
    "JD_REQUIREMENT_MATCHING",
})


def llm_mode_disabled() -> bool:
    """The Phase 17 zero-LLM-mode switch. Checked live (an env var, not a
    cached module-load-time value) so a test or operator can flip it
    without restarting the process."""
    return os.environ.get("LLM_MODE", "").strip().upper() == "DISABLED"


def _denied(reason: str, **extra) -> dict:
    return {"text": None, "authority": "ADVISORY", "model_called": False,
            "denial_reason": reason, "usage": None, **extra}


def _pre_flight(purpose, api_key, create_fn):
    """Purpose check -> kill switch -> API key -> client. Returns
    (denial_reason | None, create_fn, real_client_call, resolved_key)."""
    if purpose not in ADVISORY_PURPOSES:
        return (f"purpose {purpose!r} is not in ADVISORY_PURPOSES -- "
                f"default-denied per this gateway's Phase 3 model-access policy"), None, False
    if llm_mode_disabled():
        return "LLM_MODE=DISABLED -- zero-LLM mode active, no network call made", None, False
    real_client_call = create_fn is None
    if create_fn is None:
        if litellm_route.enabled():
            # Proxy mode (PR 53): the key held here is the proxy's virtual/
            # master key; the Anthropic key lives in the proxy. There is
            # deliberately NO fallback to a direct call if this fails.
            try:
                from anthropic import Anthropic
                create_fn = Anthropic(**litellm_route.client_settings(api_key)).messages.create
            except litellm_route.LiteLLMConfigError as exc:
                return f"LiteLLM proxy mode misconfigured: {exc}", None, False
        else:
            api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                return "ANTHROPIC_API_KEY not set -- cannot run a live model call", None, False
            from anthropic import Anthropic
            create_fn = Anthropic(api_key=api_key).messages.create
    return None, create_fn, real_client_call


def _reserve_budget(enforce_budget, real_client_call, model, system_prompt, user_text,
                    max_tokens, run_id):
    """Durable budget/rate gate, run BEFORE the provider is contacted.
    Returns (denial_reason | None, reservation_id | None). Shared by call()
    and converse() so both are refused before they are billed."""
    if not (enforce_budget is True or (enforce_budget is None and real_client_call)):
        return None, None
    verdict = gateway_budget.reserve(
        "anthropic", model, system_prompt, user_text, max_tokens, run_id=run_id)
    if not verdict["allowed"]:
        return f"BUDGET_{verdict['status']}: {verdict['message']}", None
    return None, verdict["reservation_id"]


def _summarize_and_record(response, model, duration_ms, real_client_call, reservation=None):
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    cache_write = getattr(usage, "cache_creation_input_tokens", None)
    cache_read = getattr(usage, "cache_read_input_tokens", None)
    cost = pricing_config.calculate_cost(
        "anthropic", model,
        input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
        cache_write_tokens=cache_write or 0, cache_read_tokens=cache_read or 0,
    )
    if reservation is not None and cost.get("available"):
        gateway_budget.settle(reservation, cost["total_usd"])
    if real_client_call:
        import metrics
        metrics.record_model_usage(
            provider="anthropic", model=model,
            input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
            cache_creation_input_tokens=cache_write, cache_read_input_tokens=cache_read,
        )
    return {
        "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
        "cache_creation_input_tokens": cache_write, "cache_read_input_tokens": cache_read,
        "duration_ms": duration_ms, **cost,
    }


def _messages_text(messages) -> str:
    """Characters of a conversation, for the worst-case input estimate only
    (over-counting is the safe direction for a budget reservation)."""
    try:
        return json.dumps(messages, default=lambda o: getattr(o, "__dict__", str(o)))
    except (TypeError, ValueError):
        return str(messages)


def _tools_text(tools) -> str:
    return _messages_text(tools) if tools else ""


def _converse_impl(
    purpose: str,
    system_prompt: str,
    messages: list,
    max_tokens: int,
    tools=None,
    api_key: str | None = None,
    create_fn=None,
    model: str = "claude-sonnet-5",
    run_id: str | None = None,
    enforce_budget: bool | None = None,
) -> dict:
    """Gateway entry point for caller-owned multi-turn / tool-calling /
    structured-output conversations. Makes exactly ONE request per call and
    returns the RAW response unmodified (so thinking and tool_use blocks can
    be replayed to the API by the caller); no fence-stripping, no text
    extraction. Same purpose check, kill switch, key check and usage/cost
    recording as call().

    Returns {response, authority="ADVISORY", model_called, denial_reason,
    usage}; response is None on every denial path (zero network calls)."""
    denial, create_fn, real_client_call = _pre_flight(purpose, api_key, create_fn)
    if denial:
        return _denied(denial, response=None)
    # Same durable budget/rate gate as call(): refused BEFORE it is billed.
    # The estimate is built from the whole conversation (system + messages).
    denial, reservation = _reserve_budget(
        enforce_budget, real_client_call, model, system_prompt,
        _messages_text(messages) + _tools_text(tools), max_tokens, run_id)
    if denial:
        return _denied(denial, response=None)
    kwargs = {"model": model, "max_tokens": max_tokens, "system": system_prompt,
              "messages": messages}
    if tools is not None:
        kwargs["tools"] = tools
    call_start = time.monotonic()
    response = create_fn(**kwargs)
    duration_ms = round((time.monotonic() - call_start) * 1000, 1)
    return {
        "response": response, "authority": "ADVISORY", "model_called": True,
        "denial_reason": None, "text": None,
        "usage": _summarize_and_record(response, model, duration_ms, real_client_call, reservation),
    }


def _call_impl(
    purpose: str,
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    api_key: str | None = None,
    create_fn=None,
    effort: str | None = None,
    model: str = "claude-sonnet-5",
    run_id: str | None = None,
    enforce_budget: bool | None = None,
) -> dict:
    """The one sanctioned boundary for a single-shot advisory model call.

    Returns a dict with exactly these keys, always:
      text: str | None -- the model's stripped text response, or None if
        the call was denied/unavailable/produced no real content.
      authority: always the literal string "ADVISORY" -- present on every
        result (including denials) so a caller can never mistake this for
        an authoritative decision by omission.
      model_called: bool -- True only if a real network request was made
        (False for purpose-denial, LLM_MODE=DISABLED, and missing API key
        -- these are distinct honest reasons, not folded into one boolean
        without explanation; see denial_reason).
      denial_reason: str | None -- populated whenever model_called is
        False, or when a real call returned no usable text (e.g. extended
        thinking consumed the whole max_tokens budget -- a known real
        failure mode, see agent/triage_execution.py's own prior fix for
        this exact case).
      usage: dict | None -- real token/cost/time for this call (input_tokens,
        output_tokens, cache_*_tokens, duration_ms, plus calculate_cost()'s
        own available/total_usd/pricing_version fields), or None whenever no
        real API response was obtained (every denial path). Added 2026-09-20
        (BL-009) so callers can surface real cost/time to their own UI
        instead of the usage dict being computed here and then discarded --
        real finding: agent/triage_execution.py's Incident Triage Lab made
        real, billed calls but showed zero tokens/cost/time anywhere.

    create_fn (optional): injectable, mirrors every existing call site's
    own testing pattern -- create_fn(model=..., max_tokens=..., system=...,
    messages=...) -> an object with .content (blocks with .type/.text) and
    .usage. Never omitted in a real automated test, so tests never make a
    real, billed Anthropic API call."""
    denial, create_fn, real_client_call = _pre_flight(purpose, api_key, create_fn)
    if denial:
        return _denied(denial)
    denial, reservation = _reserve_budget(
        enforce_budget, real_client_call, model, system_prompt, user_message, max_tokens, run_id)
    if denial:
        return _denied(denial)

    kwargs = {}
    if effort is not None:
        kwargs["output_config"] = {"effort": effort}
    call_start = time.monotonic()
    response = create_fn(
        model=model, max_tokens=max_tokens, system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
        **kwargs,
    )
    duration_ms = round((time.monotonic() - call_start) * 1000, 1)
    # AEQ-028: usage is only recorded to metrics for a real client call, never
    # for an injected test double (see _pre_flight / _summarize_and_record).
    usage_summary = _summarize_and_record(response, model, duration_ms, real_client_call, reservation)

    text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text")
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped
        if stripped.endswith("```"):
            stripped = stripped[:-3]
    stripped = stripped.strip()

    if not stripped:
        stop_reason = getattr(response, "stop_reason", None)
        return {
            "text": None, "authority": "ADVISORY", "model_called": True,
            "denial_reason": (
                f"model produced no real text content (stop_reason={stop_reason!r}) -- "
                f"likely extended thinking consumed the entire max_tokens budget before "
                f"any answer text; retry with a larger max_tokens"
            ),
            "usage": usage_summary,
        }

    return {
        "text": stripped, "authority": "ADVISORY", "model_called": True, "denial_reason": None,
        "usage": usage_summary,
    }


def call(purpose, system_prompt, user_message, max_tokens, api_key=None,
         create_fn=None, effort=None, model="claude-sonnet-5") -> dict:
    """Traced wrapper: every call through the gateway -- including denials --
    is one `gateway.model_call` span. Contract/doc: see _call_impl."""
    with tracing.span(
        "gateway.model_call", purpose=str(purpose), model=model,
        max_tokens=max_tokens, effort=effort,
    ) as sp:
        try:
            result = _call_impl(purpose, system_prompt, user_message, max_tokens,
                                api_key=api_key, create_fn=create_fn, effort=effort, model=model)
        except Exception as exc:  # noqa: BLE001 - recorded then re-raised unchanged
            sp.set_attribute("gateway.outcome", "error")
            sp.set_attribute("error.type", type(exc).__name__)
            sp.record_exception(exc)
            raise
        usage = result.get("usage")
        if not result.get("model_called"):
            sp.set_attribute("gateway.outcome", "denied")
            sp.set_attribute("gateway.denial_reason", str(result.get("denial_reason"))[:200])
        else:
            sp.set_attribute("gateway.outcome", "ok" if result.get("text") else "error")
            if not result.get("text"):
                sp.set_attribute("gateway.denial_reason", str(result.get("denial_reason"))[:200])
        if usage:
            sp.set_attribute("llm.input_tokens", usage["input_tokens"])
            sp.set_attribute("llm.output_tokens", usage["output_tokens"])
            sp.set_attribute("llm.duration_ms", usage["duration_ms"])
            if usage.get("available") and usage.get("total_usd") is not None:
                sp.set_attribute("llm.cost_usd", float(usage["total_usd"]))
        return result


def _annotate_span(sp, result, *, converse_mode=False):
    """Attach outcome/model/token/cost attributes to a gateway span. Shared
    by call() and converse() so every billed path emits the same span family
    (`gateway.model_call`); budget refusals are outcome=denied with the
    BUDGET_* reason, so a refusal is visible in the trace, not just absent."""
    usage = result.get("usage")
    if not result.get("model_called"):
        sp.set_attribute("gateway.outcome", "denied")
        sp.set_attribute("gateway.denial_reason", str(result.get("denial_reason"))[:200])
    else:
        ok = (result.get("response") is not None) if converse_mode else bool(result.get("text"))
        sp.set_attribute("gateway.outcome", "ok" if ok else "error")
        if not ok:
            sp.set_attribute("gateway.denial_reason", str(result.get("denial_reason"))[:200])
    if usage:
        sp.set_attribute("llm.input_tokens", usage["input_tokens"])
        sp.set_attribute("llm.output_tokens", usage["output_tokens"])
        sp.set_attribute("llm.duration_ms", usage["duration_ms"])
        if usage.get("available") and usage.get("total_usd") is not None:
            sp.set_attribute("llm.cost_usd", float(usage["total_usd"]))


def _traced(entry, fn, *, purpose, model, max_tokens, effort=None, run_id=None):
    with tracing.span(
        "gateway.model_call", purpose=str(purpose), model=model,
        max_tokens=max_tokens, effort=effort, entry=entry,
    ) as sp:
        try:
            result = fn()
        except Exception as exc:  # noqa: BLE001 - recorded then re-raised unchanged
            sp.set_attribute("gateway.outcome", "error")
            sp.set_attribute("error.type", type(exc).__name__)
            sp.record_exception(exc)
            raise
        _annotate_span(sp, result, converse_mode=(entry == "converse"))
        return result


def call(purpose, system_prompt, user_message, max_tokens, api_key=None,
         create_fn=None, effort=None, model="claude-sonnet-5", run_id=None,
         enforce_budget=None) -> dict:
    """Traced wrapper: every call through the gateway -- including denials --
    is one `gateway.model_call` span. Contract/doc: see _call_impl."""
    return _traced(
        "call",
        lambda: _call_impl(purpose, system_prompt, user_message, max_tokens,
                           api_key=api_key, create_fn=create_fn, effort=effort,
                           model=model, run_id=run_id, enforce_budget=enforce_budget),
        purpose=purpose, model=model, max_tokens=max_tokens, effort=effort)


def converse(purpose, system_prompt, messages, max_tokens, tools=None, api_key=None,
             create_fn=None, model="claude-sonnet-5", run_id=None,
             enforce_budget=None) -> dict:
    """Traced wrapper for the multi-turn / tool-calling entry point: same
    `gateway.model_call` span (entry="converse") with model, tokens, cost and
    outcome as call(). Contract/doc: see _converse_impl."""
    return _traced(
        "converse",
        lambda: _converse_impl(purpose, system_prompt, messages, max_tokens, tools=tools,
                               api_key=api_key, create_fn=create_fn, model=model,
                               run_id=run_id, enforce_budget=enforce_budget),
        purpose=purpose, model=model, max_tokens=max_tokens)
