# Public home page — research and options

**Date:** 2026-09-29 · **Status:** RESEARCH + OPTIONS ONLY. Nothing built, no nav changed, nothing deployed.
**File is deliberately untracked.** Do not commit unless the Owner says so.
**Audience of the page:** a human who clicked a link on Karthik's CV. Not an ATS. Not a peer engineer browsing for fun.
**Target roles:** Senior Backend + Agentic/Applied AI, Lead GenAI Engineering (IC), English-language, Germany.

---

## 0. The one finding that decides everything

`agent/web_server.py:2264` — `Route("/", workbench_page)`.

**The root URL is the Workbench.** Right now, an HR person who pastes
`https://agentic-platform-backend-production.up.railway.app` into a browser lands on a live delivery-pipeline console. Verified 2026-09-29: `GET /` returns 200 and serves `workbench.html`.

That is the exact failure the Owner named. Everything below is a proposal for what should be at `/` instead. Note that this is a *routing* change plus one new page — the Workbench itself does not move or change, it just stops being the front door.

**Second precondition, verified today:** "private" currently means *absent from nav*, not *unreachable*. `/learn` and `/jd-match` both return **200** to anyone who types the URL. If the new home page is the first thing that gets real recruiter traffic, the odds of someone finding those pages go up, not down. Making them genuinely private is `BL-099` in the backlog and should land in the same change as the home page, or before it.

---

## 1. Research

### 1.1 Honest note on source quality, up front

The Owner asked for sources after 2026-09-01. **Material dated September 2026 that is actually *about* this question is thin.** What exists at that date is mostly job-board aggregator pages (Glassdoor/Wellfound/Built In listing counts), which say nothing about scanning behaviour.

Three further limits on this research, stated rather than papered over:

- **Reddit and X could not be searched directly.** The available search tool is US-indexed and returned SEO content farms rather than r/CSCareerGermany, r/cscareerquestionsEU, r/Arbeitsleben or X threads. No primary community posts were retrieved. Any claim below that sounds like "developers on Reddit say…" is **not** in this document, because I could not verify one.
- **No dated Sep 2026+ engineering-blog posts** were found from adesso, ZEISS, SAP, Delivery Hero, N26, Trade Republic or Thoughtworks DE on hiring or portfolio review. Nothing is cited from them.
- **The strongest source is June 2026**, not September. It is labelled as such everywhere it is used.

A second honest caveat: several widely-repeated figures in this space ("recruiters spend 6–7 seconds", "80% more engagement with runnable code", "68% of first views are mobile") appear on undated commercial blogs with no methodology. They are directionally consistent with each other, and they are **not** treated as measurements below. They are labelled as folklore where used.

### 1.2 What the good sources actually say

**Source A — Provn, "Agentic Engineer Hiring: What CPTOs Test in 2026", dated 2026-06-03.** The most specific and most useful source found. Its split between signal and noise:

| Treated as strong proof | Treated as noise |
|---|---|
| Problem decomposition (task graphs, decision trees) | Tool familiarity alone — *"Tool knowledge on its own is weak signal now"* |
| **System boundaries: what the agent can and cannot do** | Polished output with no control mechanism |
| **Evaluation discipline — test cases, error analysis** | Happy-path-only demos |
| **Production awareness: latency, cost, observability** | Generic AI-fluency claims |
| Communication of trade-offs and design rationale | AI-assisted résumés with no evidence |

Two direct quotes worth designing against:

> "A two-page project note plus a five-minute demo can carry more signal than a big site full of generic AI projects."

> Demos should show "one successful path and one controlled failure path."

It also states human-in-the-loop and observability are non-negotiable in production agentic systems.

**Source B — the 2026 agentic-hiring commentary cluster (KORE1, HeroHunt; 2026, month not stated on page).** Consistent theme: eval literacy is the discriminator. The framing that recurs is roughly *can this person turn an agent into a production workflow people trust, or only give a slick demo* — and that engineers who have actually put agents in production are a narrow slice of the market. Treat the specific salary numbers on these pages as marketing, not data; treat the eval-literacy point as corroborating Source A, which is independent of it.

**Source C — the "AI slop" cluster: The Markup 2026-01-24, Forbes/Rachel Wells 2026-03-18.** Dated and substantive. The application pool is now flooded with polished, low-quality, AI-generated material; Forbes reports 67% of managers saying AI résumés are actively slowing hiring down. The consequence that matters here: **polish is no longer evidence of effort, so it no longer differentiates.** Verifiability does. A related and repeated point — candidates who present only successes read as either not taking risks or not being honest.

