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
| #73 | Gateway/Triage/Standing Interview budgets in Postgres (survive redeploys, fail closed) |
| #74 | GitHub knowledge pipeline (`agent/github_knowledge.py`): PRs/issues synced every 30 min, re-embeds only changed items, removes deleted ones, freshness on every hit, keep-last-good + committed snapshot (`agent/knowledge/github_snapshot.json`). Panel on Ask the Codebase; `/api/ask-github`, `/api/github-knowledge`. Railway: `GITHUB_KNOWLEDGE_SYNC=1` |
| #75 | Trace viewer: every Ask the Codebase answer returns a `trace_id`; `/traces/{id}` waterfall (`ask_codebase.request` → `permission.filter`, `embedding.query`, `retrieval.rank`). Question never recorded as text |
| #71 | 43-second captioned walkthrough video on `/kraken` (`agent/web/media/`), recorded by `scripts/record_walkthrough.js` |
| #70 | Prompt-injection red-team eval, suite 7 (`agent/injection_eval.py`, `agent/evals/injection_dataset.json`): 10 attacks through the real write dispatcher, all blocked, and the approved control edit is written. Deterministic, no model. Shown on `/eval`; zero-tolerance CI gate |

Live: https://agentic.karthikdevadoss.com (Kraken page: `/kraken`).

## Next, in order (agreed with the owner)

1. ~~60-second tour on /kraken~~ (#69).
2. ~~Prompt-injection safety eval (suite 7)~~ (#70).
3. ~~Recorded walkthrough on /kraken~~ (#71). Regenerate with
   `node scripts/record_walkthrough.js` while a local `python agent/web_server.py`
   is running (step 3 reads the recorded run from the live site). Needs ffmpeg.
4. ~~Budgets in Postgres~~ (#73). `budget_store.py` uses Postgres when
   `BUDGET_DATABASE_URL` is set (Railway: `${{Postgres.DATABASE_URL}}` on
   agentic-platform-backend, set 26 Nov), otherwise SQLite. A transaction-scoped
   advisory lock serialises writers. Unreachable store = every billed call refused
   (fail closed). Proof: `test_budget_store_postgres` (20-thread race against a cap of
   5 → exactly 5; with the lock removed, 7–11 got through) and `test_budget_fail_closed`.
   Next idea (not built): per-team keys.
   **Gotcha:** after a mutation test, delete `agent/__pycache__`. A restored file with the
   same size and mtime-second can keep running the mutated bytecode.
5. *(optional)* Port one eval suite to Inspect AI, a bonus item in the posting.
6. ~~GitHub knowledge pipeline~~ (#74) and ~~trace viewer~~ (#75), both done 26 Nov.
   Refresh the committed snapshot any time with `cd agent && python github_knowledge.py`.
   Ideas not built: per-team budget keys; Notion/Slack connectors (need accounts).

7. **AI Usage, Cost & Value Intelligence** (`/ai-usage`, branch `feat/ai-usage-intel`,
   28 Nov). It shows cost, value and recommendations, with per-number provenance.
   Metered spend and subscription value are kept apart. Public visitors get
   fictional demo data only; live data needs the owner token.
   Docs: `docs/AI_USAGE_INTELLIGENCE.md` (architecture, limits, revert steps) and
   `docs/AI_USAGE_LEARNING_GUIDE.md` (owner study plan; says AI wrote the code).
   **Restore point:** branch `stable-pre-ai-usage` = master `c9855e3`, deployed and
   live-checked 28 Nov before this feature. Tags cannot be pushed from the cloud
   session, so it is a branch. To revert, deploy that branch with the corpus script.
   Railway CLI in a cloud session: `RAILWAY_API_TOKEN=proxy-injected-placeholder`
   (the real token is injected by the environment's network secret).
   Not built yet: an enriched live gateway sink, automatic outcome capture from CI,
   provider billing reconciliation, logins/SSO and per-scope budget enforcement.

Avoid before the interview: hosted MCP gateway, Notion/Slack connectors,
Kubernetes, site-wide restyle.

## Open owner decisions (do not act without asking)

- **The featured Workbench run says "build saravanan with care"** (run `trainer-4e68fe81`,
  the only completed run in the production ledger). Do NOT edit the record or hide the
  text: that would fake evidence. The honest fix is a new real run. On the Workbench,
  submit *Change the footer text to "Changes ship only after a person approves them"*
  with the owner token (`OWNER_API_TOKEN`, Railway → agentic-platform-backend →
  Variables). That counts as the person's approval. The new run then becomes the
  featured one. Afterwards re-record the video: `node scripts/record_walkthrough.js`.
  The owner chose to do this later and declined to share the token on 26 Nov.

- Whether to state openly that the platform was designed by the owner and written
  by Claude Code under his direction.
- Whether the Claude Code hook should stop storing prompt/tool excerpts by default
  (privacy finding from the AI Usage gap analysis; the new feature does not read them).
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
