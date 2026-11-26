# Kraken interview prep: handoff

Owner goal: get the Kraken **Senior Software Engineer – AI Foundations** job
(Berlin, hybrid). Recruiter call with Brad on **3 Dec 2026**. This file is the
pick-up point for any agent (Claude, Grok bot, a person) continuing this work.
Read it, then `START_HERE.md`.

## Rules that must not be broken

- **Freeze the live site on 2 Dec 2026.** No deploys from then until after the interview.
- **Deploy the platform only with** `./scripts/deploy_platform_with_si_corpus.sh`,
  never plain `railway up`. That ships without the Standing Interview knowledge
  base, and the page silently stops answering (this happened on 25 Nov).
- The corpus `agent/.si_corpus/corpus.json` is built from the **private**
  `karthik-ai-context` repo by `scripts/build_si_corpus.py`. **Never commit it.**
  This repo is public. It must be untracked but not gitignored, so `railway up`
  uploads it.
- After every deploy run `python scripts/live_check.py`. It must print PASS for
  both addresses. It makes no model calls.
- The owner has said: **no model-cost tests** and use tokens efficiently. The
  deploy's model quality gate has been skipped with `SKIP_MODEL_GATE=1`, with
  owner approval each time. Do not run model-calling evals without asking.
- Any page claim about the owner's career must match the submitted CV. Headline:
  "Senior AI Platform Engineer". Never invent salary, titles or years.

## Done (26 Nov 2026), all merged and live

| PR | What |
|---|---|
| #65 | `scripts/live_check.py` + daily "Live check" GitHub Action; deploy rule in START_HERE; honest budget wording ("reset on redeploy"); CV headline; Standing Interview corpus redeployed (361 chunks) |
| #66 | Unlisted `/kraken` page: four AI Foundations areas + three squads, verbatim posting quotes (tested against `agent/fixtures/kraken_ai_foundations_posting_2026-11-26.txt`), honest gaps |
| #67 | "Evals" in the public nav; Standing Interview labelled "This is an AI assistant, not me"; eval snapshot republished from a clean tree (same scores) |
| #68 | README "At a glance" architecture diagram |
| #69 | "Try it in 60 seconds" tour at the top of `/kraken`; `/ask-codebase?q=...` deep link; this handoff doc |
| #70 | Prompt-injection red-team eval, suite 7 (`agent/injection_eval.py`, `agent/evals/injection_dataset.json`): 10 attacks through the real write dispatcher, all blocked, and the approved control edit is written. Deterministic, no model. Shown on `/eval`; zero-tolerance CI gate |

Live: https://agentic.karthikdevadoss.com (Kraken page: `/kraken`).

## Next, in order (agreed with the owner)

1. ~~60-second tour on /kraken~~ (#69).
2. ~~Prompt-injection safety eval (suite 7)~~ (#70).
3. **Recorded 2-minute walkthrough** of the Workbench verified run, embedded on
   `/kraken`, as a fallback if a live demo is slow. Generate it with Playwright from
   the recorded run, with no model calls.
4. *(only if 2–3 are done early)* Move gateway budgets from SQLite to the existing
   Postgres, so they survive redeploys. Then update the "Budgets" gap on `/kraken`.
5. *(optional)* Port one eval suite to Inspect AI, a bonus item in the posting.

Avoid before the interview: hosted MCP gateway, Notion/Slack connectors,
Kubernetes, site-wide restyle.

## Open owner decisions (do not act without asking)

- Whether to state openly that the platform was designed by the owner and written
  by Claude Code under his direction.
- Whether Usage or Standing Interview should return to the nav (removed by owner
  decisions on 2026-10-06 and 2026-10-21).
- The Railway token pasted in chat on 26 Nov should be deleted after the last deploy
  (railway.com/account/tokens → `claude`).

## How to verify quickly

```bash
python scripts/live_check.py
cd agent && python ci_python_tests.py
python eval_runner.py injection   # red-team suite, free
```

`ci_python_tests.py` failures that are only sandbox-related: shallow clone
(commit-history tests) and a missing embedding index. Run `python backend_rag_index.py`
first, and run `git fetch --unshallow origin` before `publish_eval_results.py`.
A shallow clone credits the agent-decision suite to the wrong commit; it must say `983161f`. GitHub CI is
the real gate.
