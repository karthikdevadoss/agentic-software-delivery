# AI Usage Intelligence: verified external facts

Every provider-specific rule the usage model and pricing rely on, with the
official source and how it was verified. All pages accessed **2026-11-28**.
"Verbatim" means the sentence or table was read word for word. "Summary" means
it came from a tool summary of a long page and was not read word for word.
Re-verify before relying on a price or rule for a new date.

## Token semantics (how each provider counts)

| Rule | Source | Confidence |
|---|---|---|
| Anthropic `usage.input_tokens` **excludes** cache reads and cache writes | code.claude.com/docs/en/monitoring-usage: input token counts "exclude tokens read from or written to the prompt cache" (verbatim). platform.claude.com/docs/en/build-with-claude/prompt-caching: `input_tokens` = tokens "not read from or used to create a cache" (summary) | Verbatim + summary |
| Anthropic `cache_creation_input_tokens` = sum of `cache_creation.ephemeral_5m_input_tokens` + `ephemeral_1h_input_tokens` | prompt-caching page (summary) | Summary |
| Anthropic 5-minute cache write = 1.25x base input; 1-hour write = 2x; cache read 0.1x on most models (0.05x / 0.025x on some) | platform.claude.com/docs/en/about-claude/pricing (verbatim) | Verbatim |
| OpenAI `usage.input_tokens` **includes** `input_tokens_details.cached_tokens` and `cache_write_tokens` | developers.openai.com/api/docs/guides/prompt-caching: "input tokens use the uncached-input, cached-input, or cache-write rate" (verbatim); example arithmetic 12000 - 4000 - 7000 (summary) | Verbatim + summary |
| OpenAI reasoning tokens are **billed as output** and appear inside `output_tokens` (`output_tokens_details.reasoning_tokens`) | developers.openai.com/api/docs/guides/reasoning: "billed as output tokens" (verbatim); usage JSON 1024 reasoning within 1186 output, total 1261 (verbatim) | Verbatim |
| OpenTelemetry GenAI: `gen_ai.usage.input_tokens` SHOULD include cached tokens; `gen_ai.usage.cache_read.input_tokens` and `gen_ai.usage.cache_write.input_tokens` SHOULD be included in it; `gen_ai.usage.output_tokens` SHOULD include `gen_ai.usage.reasoning.output_tokens`. Provider attribute is `gen_ai.provider.name`. Status: Development | github.com/open-telemetry/semantic-conventions-genai, docs/gen-ai/client-inference.md (verbatim footnotes) | Verbatim |
| Claude Code telemetry: `claude_code.token.usage` (`type` = input/output/cacheRead/cacheCreation), `claude_code.cost.usage` (USD); enable with `CLAUDE_CODE_ENABLE_TELEMETRY=1`; "Cost metrics are approximations" | code.claude.com/docs/en/monitoring-usage (verbatim) | Verbatim |

**Consequence for this platform.** The normalized `UsageEvent.input_tokens` is
the **uncached** input (Anthropic's meaning), because each bucket has its own
price. OpenAI input is converted (input − cached − cache_write). When emitting
OpenTelemetry spans, `gen_ai.usage.input_tokens` is the **sum** of all three
buckets, as the convention asks.

## List prices used for cost estimates (USD per 1M tokens, standard tier)

Anthropic, platform.claude.com/docs/en/about-claude/pricing (verbatim table):

| Model | Input | 5m cache write | 1h cache write | Cache read | Output |
|---|---|---|---|---|---|
| Claude Opus 5.5 | 4 | 5 | 8 | 0.20 | 20 |
| Claude Sonnet 5.5 | 2 | 2.50 | 4 | 0.10 | 10 |
| Claude Sonnet 5 | 2 | 2.50 | 4 | 0.20 | 10 |
| Claude Haiku 5.5 (prompt ≤ 100k tokens) | 0.10 | 0.125 | 0.20 | 0.01 | 0.50 |
| Claude Haiku 5.5 (prompt > 100k tokens) | 0.50 | 0.625 | 1 | 0.05 | 2.50 |

Haiku 5.5 long-context rule: "a request's prompt length counts all of its
input tokens, including cache reads and cache writes" (verbatim).

OpenAI, developers.openai.com/api/docs/pricing (verbatim table, ≤272K context):

| Model | Input | Cached input | Output |
|---|---|---|---|
| gpt-6.2-sol | 2.00 | 0.10 | 10.00 |
| gpt-6-luna | 0.10 | 0.01 | 0.50 |
| gpt-5.4-mini | 0.75 | 0.075 | 4.50 |

OpenAI cache-write pricing for `cache_write_tokens` is not in the table above;
the platform prices those at the **input** rate and labels the method.

**These are list prices.** A cost computed from them is an *estimated API
expenditure*. It is not the provider's internal cost, and it is not an invoice:
negotiated discounts, batch and priority tiers, data-residency uplifts and
credits are not reflected.

## What could not be verified

- No public API exposes personal ChatGPT or Claude subscription allowance
  consumption. The platform never claims to measure it.
- Anthropic and OpenAI organisation usage/cost APIs need an admin key. They are
  not connected (owner decision, 2026-11-28).
