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

Scope decision (documented, not an oversight): only agent/triage_execution.py's
single-shot advisory calls (diagnose/generate_candidate_patch) are wired
through this gateway so far -- see call site there. agent/backend_planning.py's
analyze_with_llm has a materially different response contract (structured
JSON fields, not a stripped text blob) and agent/main.py (V1 CLI)/
agent/agent_loop.py (V3's multi-turn TOOL-CALLING loop, not a single-shot
request) are a genuinely different category -- a multi-turn agentic loop
cannot be flattened into this gateway's single-call shape without a much
larger, riskier redesign than this phase's bounded scope justifies. Wiring
those in is real future work, tracked in docs/ACTION_QUEUE.json, not
silently dropped.

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

import os

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
})


def llm_mode_disabled() -> bool:
    """The Phase 17 zero-LLM-mode switch. Checked live (an env var, not a
    cached module-load-time value) so a test or operator can flip it
    without restarting the process."""
    return os.environ.get("LLM_MODE", "").strip().upper() == "DISABLED"


def call(
    purpose: str,
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    api_key: str | None = None,
    create_fn=None,
    effort: str | None = None,
    model: str = "claude-sonnet-5",
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

    create_fn (optional): injectable, mirrors every existing call site's
    own testing pattern -- create_fn(model=..., max_tokens=..., system=...,
    messages=...) -> an object with .content (blocks with .type/.text) and
    .usage. Never omitted in a real automated test, so tests never make a
    real, billed Anthropic API call."""
    if purpose not in ADVISORY_PURPOSES:
        return {
            "text": None, "authority": "ADVISORY", "model_called": False,
            "denial_reason": (
                f"purpose {purpose!r} is not in ADVISORY_PURPOSES -- "
                f"default-denied per this gateway's Phase 3 model-access policy"
            ),
        }
    if llm_mode_disabled():
        return {
            "text": None, "authority": "ADVISORY", "model_called": False,
            "denial_reason": "LLM_MODE=DISABLED -- zero-LLM mode active, no network call made",
        }

    if create_fn is None:
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return {
                "text": None, "authority": "ADVISORY", "model_called": False,
                "denial_reason": "ANTHROPIC_API_KEY not set -- cannot run a live model call",
            }
        from anthropic import Anthropic
        create_fn = Anthropic(api_key=api_key).messages.create

    kwargs = {}
    if effort is not None:
        kwargs["output_config"] = {"effort": effort}
    response = create_fn(
        model=model, max_tokens=max_tokens, system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
        **kwargs,
    )

    usage = getattr(response, "usage", None)
    if usage is not None:
        import metrics
        metrics.record_model_usage(
            provider="anthropic", model=model,
            input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
            cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", None),
            cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", None),
        )

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
        }

    return {"text": stripped, "authority": "ADVISORY", "model_called": True, "denial_reason": None}