**Source D — Berlin/Germany market colour (2026, month not stated).** Berlin startups and scale-ups are English-first by default in engineering; the in-demand backend languages named include **Java** alongside Go, Python and Kotlin; AI/ML postings in Berlin are typically English. Named active AI/ML hirers include Zalando, JetBrains, Scalable Capital, DeepL, Parloa, Helsing, Aleph Alpha, plus the fintech cluster (N26, Trade Republic, Raisin, Solaris, Mambu). This supports the Owner's own targeting; it is not a scanning-behaviour source.

**Source E — the portfolio-advice cluster (dataexpert.io, upskillist, Hakia, Scaler, CVWon; undated or 2026-generic).** Low evidential weight, but unanimous on three things, and none of them contradicts A–C: the portfolio link is clicked *before* the experience section is read; deployed and running beats notebooks and papers; and generative AI / RAG is now table stakes on an AI CV rather than a differentiator. One useful corollary if true: a live demo URL carries more weight than an experience bullet, which is an argument for putting the Standing Interview above the fold rather than in a list.

### 1.3 What this means for a 15–30 second visit

Synthesising A–E, and separating what is well-evidenced from what is inference:

**Well-evidenced:**
1. The visitor is scanning for *proof*, and the bar for what counts as proof rose in 2026. Claims are now assumed to be AI-assisted until demonstrated otherwise (Source C).
2. For agentic roles specifically, the proof they want is **boundaries, evals, and cost/observability** — not a feature list (Source A).
3. A tool list is now a *negative* differentiator, because everyone has one (Source A, explicit).
4. Admitting what does not work is a trust signal in 2026, not a weakness (Sources A and C, independently).

**Inference, labelled as mine:**
5. This portfolio's genuine, unusual asset is that it can *prove* claims live rather than assert them — the Standing Interview answers from a grounded corpus, the capability registry carries verification levels, the ledger holds real token counts. Almost nothing in the 2026 advice literature assumes a candidate can do that, because almost none can. The page should lead with the thing that is rare, not with the thing that is expected.
6. Corollary: the biggest risk is **not** looking unimpressive. It is looking like one more polished AI-generated portfolio. Design against that specifically.

### 1.4 Known bounce triggers, mapped to this site

| Trigger | Present today? | Source |
|---|---|---|
| Lands on an internal tool / console | **Yes — `/` is the Workbench** | Owner; verified in code |
| Keyword-stuffed skill wall | Not currently | A ("tool knowledge alone is weak signal") |
| "I built an AI platform" with no clickable proof | Risk on any new page | A, C |
| Happy-path demo only, no failure path shown | Risk | A (explicit) |
| A wiki/learning tree presented as a credential | **Yes — `/learn` is reachable** | Owner; verified 200 |
| Over-claimed retrieval stack (vector DB / rerank / multi-provider) | Would be false here | Owner's constraint list |
| Photo-heavy agency aesthetic | Not currently | Owner |

---

## 2. What can honestly be claimed

Verified against this repository on 2026-09-29, not from memory. `docs/PORTFOLIO_CAPABILITIES.yaml` holds **22 capabilities**: 13 `PRODUCTION_VERIFIED`, 4 `RUNTIME_VERIFIED`, 5 `TESTED`.

**Safe to put on a home page (each has a clickable destination):**

| Claim | Evidence level | Where it points |
|---|---|---|
| Grounded first-person interview answering over a private corpus | PRODUCTION_VERIFIED | `/standing-interview` — live, answers in ~6–15 s |
| Hash-bound human-in-the-loop write boundary (the model has no code path to approve its own change) | PRODUCTION_VERIFIED | `/workbench` + GitHub |
| Single model boundary with a zero-LLM kill switch | PRODUCTION_VERIFIED | GitHub |
| Durable, stateful software-change workflow on LangGraph, checkpointed in Postgres, survives a container restart | PRODUCTION_VERIFIED | API + GitHub |
| Durable event ledger with real token counts | PRODUCTION_VERIFIED | `/usage` |
| Deterministic zero-LLM CI gates for AI-characteristic defects | PRODUCTION_VERIFIED | GitHub |
| Java 21 / Spring Boot 4.1.1 REST API, Postgres + JPA + Flyway, BCrypt/JWT with RBAC, Resilience4j | PRODUCTION_VERIFIED | customer energy app + GitHub |
| RAG + embeddings + MCP context retrieval with a labelled retrieval eval in CI | RUNTIME_VERIFIED | `/ask-codebase` |
| Builder / independent-evaluator separation | RUNTIME_VERIFIED | GitHub |

