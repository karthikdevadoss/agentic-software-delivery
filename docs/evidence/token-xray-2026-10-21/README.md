# Token X-ray evidence (measured 21 Oct 2026)

The source data behind the numbers on the home page and `/tokens`.

Six everyday tasks, each done the wrong way and the right way, 3 runs each.
117 model calls in total, Claude models only (Sonnet 5.5 for five tasks;
Opus 5.5 at max effort vs Haiku 5.5 at low effort for the formula task).
The final answers were read and compared by hand; they were the same or
better on the right way (the `answer` field in the call logs).

| File | What it is |
|---|---|
| `calls_run1.jsonl` .. `calls_run3.jsonl` | One line per model call: scenario, way, step, model, input / cache write / cache read / output / thinking tokens, CLI-reported cost, prompt and answer. Prompts longer than 1,500 characters (the pasted terms page) are trimmed; the token counts are the real ones. |
| `analyze.py` | Rebuilds `results.json` from the call logs (medians, multiples, list-price cost without caching). |
| `results.json` | Per-task medians and multiples. |
| `headline.json` | Totals: 56,188 vs 12,601 tokens, cost without caching, and the 40-task straight-line projection (an estimate, not a measurement). |
| `charts.py` | Draws the charts used on the site from `results.json`. |

Method: Claude Code CLI in print mode with `--output-format json` (real usage
per call), a minimal system prompt, all tools off. Tokens = input + cache
write + cache read + output (thinking included). Cost = Anthropic list price
without caching, so automatic caching does not hide the effect.

Limits: one provider, 3 runs per task, a fixed per-message overhead from the
system prompt that makes the multiple smaller for tiny tasks.

Reproduce the table: `cd docs/evidence/token-xray-2026-10-21 && python analyze.py`.
Publish the site JSON: `python agent/publish_token_xray.py`.
