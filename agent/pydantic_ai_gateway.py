"""Pydantic AI slice (platform upgrade item 8): ONE path -- Triage Lab
Scenario A's diagnose() -- rebuilt on Pydantic AI with a typed, validated
output, while every billed model call STILL goes through
reasoning_gateway.call() (purpose gate, LLM_MODE=DISABLED kill switch, cost
recording, injectable create_fn). See docs/PYDANTIC_AI.md.

`GatewayModel` is a custom pydantic_ai `Model` whose only network seam is
reasoning_gateway.call(). Pydantic AI never talks to Anthropic itself here,
so the `anthropic` provider/SDK path inside pydantic_ai is unused.
Output is ADVISORY only, exactly as before: nothing here authorizes anything.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")  # no startup banner on stdout

from pydantic import BaseModel
from pydantic_ai import Agent, PromptedOutput
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.settings import ModelSettings

import reasoning_gateway


class GatewayDenied(Exception):
    """The gateway made no usable model call (bad purpose, LLM_MODE=DISABLED,
    no API key, or empty model text). Carries the gateway's honest reason."""

    def __init__(self, reason: str, usage: dict | None = None):
        super().__init__(reason)
        self.reason = reason
        self.usage = usage


class Diagnosis(BaseModel):
    """A root-cause diagnosis."""  # kept short: Pydantic AI puts this in the prompted schema
    hypothesis: str
    root_cause: str
    affected_component: str
    confidence: Literal["HIGH", "MEDIUM", "LOW"]


@dataclass
class GatewayModel(Model):
    """pydantic_ai Model backed by reasoning_gateway.call()."""
    purpose: str = "NOVEL_ROOT_CAUSE_HYPOTHESES"
    max_tokens: int = 512
    api_key: str | None = None
    create_fn: object = None
    effort: str | None = None
    gateway_model: str = "claude-sonnet-5"
    gateway_calls: list = field(default_factory=list)  # every raw gateway result, for usage/audit

    def __post_init__(self):
        Model.__init__(self)

    @property
    def model_name(self) -> str:
        return self.gateway_model

    @property
    def system(self) -> str:
        return "anthropic-via-reasoning-gateway"

    async def request(self, messages: list[ModelMessage], model_settings: ModelSettings | None,
                      model_request_parameters: ModelRequestParameters) -> ModelResponse:
        # prepare_request() resolves the output mode and, for PromptedOutput, appends
        # the JSON-schema instructions to instruction_parts (every built-in Model does this).
        model_settings, model_request_parameters = self.prepare_request(model_settings, model_request_parameters)
        instructions = [p.content for p in (model_request_parameters.instruction_parts or [])]
        if not instructions:  # direct model.request() calls without an Agent
            instructions = [m.instructions for m in messages
                            if isinstance(m, ModelRequest) and m.instructions]
        user = "\n\n".join(
            p.content for m in messages if isinstance(m, ModelRequest)
            for p in m.parts if isinstance(p, UserPromptPart) and isinstance(p.content, str))
        result = reasoning_gateway.call(
            purpose=self.purpose, system_prompt="\n\n".join(instructions), user_message=user,
            max_tokens=self.max_tokens, api_key=self.api_key, create_fn=self.create_fn,
            effort=self.effort, model=self.gateway_model,
        )
        self.gateway_calls.append(result)
        if result["text"] is None:
            raise GatewayDenied(result["denial_reason"], result["usage"])
        return ModelResponse(parts=[TextPart(result["text"])], model_name=self.gateway_model)


def run_typed_diagnosis(system_prompt: str, evidence: str, *, purpose: str, max_tokens: int,
                        api_key: str | None, create_fn) -> tuple[Diagnosis, dict | None]:
    """Runs one typed diagnosis. Returns (Diagnosis, usage).
    Raises GatewayDenied (no usable call) or UnexpectedModelBehavior (model
    output did not validate against Diagnosis). retries=0 so a malformed answer
    fails honestly instead of triggering a second billed call."""
    model = GatewayModel(purpose=purpose, max_tokens=max_tokens, api_key=api_key, create_fn=create_fn)
    agent = Agent(model, instructions=system_prompt, output_type=PromptedOutput(Diagnosis),
                  retries={"output": 0})
    try:
        result = agent.run_sync(evidence)
    except UnexpectedModelBehavior as exc:
        exc.gateway_usage = model.gateway_calls[-1]["usage"] if model.gateway_calls else None
        raise
    return result.output, model.gateway_calls[-1]["usage"]
