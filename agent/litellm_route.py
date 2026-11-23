"""Optional LiteLLM proxy routing for reasoning_gateway.

OFF by default: with LITELLM_PROXY_URL unset, reasoning_gateway uses today's
direct Anthropic client and nothing here is exercised.

ON when LITELLM_PROXY_URL is set (e.g. http://localhost:4000): the gateway
builds its Anthropic SDK client with base_url=<proxy>, so the request is a
POST <proxy>/v1/messages (LiteLLM's Anthropic-compatible route) and never
goes to api.anthropic.com. The key sent is LITELLM_API_KEY (the proxy's
master/virtual key), not the Anthropic key -- that stays inside the proxy
container (infra/litellm/). There is no fallback: if the proxy mode is
misconfigured the call is refused, not silently sent direct.

The durable budget gate in reasoning_gateway runs BEFORE this client is
used, so the proxy sits behind the platform's own caps rather than replacing
them. See docs/LITELLM_GATEWAY.md for scope and honest limits (a local,
personal proxy -- not a company-scale gateway).
"""
from __future__ import annotations

import os
from urllib.parse import urlparse


class LiteLLMConfigError(ValueError):
    pass


def proxy_url() -> str | None:
    raw = os.environ.get("LITELLM_PROXY_URL", "").strip()
    return raw.rstrip("/") or None


def enabled() -> bool:
    return proxy_url() is not None


def client_settings(api_key: str | None = None) -> dict:
    """kwargs for the Anthropic SDK client (the SDK import itself stays in
    reasoning_gateway, the one sanctioned importer)."""
    url = proxy_url()
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise LiteLLMConfigError(f"LITELLM_PROXY_URL={url!r} is not an http(s) URL")
    key = api_key or os.environ.get("LITELLM_API_KEY", "").strip()
    if not key:
        raise LiteLLMConfigError("LITELLM_API_KEY not set (the proxy's master/virtual key)")
    return {"api_key": key, "base_url": url}