**Must be labelled PARTIAL or left off — implemented but not production-proven:** transactional Kafka outbox (TESTED), Redis cache-aside (TESTED, gated off in production), RS256 JWT with JWKS (TESTED), BFF aggregator fan-out (TESTED), real-topology gating tier (TESTED).

**Must never appear (Owner's list, all confirmed absent from the repo):** a second LLM provider · hybrid search or reranking · a Pinecone-class vector database · Spring AI · React/TypeScript specialism · Terraform/SRE ownership · "I designed the NRG/BCBSA architecture" · Kafka at NRG · 3M customers as a personal metric.

Two traps specific to this site:
- The repo *does* have a `kafka-outbox` capability. It is **this platform's own** outbox pattern, TESTED, not production. It must never sit near the NRG paragraph, or a reader will merge the two into "Kafka at NRG", which is false.
- NRG is described as **multi-million-customer retail energy systems**, never with a personal metric attached.

---

## 3. The options

All four assume `/` becomes a new page and the Workbench moves to `/workbench` only.

---

### OPTION A — "Recruiter brief"

*The lowest-risk option. One screen, four facts, one live thing to click.*

**First screen (no scroll, ~1000px):**

```
┌──────────────────────────────────────────────────────────────────────┐
│  Karthik Devadoss — Senior Backend Engineer (Java/Spring) building   │
│  production agentic AI systems.  Berlin · German PR · English         │
│                                                                       │
│  15 years backend. Currently at NRG, a multi-million-customer         │
│  retail-energy platform. For the last year I have been building and   │
│  running the agentic delivery platform this page is served from.      │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  ▸ Interview me right now                                      │  │
│  │    Ask about my backend work. Answers come from my own          │  │
│  │    recorded engineering knowledge — if it isn't in there,       │  │
│  │    it says so instead of guessing.        [ Ask a question → ]  │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  What runs in production here                                         │
│  · Human approval gate the model cannot bypass                        │
│  · Durable workflow that survives a container restart                 │
│  · Retrieval grounded in a private corpus, with a refusal path        │
│  · Every model call metered — real tokens, real cost                  │
│                                                                       │
│  [ Role showcase ]  [ Source on GitHub ]  [ CV (PDF) ]                │
└──────────────────────────────────────────────────────────────────────┘
```

- **Primary CTA:** ask the Standing Interview a question, inline on the home page.
- **Secondary:** Role Showcase · GitHub · CV.
- **Impresses:** HR strongly (one screen, plain language, a name, a location, a clickable thing). Tech screener adequately — they will click through to GitHub within seconds.
- **Risks:** a tech screener may read it as *marketing* and bounce to GitHub without seeing the engineering. Four bullets is close to the "generic AI fluency claim" pattern Source A warns about — each bullet must be a link to the real thing, or it becomes exactly the noise it is trying to avoid.
- **Build vs reuse:** one new static HTML page reusing `style.css` and the existing shell. The Standing Interview box can be a link (zero new code) or a small inline form posting to the existing `/api/standing-interview/ask` (no new backend). Reuse: everything. Build: ~1 page.
- **AI topics the page itself demonstrates:** essentially none if the CTA is a link; *grounded RAG with an honest refusal path* if the ask box is inline, because the visitor can watch it decline a question it cannot answer. That single behaviour is the cheapest way to demonstrate Source A's "system boundaries" point.

---

### OPTION B — "Dual path"

*Two doors, because the Owner is applying for two different jobs.*

**First screen:**

```
┌──────────────────────────────────────────────────────────────────────┐
│  Karthik Devadoss · Berlin · Senior Backend / Agentic AI (IC)         │
│  15 years Java & Spring. Currently building agentic systems that      │
│  run in production — including the one serving this page.             │
│                                                                       │
│   What are you hiring for?                                            │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐    │
│  │  JAVA / SPRING BACKEND      │  │  AGENTIC / GENAI            │    │
│  │                             │  │                             │    │
│  │  Java 21, Spring Boot 4.1,  │  │  Agent + tools, a human     │    │
│  │  Postgres/JPA/Flyway, JWT   │  │  approval gate the model    │    │
│  │  + RBAC, Resilience4j.      │  │  cannot bypass, grounded    │    │
│  │  A running app, not a repo. │  │  retrieval, evals in CI,    │    │
│  │                             │  │  metered cost per run.      │    │
│  │  [ See the running app → ]  │  │  [ See it work → ]          │    │
│  └─────────────────────────────┘  └─────────────────────────────┘    │
│                                                                       │
│  Not sure? Ask my Standing Interview a question instead. →            │
│  GitHub · CV                                                          │
└──────────────────────────────────────────────────────────────────────┘
```

- **Primary CTA:** whichever door matches the visitor's vacancy.
- **Secondary:** Standing Interview · GitHub · CV.
- **Impresses:** HR very strongly — it answers their actual question ("is this person right for *my* req?") in one glance. Tech screener well, because each door leads to running software.
- **Risks:** the real one is **dilution** — a reader may conclude he is half-and-half at both rather than strong at the intersection, which is precisely the positioning that sells in 2026. Also two doors means two landing destinations to maintain, and the Java door currently points at a customer app whose auth claims have not been re-verified (`BL-102`). Mitigation: a single sentence above the doors that names the intersection, so the doors read as *emphasis*, not as *split identity*.
- **Build vs reuse:** one new page, two panels; both link to existing surfaces. No backend work. Possibly one new thin landing section on the customer app.
- **AI topics demonstrated:** none by the page itself. It is a router. All demonstration is one click away.

---

### OPTION C — "Proof wall"

*The counter-positioning play against AI slop: publish what is NOT true.*

**First screen:**

```
┌──────────────────────────────────────────────────────────────────────┐
│  Karthik Devadoss — Senior Backend / Agentic AI · Berlin · English    │
│                                                                       │
│  Every claim below links to running software or to the source.        │
│  The "not yet" rows are here on purpose.                              │
│                                                                       │
│  CAPABILITY                          STATUS          PROOF            │
│  ───────────────────────────────────────────────────────────────────  │
│  Human approval gate the model       LIVE            open workbench   │
│    cannot bypass                                                      │
│  Durable agent workflow, survives    LIVE            how it works     │
│    a restart mid-run                                                  │
│  Grounded retrieval + refusal path   LIVE            ask it now       │
│  Metered cost per model call         LIVE            open usage       │
│  Java 21 / Spring Boot REST + JWT    LIVE            open the app     │
│  Transactional outbox                PARTIAL         tested, not in   │
│                                                        production     │
│  Second model provider / failover    NOT YET         —                │
│  Hybrid search + reranking           NOT YET         —                │
│  ───────────────────────────────────────────────────────────────────  │
│                                                                       │
│  [ Ask my Standing Interview → ]   Role showcase · GitHub · CV        │
└──────────────────────────────────────────────────────────────────────┘
```

- **Primary CTA:** any PROOF link — the table *is* the navigation.
- **Secondary:** Standing Interview · Role Showcase · GitHub.
- **Impresses:** tech screener and hiring manager very strongly. This is Source A's "system boundaries" and "controlled failure path" rendered as a page, and it is the hardest thing in this document for another candidate to fake. HR: **mixed** — a table of red rows can read as a list of things he cannot do if the labels are careless.
- **Risks:** the serious one. (1) A recruiter skimming at speed may register "NOT YET ×2" and nothing else — the LIVE rows must dominate visually and come first, and the NOT-YET block must be short and framed as scope, not gaps. (2) It invites a challenge on every row, so every row must survive one. (3) It is only credible if the statuses are *generated from the registry*, not hand-typed — a hand-typed proof wall that drifts from reality is worse than no proof wall.
- **Build vs reuse:** reuse `docs/PORTFOLIO_CAPABILITIES.yaml` as the source of truth; the registry already carries `verification_level` on all 22 entries and 45 validated evidence links. Build: a renderer plus an editorial decision about which 6–8 rows appear above the fold. **Do not hand-maintain a second list.**
- **AI topics demonstrated:** verification-level discipline, evidence linking, and honest capability boundaries — i.e. the page is itself an artefact of the evaluation practice it is claiming. Strongest option on this axis.

---

### OPTION D — "Ask it anything, and watch it refuse" *(invented from the Sep-2026 research)*

*Source A asks for one successful path and one controlled failure path. This option makes that the entire home page.*

The insight: everyone's 2026 portfolio has a chatbot. Almost nobody's chatbot **declines**. The differentiator is not that it answers — it is that it visibly refuses when it is not grounded, and that the refusal is a deterministic control rather than the model being polite.

**First screen:**

```
┌──────────────────────────────────────────────────────────────────────┐
│  Karthik Devadoss · Senior Backend + Agentic AI · Berlin · English    │
│                                                                       │
│  Ask me anything about my engineering work.                           │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  How did you use Spring Security at NRG?            [ Ask ]    │  │
│  └────────────────────────────────────────────────────────────────┘  │
│   Try:  "your Kafka experience"  ·  "the approval gate"  ·            │
│         "what's the capital of France?"  ← this one it refuses        │
│                                                                       │
│  ── why that matters ───────────────────────────────────────────────  │
│  This answers only from my own recorded engineering knowledge.        │
│  When retrieval finds nothing solid, code refuses before the model    │
│  is even called — the refusal is a gate, not the model being polite.  │
│  Same discipline runs the rest of the platform: a human approval      │
│  step the model has no code path to bypass, and every call metered.   │
│                                                                       │
│  Backend track: Java 21 / Spring Boot app →    GitHub · CV · Showcase │
└──────────────────────────────────────────────────────────────────────┘
```

The move is the third suggested chip. **The site invites the visitor to break it, and then shows the control holding.** That is the "controlled failure path" Source A asks for, converted from a claim into a two-click experience — and it is verified real: production refuses that exact question (`ungrounded_model_declined`, retrieval score 0.5121, measured 2026-09-29).

- **Primary CTA:** ask a question — including the one designed to fail.
- **Secondary:** the Java/Spring track · GitHub · CV · Role Showcase.
- **Impresses:** tech screener and engineering manager most of all; this is the single most senior-looking thing on the site, because it demonstrates judgement about boundaries rather than capability. HR: good, provided the box works on the first try and the copy stays plain. It is also the most memorable option — a recruiter describing it to a hiring manager has a story to tell.
- **Risks:** the highest-variance option. (1) **It is only as good as the Standing Interview's next answer**, and the audit finished today found real defects: 39% of answered questions volunteer a negative nobody asked for, one legitimate interview question is refused 3/3, and another is refused 1/3. Fronting the site with it before `BL-142`–`BL-144` land would put the weakest surface first. (2) Latency is 5–16 s — needs a visible progress state or it reads as broken. (3) The endpoint has **no rate limit, no cooldown and no daily cap** (`SI-13` / `BL-147`); making it the front door turns an uncapped paid endpoint into the most-clicked thing on the site. **This option is gated on that fix, not merely improved by it.**
- **Build vs reuse:** reuse the existing API and page logic wholesale. Build: one page plus the suggested-question chips.
- **AI topics demonstrated:** the most of any option — grounded RAG, deterministic refusal as a control, model-as-advisory, and (if the ask box surfaces the run's token count) real cost transparency in the same view.

---

### Comparison

| | A · Recruiter brief | B · Dual path | C · Proof wall | D · Ask it / watch it refuse |
|---|---|---|---|---|
| HR-safe in 15 s | ★★★★ | ★★★★ | ★★ | ★★★ |
| Convinces a tech screener | ★★ | ★★★ | ★★★★ | ★★★★ |
| Counters "AI slop" suspicion | ★★ | ★★ | ★★★★ | ★★★★ |
| Build cost | lowest | low | medium | low–medium |
| Depends on unfixed defects | no | no | no | **yes** |
| Memorable | ★★ | ★★ | ★★★ | ★★★★ |

---

## 4. Recommendation for applications THIS WEEK

**Ship Option A, with one element of C and one of D folded in, and keep it to one screen.**

Reasoning, in order of weight:

1. **The urgent problem is not "the home page is unimpressive", it is "the home page is the Workbench."** Any of the four fixes that. A fixes it with the least that can go wrong, and Source A's own advice — a tight brief beats a big site — points the same way.
2. **D is the best page and is not ready this week.** The audit committed today found the Standing Interview volunteering unsolicited negatives on 39% of answered questions, refusing one legitimate interview question on 3 of 3 draws, and running on an endpoint with no rate limit. Putting that first while applying would be leading with the surface that has known, documented, unfixed defects. Borrow its *idea* now; promote it to the front door after `BL-142`–`BL-144` and `BL-147`.
3. **C's honesty is the strongest differentiator and its full form is risky for HR.** Take one row of it: a single line under the claims saying what is deliberately not built. That gets most of the trust signal at none of the bounce risk.

**The concrete recommendation** — Option A's layout, plus:
- one live ask box (from D) with a visible loading state and **three** suggested questions, one of which is answered honestly and briefly rather than one designed to fail — save the refusal demo for when the gates are fixed;
- one line under the capability bullets (from C): *"Not built here: a second model provider, hybrid search or reranking, a managed vector database. The retrieval is plain cosine over a small corpus, which is what this scale needs."* Factual, checkable, and it pre-empts the exact over-claim a technical reader is scanning for;
- every bullet is a link to the running thing. No bullet without a destination.

Sequencing note: this needs `BL-099` (make `/learn` and `/jd-match` genuinely unreachable, not merely unlinked) either first or in the same change. Publishing a front door that increases traffic while two pages the Owner considers private still return 200 is the wrong order.

### What NOT to build this week

- **Not Option D as the front door.** Gated on the SI fix sprint and on a rate limit.
- **Not the full Proof Wall.** Worth building, but only rendered *from* `PORTFOLIO_CAPABILITIES.yaml` — a hand-typed version will drift, and a drifted proof wall is worse than none. That is a sprint item, not a this-week item.
- **Not a nav change.** The Owner said so, and the current nav is guarded by a passing spec; changing it and the home page together makes a failure ambiguous.
- **Not a redesign of Workbench, Triage, Usage or Ask the Codebase.** Out of scope; `BL-100` covers them.
- **Not a photo, a hero image, an animated gradient, or a testimonial block.** Polish is no longer a differentiator (Source C) and this Owner's standing instruction is that nothing should read as AI-generated.
- **Not a skills grid or a tech-logo wall.** Source A is explicit that tool familiarity alone is now weak signal.
- **Not a blog, a "my journey" narrative, or a Learn wiki link.**
- **Not a second CV rendering on the page.** The CV stays a separate ATS-safe artefact; this page is for the human who already clicked.

---

## 5. Three first-fold copy blocks

Short, factual, English, no metric that is not true. Each is ~40–60 words.

**Copy block 1 — hybrid default (recommended)**

> I'm a senior backend engineer — Java and Spring, fifteen years — who now builds agentic AI systems that run in production. Currently at NRG, working on multi-million-customer retail energy systems. The platform serving this page is one I built: a human approval step the model cannot bypass, and every model call metered.

**Copy block 2 — AI-first (for an agentic/GenAI req)**

> I build agentic systems that hold up outside a demo. This platform runs an approval gate the model has no code path to bypass, a durable workflow that survives a container restart mid-run, retrieval grounded in a private corpus that refuses rather than guesses, and evals that block CI. Fifteen years of Java and Spring underneath it.

**Copy block 3 — backend-first (for a Java/Spring req)**

> Fifteen years of backend engineering in Java and Spring — currently multi-million-customer retail energy systems at NRG, previously healthcare and insurance integration. Java 21, Spring Boot 4.1, Postgres, JWT and RBAC, resilience patterns. For the last year I've also been building the agentic AI delivery platform that serves this page.

*Notes on wording, so the constraints survive an edit:* "multi-million-customer retail energy systems" describes NRG, never a personal metric. No sentence claims the NRG or BCBSA architecture was his. Kafka is not mentioned in any block — the platform's own outbox is TESTED, not production, and any Kafka sentence sitting near the NRG sentence risks reading as Kafka at NRG. "Evals that block CI" is true of the retrieval/routing eval in `eval_runner.py`; it is not a claim about agent evals.

---

## 6. Sources

| Source | Date | Weight |
|---|---|---|
| [Provn — Agentic Engineer Hiring: What CPTOs Test in 2026](https://provn.co/blog/2026/06/agentic-engineer-hiring-requirements) | **2026-06-03** | **High** — specific, dated, directly on topic |
| [The Markup — hiring in an era of fake candidates, real scams and AI slop](https://themarkup.org/hello-world/2026/01/24/we-posted-a-job-then-came-the-ai-slop-impersonator-and-recruiter-scam) | **2026-01-24** | High — dated, first-hand |
| [Forbes — AI résumés are sabotaging the hiring process, 67% of managers reveal](https://www.forbes.com/sites/rachelwells/2026/03/18/ai-resumes-are-sabotaging-the-hiring-process-67-of-managers-reveal/) | **2026-03-18** | Medium-high — dated, survey-based |
| [KORE1 — Agentic AI Engineering Hiring Survey 2026](https://www.kore1.com/agentic-ai-hiring-2026/) · [How to Hire Agentic AI Engineers in 2026](https://www.kore1.com/hire-agentic-ai-engineers-2026/) | 2026, month not stated | Medium — corroborates Provn on evals |
| [HeroHunt — How to Recruit AI Evals Engineers (2026)](https://www.herohunt.ai/blog/how-to-recruit-ai-evals-engineers-2026/) · [Surviving the AI Application Flood (2026)](https://www.herohunt.ai/blog/surviving-the-ai-application-flood-2026-playbook/) | 2026, month not stated | Medium |
| [Migaku — English-speaking jobs in Berlin tech (2026)](https://migaku.com/blog/language-fun/how-to-find-english-speaking-jobs-in-berlins-tech-scene) | 2026, month not stated | Medium — market colour only |
| [Glassdoor — AI engineer jobs in Germany, September 2026](https://www.glassdoor.com/Job/germany-artificial-intelligence-engineer-jobs-SRCH_IL.0,7_IN96_KO8,40.htm) · [Agentic AI engineering jobs in Germany, Sep 2026](https://agentic-engineering-jobs.com/jobs/germany) | **Sep 2026** | Low — listing counts only; second URL returned HTTP 500 when fetched |
| [dataexpert.io](https://www.dataexpert.io/blog/ultimate-guide-ai-engineering-portfolios) · [upskillist](https://www.upskillist.com/blog/10-ai-portfolio-examples-impress-recruiters/) · [Hakia](https://hakia.com/skills/building-portfolio/) · [Scaler](https://www.scaler.com/blog/10-ai-portfolio-projects-to-land-your-dream-job-2026/) · [CVWon](https://cvwon.com/blog/ai-engineer-cv-2026) | undated / 2026-generic | **Low — treated as folklore**, not measurement. The "6–7 second scan", "80% more engagement" and "68% mobile" figures come from here and carry no methodology |

**Not retrieved, and therefore not cited anywhere above:** Reddit (r/CSCareerGermany, r/cscareerquestionsEU, r/germantrees, r/Arbeitsleben), X/Twitter, StepStone/Xing commentary, and engineering blogs from adesso, ZEISS, SAP, Delivery Hero, N26, Trade Republic or Thoughtworks DE. The search tool available here is US-indexed and returned no primary posts from any of them. If the Owner wants community signal specifically, that needs a manual pass or a different tool — it is a real gap in this research, not an omission.

---

RECOMMENDED_OPTION: **A (Recruiter brief) as the shipped page this week — one screen, one live ask box borrowed from D, and one "not built here" line borrowed from C. Option D becomes the front door once BL-142–BL-144 and BL-147 land; Option C ships later, rendered from `PORTFOLIO_CAPABILITIES.yaml` rather than hand-typed.**

SAFE_TO_BUILD_THIS_WEEK: **yes** — for the recommended A+C+D hybrid only, and only if `BL-099` (making `/learn` and `/jd-match` genuinely unreachable) lands first or in the same change. **No** for full Option D or the full Proof Wall.

OPEN_OWNER_QUESTIONS:
1. **Headline mode** — confirm the hybrid copy block 1, or pick AI-first (block 2) or backend-first (block 3)? Everything else on the page follows from that sentence.
2. **Name and face** — the site currently never says whose portfolio it is. Full name in the H1, and is a photo wanted or explicitly not?
3. **CV link** — should the home page link a PDF CV directly, and if so from where? There is no public CV artefact in this repo today.
4. **Does `/` become the new page, or a new path like `/home` with `/` redirecting?** The former is cleaner; the latter is reversible in one line if the page lands badly.
5. **The "not built here" line** — approve publishing a short list of deliberate absences on the public home page? It is the strongest trust signal in the 2026 research and the one element that needs your sign-off before it is written down publicly.
