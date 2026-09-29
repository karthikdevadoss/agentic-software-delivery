# Recruiter-facing home page — market research and concept recommendations

**Date:** 2026-09-29 · **Repository:** `karthikdevadoss/agentic-software-delivery` @ `d7b4b7e`
**Status:** RESEARCH AND ANALYSIS ONLY. No code, UI, navigation, route, style, content, backlog or deployment change was made. Nothing was committed. Nothing was deployed.
**Research window:** June 2026 onward, as instructed, with recency preference Sept > Aug > earlier 2026.

---

## Source labelling used throughout

| Label | Meaning |
|---|---|
| **FACT** | Directly observable and checked in this session (a live HTTP response, a file, a real job posting's text) |
| **SURVEY** | A named study with a stated sample |
| **RECRUITER OPINION** | A recruiter, HR or hiring-manager view published as commentary |
| **VENDOR CLAIM** | A statistic or assertion published by a company selling into this market, with no methodology given |
| **COMMUNITY ANECDOTE** | Forum/social post |
| **INFERENCE** | My reasoning from the above, marked as mine |

**No Reddit, LinkedIn, X or Kununu post is cited in this report.** The search tooling available here is US-indexed and returned aggregator and SEO content for every community query attempted. I could not reach those platforms, so **no community anecdote appears below at all** — and I have not dressed up SEO content as community sentiment. That is a genuine gap in the brief's coverage and is listed again in §8.

---

# 1. Executive answer

Two things are true at once in late 2026, and the home page has to be built on both.

**First: producing a polished portfolio became free, so polish stopped carrying information.** Every signal that used to mean "this person put in effort" — a tailored CV, a clean personal site, a GitHub repo with a good README, a RAG demo — can now be generated in minutes. Recruiters know it, and they have responded by adding screening steps and by shifting weight onto things that are expensive to fake.

**Second: the things that are still expensive to fake are exactly what Karthik has.** A system that is *deployed and reachable by URL*. Evaluation numbers from a real labelled set. A crash drill with a real kill. A human-approval boundary enforced in code rather than in a prompt. And — the rarest of all — a documented account of what the system *cannot* do.

So the strategic answer is not "make a nicer landing page". It is: **convert a tool into evidence, and put the evidence where a stranger can check it in twenty seconds.**

The current landing page does the opposite of this, and that is the single highest-value finding in the whole report.

---

# 2. Product review — what a recruiter actually sees today

All nine public surfaces were loaded in real Chromium at 1280×800 on 2026-09-29, with above-the-fold text extracted and screenshots captured. **FACT**, all of it.

| Page | HTTP | DOM load | Nav items | Words | Jargon terms | Console errors |
|---|---|---|---|---|---|---|
| `/` (**= Workbench**) | 200 | 673 ms | 8 | 157 | 0 | 0 |
| `/workbench` | 200 | 436 ms | 8 | 157 | 0 | 0 |
| `/triage` | 200 | 434 ms | 9 | 189 | 1 | 0 |
| `/usage` | 200 | 375 ms | 8 | 1,788 | 3 | 0 |
| `/dashboard` | 200 | 330 ms | 8 | 3,470 | **13** | 0 |
| `/ask-codebase` | 200 | 389 ms | 9 | 308 | 5 | 0 |
| `/standing-interview` | 200 | 347 ms | 9 | **69** | 0 | 0 |
| `/showcase/senior-java-ai-transformation` | 200 | 355 ms | 9 | 1,508 | 6 | 0 |
| customer app (separate host) | 200 | 251 ms | **0** | 41 | 0 | 0 |

**Everything is fast, everything is up, nothing throws errors.** The engineering is not the problem. The framing is.

### 2.1 The landing page problem, stated precisely

`agent/web_server.py:2264` — `Route("/", workbench_page)`. **FACT.**

What is above the fold at `/` today, verbatim from the rendered DOM:

> "Agentic Software Delivery — Workbench" · "Enter a real requirement. Small, low-risk changes are implemented, tested, and deployed automatically…" · TARGET APPLICATION · Application: Customer App · Environment: Production Demo · "This is the live demo application your requirement will modify." · OPEN CURRENT CUSTOMER APP · SEE A VERIFIED RUN · "1. What would you like to change?"

**There is no name on this page. No role. No location. No statement of what the person is good at.** A German HR recruiter who opens this link from a CV sees a dark-themed internal console asking them to submit a change request to a production demo. The page is well-built and it is addressed to someone who already knows what this is — which a recruiter, by definition, does not.

This is the worst possible use of the first ten seconds, and it is a routing decision, not a design flaw. Everything else in this report is secondary to fixing it.

### 2.2 Page-by-page recruiter-readiness

| Page | Recruiter-ready? | Assessment |
|---|---|---|
| **Role Showcase** | **Yes — the most ready thing on the site** | `h1`: *"Senior Java Backend + AI-Assisted Delivery Transformation — evidence-backed, not a technology badge list."* That headline already does the positioning job. Above the fold: START HERE, START THE LIVE DEMO, INTERVIEW WALKTHROUGH, then role categories. It is the closest existing asset to what the home page should be. Caveats: 1,508 words and 6 jargon terms (`embedding`, `idempot`, `MCP`, `ledger`, `eval`, `deterministic`). |
| **Ask the Codebase** | Yes, with trimming | `h1`: *"Ask the Codebase — real, cited retrieval, not a chat bot."* Excellent self-positioning against exactly the thing recruiters are tired of (§3, F7). 5 jargon terms. A strong secondary destination. |
| **Triage** | Yes | Good one-liner: *"Diagnose and repair a real, contained defect — reproduction, AI diagnosis, a real patch, real tests, and a human…"*. But three unexplained scenario variants (A/B/C) above the fold will confuse a non-technical reader. |
| **Workbench** | As a *destination*, yes. As a *landing*, no | It is an interactive tool. Interactive tools are excellent second clicks and terrible front doors. |
| **Usage** | Partly | 1,788 words. Genuine differentiator (real token/cost telemetry) but needs one plain sentence at the top saying why a recruiter should care. |
| **Dashboard** | **No** | 3,470 words and **13 jargon terms** — the densest page on the site. Deep-link territory, not a first or second click. |
| **Standing Interview** | **No, as it stands** | **69 words total.** Above the fold there is only navigation, an input box and "One question at a time. Typed answers only — no audio." No name, no context, no explanation of what it knows. Also: the SI audit committed today (`docs/audits/SI_AUDIT_2026-09-29.md`) found live defects — 39% of answered questions volunteer unsolicited negatives, one legitimate interview question refused 3/3. **It should not be the primary CTA until those land.** |
| **Customer app** | Functional, but **orphaned** | **Zero navigation links. FACT.** A recruiter who clicks through has no path back to the portfolio. Its login page is honest and well-written ("This is a public portfolio demo password, prefilled on purpose — edit it to see a real authentication failure"), which is a nice touch. |

### 2.3 Two navigation facts worth knowing before any home-page work

- **JD Match is in the public navigation on every page**, and `/learn` and `/jd-match` both return **200** to a direct URL. **FACT.** They are not private; they are merely not emphasised. The Owner has said both should become private.
- **The nav is inconsistent:** `/` and `/workbench` render 8 items, other pages render 9 (Learn is hidden on Workbench/Dashboard/Usage by an older rule). **FACT.** A recruiter moving between pages sees the menu change.

---

# 3. Market research — how recruiter behaviour changed

## 3.1 The volume and trust collapse

| # | Finding | Label | Source | Date |
|---|---|---|---|---|
| F1 | Recruiters are deliberately adding friction to applications; ~1 in 5 hiring managers added at least one extra screening step specifically because of AI-generated applications. | RECRUITER OPINION | [skillfuel.com](https://www.skillfuel.com/recruiters-friction-job-applications-ai-hiring/) | 2026 (month not stated) |
| F2 | Volume moved from dozens to "hundreds and hundreds" per posting. A recruiting platform is reported as saying recruiters know only ~30 of 1,000 applications are serious. Verification steps now include identity checks, skills testing, and a return to referral networks. Named trusted signals: direct skill measurement, real-time collaboration, job-relevant evidence over AI-polished CVs. | RECRUITER OPINION (reporting survey data) | [ptechpartners.com](https://www.ptechpartners.com/2026/09/09/ai-resumes-meet-ai-recruiters-dispatches-from-the-automated-hiring-cycle/) | **2026-09-09** |
| F3 | 76% of developers say AI makes technical assessments easier to fool; 78% say hiring assessments don't measure real work. | SURVEY (HackerRank 2025, cited secondhand) | via F2 | study 2025 |
| F4 | 67% of managers say AI résumés are actively slowing the hiring process. | SURVEY | [Forbes / Rachel Wells](https://www.forbes.com/sites/rachelwells/2026/03/18/ai-resumes-are-sabotaging-the-hiring-process-67-of-managers-reveal/) | 2026-03-18 |
| F5 | First-hand reporting on AI slop, impersonators and scams reaching real job postings. | RECRUITER OPINION (first-hand) | [The Markup](https://themarkup.org/hello-world/2026/01/24/we-posted-a-job-then-came-the-ai-slop-impersonator-and-recruiter-scam) | 2026-01-24 |
| F6 | 93% of recruiters plan to increase AI use in 2026; 60% say AI helps surface "hidden gem" candidates. | VENDOR CLAIM (LinkedIn executive, via CNBC) | [CNBC](https://www.cnbc.com/2026/01/11/ai-dominate-hiring-2026-linkedin-execs-top-tips-stand-out.html) | 2026-01-11 |

**Answering the brief's questions 1 and 2 directly.** Are recruiters spending less time on CVs? **The evidence does not actually say that.** What it says is that they are spending *more* effort per hire, redistributed away from the CV and toward verification (F1, F2). Are polished AI-generated CVs losing signalling value? **Yes — this is the best-supported claim in the whole report**, carried independently by F2, F4 and F5. That is a different and more useful conclusion than "recruiters skim faster".

## 3.2 What senior AI hiring now tests

| # | Finding | Label | Source | Date |
|---|---|---|---|---|
| F7 | Signal vs noise, explicitly separated. **Signal:** problem decomposition; **system boundaries — what the agent can and cannot do**; evaluation discipline with test cases and error analysis; production awareness (latency, cost, observability); communication of trade-offs. **Noise:** tool familiarity alone — *"tool knowledge on its own is weak signal now"* — polished output with no control mechanism, happy-path-only demos, generic AI-fluency claims. Demos should show *"one successful path and one controlled failure path."* Human-in-the-loop and observability called non-negotiable in production agentic systems. Also: *"A two-page project note plus a five-minute demo can carry more signal than a big site full of generic AI projects."* | RECRUITER OPINION (CPTO synthesis) | [provn.co](https://provn.co/blog/2026/06/agentic-engineer-hiring-requirements) | **2026-06-03** |
| F8 | Four portfolio signals in priority order: (1) a README that reads like a product spec, (2) an eval report with named metrics and numbers, (3) **a live deployment URL**, (4) cost and latency figures. Red flags: "just vibes" with no evals, no deploy, benchmark claims without numbers, copy-pasted demos. *"A live, clickable URL is one of the most-cited must-haves, because reviewers won't clone your repo."* | RECRUITER OPINION (practitioner) | [ai-engineering-field-guide](https://github.com/alexeygrigorev/ai-engineering-field-guide), [projects-to-land-an-ai-job](https://github.com/landedjobs/projects-to-land-an-ai-job), [slategit.com](https://slategit.com/blog/github-profile-for-ai-engineer-roles-2026) | 2026 |
| F9 | Eval literacy repeatedly named as the clearest discriminator between people who have shipped LLM systems and people who have not. | VENDOR CLAIM | [KORE1](https://www.kore1.com/agentic-ai-hiring-2026/), [HeroHunt](https://www.herohunt.ai/blog/how-to-recruit-ai-evals-engineers-2026/) | 2026 |
| F10 | *"Roughly 70% of AI engineering candidates now have at least one ChatGPT wrapper in their portfolio"*, making skill unassessable from the project alone. Hiring managers respond by reviewing **commit history and commit content**, and by looking for **evidence of independent judgment — decisions the candidate cannot explain unless they made them.** And: *"A senior engineer's hallmark is knowing what their system cannot do; one paragraph on failure modes, edge cases, or known retrieval gaps"* separates junior from principal-level. | VENDOR CLAIM (the 70% figure has no methodology) / RECRUITER OPINION (the rest) | [agenticcareers.co](https://agenticcareers.co/blog/ai-agent-portfolio-projects-get-hired-2026), [dev.to](https://dev.to/klement_gunndu/5-ai-portfolio-projects-that-actually-get-you-hired-in-2026-5bpl) | 2026 |
| F11 | Candidates presenting only successes read as not taking risks or not being honest. | RECRUITER OPINION | [HeroHunt](https://www.herohunt.ai/blog/emerging-skill-sets-ai-era-hiring-managers-guide-2026/) | 2026 |

**This answers brief questions 4, 5, 7, 8 and 9 in one move.** "Built with AI" is now assumed, not impressive (F7, F10). What is scarce is *judgement you can see*: boundaries, evals, failure modes, and decisions with reasons. The specific things that make a portfolio look like demo spam are named in F7 and F8 — happy-path demos, no deployment, numbers without a source, tool lists.

## 3.3 Real German job descriptions — the most direct evidence available

These are actual postings, read in this session. **FACT** as to their text.

**E.ON SE — Senior Agentic AI Platform Engineer (m/w/d), Essen. Last updated 2026-09-28** — one day before this report. [Listing](https://praktischkommune.de/jobs/82322539-senior-agentic-ai-platform-engineer-m-w-d-essen)

Requirements, verbatim fragments: *"LLM-Inference-Endpunkte, Agent-Gateways, Multi-Agent-Orchestrierung, Vektordatenbanken"* · *"LangGraph, AutoGen oder CrewAI"* · *"Monitoring, Logging und Alerting von Agent-Workflows"* including *"Observability für LLM-Calls, Tool-Invocations und Agent-Entscheidungspfade"* · *"sichere API-Anbindungen über Zugriffskontrolle und Prompt-Security bis zur Einhaltung unternehmensweiter KI-Richtlinien"* · *"skalierbar, zuverlässig und produktionsreif"* · assessing new LLM and agent technologies for *"Produktionsreife"*.

**Devoteam — Forward Deployed Engineer – Gen AI (m/w/d), München/Frankfurt, posted ~Aug 2026.** [Listing](https://www.dreamworkhq.com/job/02508eed-9c3f-4323-8776-82afee166a1c)

*"LangGraph, Google Agent Development Kit, LangChain, CrewAI"* · *"Vektordatenbanken"* · *"CI/CD, Testing, Deployment, Monitoring"* · build *"evaluation and monitoring solutions for LLM systems"* · desired: enterprise AI governance and security, **"Model Context Protocol Servern"**, LLM evaluation frameworks · **language: *"fließende Deutsch- und Englischkenntnisse"*** · €85K–€115K (aggregator estimate, not the employer's).

**Market volume:** jobvector lists 119 Agentic AI and 128 Generative AI postings in Germany. Other named hirers surfaced: Deloitte (Senior Consultant GenAI & Agentic AI), Advantest Europe (AI Engineer – RAG and Agentic AI, Böblingen). **FACT** as to listing counts on that date.

### What this means for Karthik specifically — the overlap is unusually good, with two named gaps

| What these German JDs ask for | Karthik's verified position |
|---|---|
| Agent gateways | ✅ `reasoning_gateway.py` — single model boundary, purpose allowlist, zero-LLM kill switch (`PRODUCTION_VERIFIED`) |
| Multi-agent orchestration / LangGraph | ✅ LangGraph durable workflow with Postgres checkpoints (`PRODUCTION_VERIFIED`); **named by both JDs** |
| Observability for LLM calls, tool invocations, agent decision paths | ✅ Event ledger, write-through, real token counts (`PRODUCTION_VERIFIED`) |
| Access control, prompt security, enterprise AI policy compliance | ✅ Hash-bound write boundary, approve/reject absent from the tool schema (`PRODUCTION_VERIFIED`) |
| Evaluation / monitoring solutions for LLM systems | ✅ Labelled eval sets blocking CI — retrieval (12 cases), routing (14 cases), agent-decision |
| MCP servers (*desired* at Devoteam) | ✅ `agent/mcp_server.py` with tests |
| CI/CD, testing, deployment, monitoring | ⚠️ Partial — CI and testing are strong; **deployment is manual** |
| **Vektordatenbanken** — named by **both** JDs | ❌ **Absent.** Retrieval is plain cosine over small corpora. This is the single most common requirement he cannot claim |
| Azure / AWS / GCP platform depth | ⚠️ Partial — AWS Lambda hands-on at NRG; not platform-engineering depth |
| **Fluent German** (Devoteam; many Mittelstand/consultancy roles) | ❌ **English only.** A hard filter on a meaningful share of the market |

**INFERENCE (mine):** the home page should lead with the five green rows, because they are precisely the words in the JDs and precisely the things most candidates cannot show. The vector-database gap should be stated rather than hidden — F7, F10 and F11 all say the admission is worth more than the omission, and an interviewer will find it in thirty seconds anyway.

## 3.4 German / DACH specifics

| # | Finding | Label | Source | Date |
|---|---|---|---|---|
| F12 | German employers use AI to *assist*, not decide: automated CV screening 31%, semantic matching 17%, **automated ranking 12% — and 60%+ call it "unreliable for independent decisions."** Barriers: GDPR 68%, lack of expertise 54%, EU AI Act uncertainty 41%. Only 11% deploy AI specifically in recruiting. | **SURVEY** (Bitkom New Work 2025; Haufe Recruiting Trends 2025; LinkedIn Talent Insights DACH 2025) | via [yena.ai](https://www.yena.ai/de/blog/ki-im-recruiting-studie-dach-2026) | analysis 2026-03-21, **studies 2025** |
| F13 | 83% of German-speaking young candidates use AI to optimise application materials. Only 33% trust official corporate communications; 51% trust student/alumni voices. | **SURVEY** — Karriere-Barometer 2026 (Job Teaser / EDHEC / Kantar), n=1,133, fielded Aug–Oct 2025 | [Personalwirtschaft](https://www.personalwirtschaft.de/news/recruiting/recruiting-2026-warum-junge-bewerber-den-prozess-abbrechen-201026/) | 2026-02-26 |
| F14 | Skills-first framing in DACH: capabilities weighted over formal qualifications; recruiters search for skills rather than whole dossiers. ATS-optimised CV with JD keywords described as crucial. | RECRUITER OPINION | [karriere.at](https://www.karriere.at/c/a/arbeitstrends-2026), [jobcrawl.de](https://jobcrawl.de/ratgeber/bewerbungstrends-2026) | 2026 |
| F15 | Berlin tech works in English by default; 59% of German tech startups require no German, 54% use English as official company language. Munich skews larger, more German-speaking, more traditional. | **SURVEY** (Bitkom Startup Report **2023** — older, labelled) + opinion | [migaku](https://migaku.com/blog/language-fun/how-to-find-english-speaking-jobs-in-berlins-tech-scene), [tribexyz](https://www.tribexyz.com/blog/tech-hiring-germany-2026) | 2026 article / 2023 study |

**Important caveat on F13:** the sample is students and recent graduates aged 18–30. That is **not** Karthik's segment, and no equivalent German survey of senior/lead hiring was found. The only figure I would carry across is the 83% AI-usage rate, which corroborates the global flood finding.

**On German cultural expectations (brief question 18).** Searches for understatement vs self-promotion, truthfulness norms and professional seriousness in German hiring returned **nothing citable**. I am therefore **not** making a claim about German cultural communication style, and no option below is justified by one. What *is* evidenced: F12 shows DACH employers distrust automated judgement and keep a human in the loop — so **a human is probably reading the page**, which argues for prose a person can read rather than keyword density. Data-protection sensitivity is evidenced indirectly (GDPR named as the top barrier at 68%, F12), which supports a page with no trackers.

**Language (brief question 18).** English is correct for Berlin product/startup engineering (F15) and for Karthik's stated situation. But Devoteam's *"fließende Deutsch- und Englischkenntnisse"* is real and common in consultancy and Mittelstand. **INFERENCE:** the page should state the language position plainly and early rather than let a recruiter discover it at screening-call stage.

## 3.5 Does a live portfolio help in German senior hiring? (brief question 6)

**Honest answer: no direct evidence was found either way.** I found no German-specific study on whether portfolio sites influence senior engineering hiring outcomes. What I have is (a) global evidence that a live URL is the most-cited must-have for AI roles (F8), (b) German evidence that a human makes the decision (F12), and (c) the fact that Karthik will be *sending the link himself on a CV* — which sidesteps the discovery question entirely. The relevant question is not "will they find it" but "when they click it, what happens in the first twenty seconds".

---

# 4. The five homepage concepts

Five, not four — the fifth emerged from the JD evidence in §3.3 and is materially different.

---

## OPTION A — The Recruiter Proof Page

**1. Core idea.** A one-screen brief: who he is, what he is good at, three checkable proofs, one click deeper. Optimised for the reader who has thirty seconds and no technical vocabulary.

**2. Above the fold.** Name · one-line positioning · Berlin / English / open to Senior-Lead IC · three proof blocks each ending in a link to a running system · two buttons.

**3. Information hierarchy.** Identity → positioning → proof → depth → contact. Person first, then evidence, then system.

**4. Primary CTA.** *"See a verified run"* → Workbench's already-completed run view.
**5. Secondary CTAs.** Role Showcase · GitHub · CV · the Java app.
**6. Links to.** Workbench (verified-run view), Role Showcase, Ask the Codebase, customer app, GitHub.
**7. Do NOT show initially.** Dashboard, Usage, Triage scenario variants, any eval metric deeper than one line, LangGraph/MCP/ledger vocabulary.

**8. Why HR understands it.** It is a person with a job title and a location, in plain sentences.
**9. Why a technical recruiter cares.** Three concrete capability claims that map to JD keywords, each with a link.
**10. Why a senior AI interviewer cares.** They mostly won't linger — they will click through to GitHub within seconds. That is acceptable; the page's job is to route them fast.

**11. Risks.** Thin for architect-level screening; the least memorable option; risks reading as marketing if any bullet lacks a link.
**12. AI-generated risk: moderate.** A short claims-plus-buttons page is exactly the shape of a generated portfolio. Mitigated only by every claim being clickable.
**13. German fit: good.** Sober, factual, no hype.
**14. Fit for Karthik: good but under-uses him.** His differentiator is depth; this page shows breadth.
**15. Communicates:** backend ✅ · enterprise ⚠️ (employer names only) · AI ✅ · production ✅ · seniority ⚠️ · honesty ✅
**16. Blocks.** Header · 3 proof blocks · CTA row · stack + employers · honesty box · footer.
**17. Headline.** "I build backend systems, and the agentic AI that ships them."
**18. Subheadline.** "Berlin. Java and Spring backend engineering, currently at NRG Energy on multi-million-customer retail energy systems. The delivery platform serving this page is one I built and operate."
**19. CTA wording.** "See a verified run →" / "Ask my Standing Interview"

---

## OPTION B — Live Agentic System First

**1. Core idea.** Keep something live and interactive above the fold, but frame it. A compact hero explains who he is in two lines, then an embedded *completed* agent run — requirement in, investigation, approval gate, commit, tests, production verification — shown as a replay the visitor can step through without submitting anything.

**2. Above the fold.** Two-line identity · the run replay with its stages visible · a caption naming the approval gate.
**3. Hierarchy.** Identity (minimal) → the system working → what the system guarantees → who built it.
**4. Primary CTA.** *"Step through a real run"*.
**5. Secondary.** "Submit your own change" (Workbench) · Role Showcase · GitHub.
**6. Links to.** Workbench, customer app, Usage, GitHub.
**7. Do NOT show initially.** The live input box (that is the current mistake), Dashboard, corpus/eval vocabulary.

**8. Why HR understands it.** A visible sequence of steps with plain labels is legible even to someone who cannot read the code.
**9. Why a technical recruiter cares.** It is the thing JDs describe — an agentic workflow with an approval step — running.
**10. Why a senior AI interviewer cares.** Most of all. F7's "one successful path and one controlled failure path" is directly expressible here, and the approval gate is the judgement signal.

**11. Risks.** Highest execution risk. If the replay is slow, breaks, or needs explaining, the first impression is a broken demo. Requires new build, not just new copy.
**12. AI-generated risk: low** — a working multi-stage system is the hardest thing on this list to fake.
**13. German fit: moderate.** Show-don't-tell is good; a moving demo above the fold can read as flashy to a conservative reviewer.
**14. Fit for Karthik: strong on substance, weak on timing** — he is applying today and this is the slowest to build.
**15. Communicates:** backend ⚠️ · enterprise ⚠️ · AI ✅✅ · production ✅✅ · seniority ✅ · honesty ⚠️ (needs an explicit limits line)
**16. Blocks.** Two-line hero · run replay · "what the gate guarantees" · stack strip · footer.
**17. Headline.** "Watch an AI agent ship a change — and watch where it has to stop."
**18. Subheadline.** "A real run: requirement, investigation, a human approval bound by hash to the exact change, commit, tests, production verification."
**19. CTA wording.** "Step through the run →"

---

## OPTION C — Senior Engineer + AI Transformation Story

**1. Core idea.** Narrative. An experienced enterprise backend engineer explains what he did when coding agents arrived: he built the control system he would want in production — approval boundaries, durability, evaluation — and here is the evidence. Positions the AI work as the *continuation* of fifteen enterprise years, not a pivot away from them.

**2. Above the fold.** Name and role · a three-sentence story · one figure strip (crash drill 22/22 · survived a real container restart · zero duplicate writes) · one CTA.
**3. Hierarchy.** Person → why they built it → what it proves → evidence.
**4. Primary CTA.** *"Read how it survives a crash"* → deep technical case study.
**5. Secondary.** Role Showcase · the Java app · GitHub.
**6. Links to.** Role Showcase, customer app, GitHub, Workbench.
**7. Do NOT show initially.** Metric tables, nav to Dashboard/Usage, any tool list.

**8. Why HR understands it.** It is a career story with a clear before and after — the most familiar possible format.
**9. Why a technical recruiter cares.** It names enterprise credibility and AI credibility in one sentence, which is exactly the two-sided req they are filling.
**10. Why a senior AI interviewer cares.** Narrative reveals judgement, and F10 says judgement you can see is the discriminator.

**11. Risks.** Story pages age into self-promotion quickly. Requires genuinely good writing or it reads as a LinkedIn post. Slowest of the five to *read*.
**12. AI-generated risk: highest of the five.** Career-narrative prose is the single most generated text form on the internet in 2026. It only survives if it carries specifics no model would invent — which here means real defect names, real drill numbers.
**13. German fit: moderate-to-good** if it stays factual; poor if it becomes a hero story.
**14. Fit for Karthik: excellent on substance.** It is the only option that explains why an enterprise Java engineer is credible in agentic AI, which is his actual positioning problem.
**15. Communicates:** backend ✅✅ · enterprise ✅✅ · AI ✅ · production ✅ · seniority ✅✅ · honesty ✅
**16. Blocks.** Hero + story · figure strip · "what I built and why" · evidence links · limits · employers · footer.
**17. Headline.** "Fifteen years of enterprise backend. Then coding agents arrived, so I built the controls I'd want in production."
**18. Subheadline.** "Approval bound by hash to the exact change. A workflow that survives the machine dying mid-run. Evaluation that blocks the build. All running, all linked."
**19. CTA wording.** "Read how it survives a crash →"

*(Note: the "fifteen years" figure is unverified — see §7, Owner decision 3.)*

---

## OPTION D — Capability Evidence Dashboard (the Proof Wall)

**1. Core idea.** Every claim is a row: capability · verification level · link to the running thing. Followed by a short, deliberate **"Not built here"** section. Rendered from `docs/PORTFOLIO_CAPABILITIES.yaml` so it cannot drift.

**2. Above the fold.** One identity line · one framing line ("every claim links to the running thing") · the first six LIVE rows.
**3. Hierarchy.** Framing → evidence → boundaries → person.
**4. Primary CTA.** Any proof link — the table *is* the navigation.
**5. Secondary.** Standing Interview · Role Showcase · GitHub · CV.
**6. Links to.** Workbench, Ask the Codebase, Usage, customer app, GitHub source files, Role Showcase.
**7. Do NOT show initially.** Dashboard, Triage variants, the Standing Interview as primary CTA (until its fixes land).

**8. Why HR understands it.** Colour-coded status is scannable without technical vocabulary — but the rows themselves are technical, which is this option's weak point.
**9. Why a technical recruiter cares.** It maps one-to-one onto a requirements list. This is the fastest page in the set for "does he have X?".
**10. Why a senior AI interviewer cares.** F7's "system boundaries" and F10's "knowing what your system cannot do" rendered as page structure. The NOT-BUILT rows are the strongest seniority signal available.

**11. Risks.** A skimming HR reader may register the grey rows as gaps. Dense. Only credible if generated from the registry.
**12. AI-generated risk: lowest of the five.** It is structurally an anti-overclaim artifact.
**13. German fit: very good.** Factual, verifiable, no salesmanship; aligns with the data-honesty instinct behind F12's GDPR caution.
**14. Fit for Karthik: very good** — the registry already exists with 22 entries, verification levels and 45 validated evidence links.
**15. Communicates:** backend ✅ · enterprise ⚠️ · AI ✅✅ · production ✅✅ · seniority ✅✅ · honesty ✅✅✅
**16. Blocks.** Identity line · framing · LIVE rows · PARTIAL rows · NOT-BUILT rows · why-I-publish-absences note · CTA · employers · footer.
**17. Headline.** "Every claim on this page links to the running system."
**18. Subheadline.** "Backend engineering in Java and Spring, currently at NRG Energy. Separately, I build and operate the agentic delivery platform described below — including the three things it deliberately does not do."
**19. CTA wording.** "Open the running system →"

---

## OPTION E — The Requirements Mirror *(invented from the German JD evidence, §3.3)*

**1. Core idea.** German agentic-AI JDs use a remarkably consistent vocabulary — agent gateways, multi-agent orchestration, LangGraph, observability for LLM calls and tool invocations, access control and prompt security, production-readiness, evaluation, vector databases. **The home page mirrors that vocabulary back, row by row, with a link and an honest status against each.** It is a self-assessment against the market's own job description, including the requirements he does not meet.

**2. Above the fold.** One identity line · "Here is what German agentic-AI roles are asking for in 2026, and exactly where I stand on each" · the first five rows with ✅ / ⚠️ / ❌ and a link.

**3. Hierarchy.** The market's requirements → his status on each → proof → person.
**4. Primary CTA.** *"Open the agent gateway"* (or whichever row the reader is hiring for).
**5. Secondary.** Role Showcase · GitHub · CV · Standing Interview.
**6. Links to.** GitHub source per row, Workbench, Usage, Ask the Codebase, customer app.
**7. Do NOT show initially.** The Java/enterprise background — it belongs immediately below the fold, not above it.

**8. Why HR understands it.** They are holding the JD. The page is laid out in the JD's own words, so matching is mechanical rather than interpretive.
**9. Why a technical recruiter cares.** It does their screening for them, and it is falsifiable — which makes it credible rather than presumptuous.
**10. Why a senior AI interviewer cares.** Three ❌ rows stated voluntarily is a stronger seniority signal than twenty ✅ rows. It also pre-frames the interview around what he *did* build.

**11. Risks.** The biggest: it can read as presumptuous — "I have graded myself against your job ad". Tone has to be scrupulously neutral. It also dates faster than any other option, because it tracks a moving market. And ❌ rows above the fold is a real risk if a recruiter reads only the first screen.
**12. AI-generated risk: very low.** Nobody generates a page that lists their own gaps against live job postings.
**13. German fit: strong, with one caveat.** Directness and verifiability fit well; the self-grading framing must not tip into cleverness.
**14. Fit for Karthik: the best strategic fit of the five.** His overlap with real German JDs is genuinely unusual (§3.3) and invisible on the current site. His two gaps — vector databases, German language — are ones he cannot hide anyway.
**15. Communicates:** backend ⚠️ (below fold) · enterprise ⚠️ · AI ✅✅✅ · production ✅✅ · seniority ✅✅✅ · honesty ✅✅✅
**16. Blocks.** Identity line · framing · requirement rows with status+link · "what I can't claim" · enterprise background · employers · footer.
**17. Headline.** "What German agentic-AI roles are asking for in 2026 — and where I actually stand."
**18. Subheadline.** "Taken from live job descriptions at E.ON, Deloitte and Devoteam. Green links to a running system. Red means I haven't built it."
**19. CTA wording.** "Open the running system →" per row.

---

# 5. Comparison matrix

1–10; higher is better. For the two risk rows, **higher = lower risk** (i.e. 10 = safest), so that the totals are directionally meaningful.

| Criterion | A · Proof Page | B · Live System | C · Story | D · Evidence Dashboard | E · Requirements Mirror |
|---|:--:|:--:|:--:|:--:|:--:|
| HR first impression | **9** | 6 | 8 | 5 | 7 |
| Technical recruiter first impression | 7 | 8 | 6 | **9** | **9** |
| AI interviewer credibility | 5 | **9** | 7 | **9** | **9** |
| German-market fit | 8 | 6 | 7 | **9** | 8 |
| Clarity in the first 10 seconds | **9** | 6 | 7 | 6 | 7 |
| Differentiation from AI-generated portfolios | 5 | 8 | 4 | **9** | **10** |
| Evidence strength | 6 | 8 | 6 | **10** | 9 |
| Technical depth | 4 | 8 | 7 | 9 | **9** |
| Low risk of overwhelming non-technical recruiters | **9** | 6 | 8 | 4 | 5 |
| Low risk of looking like a toy/demo | 8 | 4 | 7 | **9** | **9** |
| Maintainability as the system grows | 8 | 5 | **9** | 7 (auto-generated) | 4 (tracks a moving market) |
| **Total (max 110)** | **78** | **74** | **76** | **86** | **86** |

D and E tie at 86 on very different profiles: **D is safer and self-maintaining; E is sharper and decays faster.** A leads on the two HR-facing rows, which is why it appears in the recommendation as a component rather than being discarded.

---

# 6. Final analysis

## 6.1 BEST DEFAULT HOMEPAGE

**Option D — Capability Evidence Dashboard, opened by Option A's identity block.**

Concretely: the first 250px is A's header (name, one-line positioning, Berlin / English / Senior-Lead IC, currently at NRG Energy). Immediately below it, D's evidence rows. Below those, the "Not built here" section. Below that, the enterprise background and employers.

**Five reasons:**
1. **It is built on the one thing that did not get commoditised.** F2, F4 and F5 all converge: polished claims stopped carrying information. D's entire structure is "claim → verification level → link", which is the format of the thing that still does.
2. **It matches what senior AI hiring actually tests.** F7 names system boundaries, evaluation discipline and production awareness as the signal. D shows all three above the fold, and its NOT-BUILT section is F10's "knowing what your system cannot do" made into page furniture.
3. **The registry already exists.** 22 entries with verification levels and 45 validated evidence links. Generating the page from `PORTFOLIO_CAPABILITIES.yaml` means the wall cannot drift — and a drifted proof wall would be worse than none.
4. **It fits the German evidence better than the alternatives.** F12 shows a human making the decision under GDPR caution and distrust of automated judgement. A factual, checkable, tracker-free page suits that reader.
5. **A's header fixes D's one real weakness.** Standalone, D scores 5/10 on HR first impression and 4/10 on overwhelming a non-technical reader. Those are its only sub-6 scores, and a plain identity block above the table removes both.

## 6.2 BEST ALTERNATIVE

**Option E — The Requirements Mirror.** Same score, higher ceiling, higher variance.

Take it if Karthik is applying mainly to roles matching the E.ON/Devoteam profile, where his overlap is genuinely unusual and currently invisible. Its three risks are real and should be respected: it can read as presumptuous, it dates fast, and ❌ rows above the fold could cost him an HR screener who reads only the first screen. **INFERENCE (mine):** the safest form of E is not as the home page but as a *second* page linked from D — "How I map to a typical German agentic-AI job description" — which keeps D's safe front door and E's sharp argument.

## 6.3 WHAT SHOULD REMAIN BELOW THE FOLD

- Enterprise employment history and employer names (NRG Energy, BCBSA, Marsh — see Owner decision 2 on Northern Trust).
- The full stack list — Java 21, Spring Boot, Postgres, Kafka at BCBSA, Redis, AWS, REST/GraphQL, Spring Security.
- PARTIAL-status capabilities (outbox, JWKS, aggregator fan-out).
- The "Not built here" list — **below the fold, not hidden.** Above the fold it costs an HR skim; below it, it converts a technical reader.
- Eval metrics beyond a single headline number.
- Links to Dashboard and Usage.
- Any mention of LangGraph, MCP, checkpointers, ledgers, corpora, cosine, idempotency — one click down, never on the first screen.

## 6.4 WHAT SHOULD MOVE OUT OF PUBLIC NAVIGATION

| Item | Action | Why |
|---|---|---|
| **JD Match** | Remove from nav **and** make unreachable | Owner decision already taken. It is currently in the nav on every page and returns 200. **FACT.** |
| **Learn** | Same | Owner decision. Returns 200. A learning wiki on a senior portfolio invites the "tutorialware" read (F8, F10). |
| **Dashboard** | Remove from primary nav; keep as a deep link | 3,470 words, 13 jargon terms — the densest surface on the site. **FACT.** |
| **Workbench** | Keep in nav, **remove from `/`** | It is a good destination and a bad front door. |
| **Standing Interview** | Keep, but **not as primary CTA** until the audit fixes land | Today's audit found 39% of answered questions volunteer unsolicited negatives and one legitimate question refused 3/3. |
| **Customer app** | Add a link back to the portfolio | **Zero nav links today. FACT.** A recruiter who clicks in is stranded. |
| Nav inconsistency (8 vs 9 items) | Fix in the same change | The menu currently changes between pages. **FACT.** |

## 6.5 WHAT SHOULD NEVER BE CLAIMED

Verified as false, absent, or unverifiable in this repository:

- **A managed vector database, hybrid search, or reranking.** Retrieval is plain cosine over small corpora. Both German JDs ask for vector databases; the honest answer is a scope explanation, never a claim.
- **A second LLM provider, routing, or failover.** One provider behind one gateway.
- **LLM-as-judge evaluation.** Not built.
- **Automated deployment / CD with production verification.** Deploys are scripted but **manually triggered**.
- **Spring AI.** Not used.
- **Employer production scale for the portfolio platform.** It is his own system; the traffic is his. This distinction must be explicit, not implied.
- **Kafka at NRG.** Kafka is BCBSA, hands-on, application-side. The repo's own `kafka-outbox` is this platform's, `TESTED`, not production — it must never sit near an NRG sentence.
- **"I designed the NRG / BCBSA architecture."**
- **Any customer-count metric as a personal achievement.** NRG is "multi-million-customer retail energy systems" — the system's scale, not his metric.
- **The Standing Interview's "15/15 acceptance gate".** The registry records it; today's audit found that gate has no quality oracle and passes answers the Owner rejects.
- **Years of experience** — until confirmed. No figure exists in the Owner's verified inputs (Owner decision 3).
- **Any platform-age claim** that contradicts git: first commit **2026-09-08**, 534 commits. "A year of building this" would be false. **FACT.**

## 6.6 WHAT THE HOME PAGE SHOULD LINK TO FOR DEEP TECHNICAL PROOF

In descending order of what a senior interviewer will actually open:

1. **GitHub source files, deep-linked per claim** — `write_tools.py` (the write boundary), `durable_workflow.py`, `workflow_drill.py` (the crash drill), `reasoning_gateway.py`, `eval_runner.py`. F8 ranks "a README that reads like a product spec" first, but the file that proves the claim beats the repo root.
2. **`docs/audits/SI_AUDIT_2026-09-29.md`** — a self-audit that found real defects in his own system, committed next to the code it criticises. Against F10's "independent judgment" and F11's "only successes reads as dishonest", this may be the single most differentiating artifact on the whole site.
3. **Role Showcase** — already the most recruiter-ready page.
4. **A verified Workbench run** (the completed-run view, not the input form).
5. **Ask the Codebase** — live retrieval with citations; good self-positioning already.
6. **Usage** — real token/cost telemetry, matching the JDs' observability language.
7. **The customer app** — the Java 21 / Spring artifact, once it has a link back.

---

# 7. "Twenty to thirty seconds. What must they understand before they leave?"

Six things, in this order. If the page delivers these six, it has done its job; anything else is a bonus.

1. **Who.** Karthikeyan Devadoss, Berlin, works in English, available for Senior / Lead / Architect IC roles.
2. **What kind of engineer.** An enterprise Java and Spring backend engineer — currently at NRG Energy, on multi-million-customer retail energy systems — *not* a data scientist and *not* a researcher.
3. **The one-sentence differentiator.** He builds agentic AI systems with the controls that make them safe to run: a human approval the model cannot bypass, a workflow that survives a crash, and evaluation that blocks the build.
4. **That it is real and they can check it.** Something on that first screen is a link to a running system, and they register that they *could* click it — whether or not they do.
5. **That he is honest about the edges.** They should catch a glimpse that this page also says what he has not built. This is what separates him from the polished-portfolio pile (F7, F10, F11).
6. **Where to go next**, matched to who they are: HR → the CV; technical recruiter → the capability list; hiring manager → GitHub or the crash-drill story.

**What they must NOT conclude in those thirty seconds** — each of which the current landing page actively risks:
- "This is an internal tool, I'm in the wrong place." ← what `/` produces today
- "Java developer who recently discovered ChatGPT."
- "AI researcher."
- "Another AI-generated portfolio."
- "Impressive but I have no idea what he actually does."

---

# 8. Research limitations — stated plainly

1. **No Reddit, LinkedIn, X, StepStone, Xing or Kununu source was reachable.** The search tool is US-indexed and returned SEO and aggregator content for every community query. **Nothing in this report is attributed to those platforms**, and no community anecdote appears. The brief asked for them specifically; this is the largest gap, and it would need a manual pass or different tooling.
2. **Post-2026-09-01 evidence remains thin even with the window opened to June.** The genuinely dated, substantive sources are: a real E.ON job posting updated **2026-09-28**, an industry article from **2026-09-09**, the Provn analysis from **2026-06-03**, Forbes **2026-03-18**, Personalwirtschaft **2026-02-26**, The Markup **2026-01-24**, CNBC **2026-01-11**. Everything else is undated 2026 content.
3. **The German survey data is second-hand and its underlying studies are 2025** (Bitkom, Haufe, LinkedIn Talent Insights via a 2026-03-21 analysis). The primary PDFs were not retrieved.
4. **The one clean German survey found (Karriere-Barometer 2026, n=1,133) samples 18–30-year-old students and graduates** — the wrong population for a senior hire, and labelled as such wherever used.
5. **No evidence on German cultural communication norms in hiring was found.** No claim about understatement, modesty or self-promotion is made anywhere in this report.
6. **No German-specific evidence on whether portfolio sites influence senior hiring outcomes** was found, in either direction.
7. **Several widely-repeated figures were excluded for lack of methodology:** the "6-second scan" family, "80% more engagement with runnable code", "68% of views are mobile", and a "1,000 applicants per role" figure attributed to WIRED that did not resolve to a locatable article.
8. **The "~70% of candidates have a ChatGPT wrapper" figure (F10) is a vendor claim with no methodology** and should not be repeated as fact.
9. **Salary figures seen on aggregators are aggregator estimates**, not employer statements.
10. **Only two full German JDs were read end-to-end.** Two postings are an illustration, not a market sample.

---

# 9. Open Owner decisions

| # | Decision |
|---|---|
| 1 | **Which option** — the recommended D+A hybrid, or E as the front door instead of as a second page? |
| 2 | **Employer list.** This brief names NRG Energy, BCBSA and Marsh. The brief two days ago also included **Northern Trust**. Which is correct for public display? |
| 3 | **Years of experience.** No figure exists in any verified input. State it, or deliberately omit it? Option C's headline currently depends on it. |
| 4 | **Platform age.** First commit is 2026-09-08 — three weeks, 534 commits. Say nothing, or state it truthfully as recent and fast? The git history is public, so whatever is said must match it. |
| 5 | **Publish the "Not built here" list?** It is the strongest differentiator in the research and the one element that states limitations publicly. Needs an explicit yes. |
| 6 | **Language position.** State "English, German at [level]" on the first screen? Devoteam-class roles require fluent German; being upfront saves everyone a screening call. |
| 7 | **Standing Interview as a CTA** — hold it back until the audit fixes (`BL-142`–`BL-144`, `BL-147`) land? |
| 8 | **Make `/learn` and `/jd-match` genuinely unreachable** before or with the home page? Both return 200 today. |
| 9 | **CV file and LinkedIn URL** — neither exists as an artifact in this repository. |
| 10 | **Does `/` become the new page, or a new path with `/` redirecting?** The latter is reversible in one line. |

---

---

# SUMMARY

## LATEST HIRING SIGNALS
- Application volume exploded; ~1 in 5 hiring managers added a screening step specifically because of AI-generated applications *(RECRUITER OPINION, 2026)*. 67% of managers say AI résumés slow hiring *(SURVEY, Forbes, 2026-03-18)*.
- Weight moved from the CV to **verification** — identity checks, skills testing, commit-history review, referrals *(RECRUITER OPINION, 2026-09-09)*.
- For AI roles, four signals in order: a spec-quality README, **an eval report with real numbers**, **a live deployment URL**, cost and latency figures *(RECRUITER OPINION, 2026)*.
- Real German JDs (E.ON, updated **2026-09-28**; Devoteam) ask by name for agent gateways, multi-agent orchestration, **LangGraph**, observability for LLM calls and tool invocations, access control and prompt security, production-readiness, LLM evaluation, **MCP servers** — and **vector databases** *(FACT)*.
- In DACH, AI assists but does not decide: automated ranking 12% adoption, 60%+ call it unreliable; GDPR is the top barrier at 68% *(SURVEY, 2025 studies via 2026 analysis)*. **A human is reading the page.**

## WHAT RECRUITERS NOW DISTRUST
- Polished claims with nothing clickable underneath.
- Tool and framework lists — *"tool knowledge on its own is weak signal now"* *(RECRUITER OPINION, 2026-06-03)*.
- Happy-path demos with no failure path, no deployment, and benchmark numbers with no source.
- Another RAG chatbot — a vendor claim puts ~70% of AI candidates as having one *(VENDOR CLAIM, unverified)*.
- Portfolios showing only successes — read as not taking risks or not being straight.
- Learning wikis and tutorial content presented as credentials.

## WHAT CREATES CREDIBILITY IN 2026
- A **live URL** a stranger can click — *"reviewers won't clone your repo."*
- **Real evaluation numbers** from a real labelled set, re-run automatically.
- **Boundaries stated explicitly** — what the system can and cannot do.
- **A controlled failure path**, not only a success path.
- **Decisions with reasons** the candidate could not explain unless they made them.
- **Published limitations** — the rarest signal available, and the cheapest for Karthik to give.

## 4+ HOMEPAGE OPTIONS
**A · Recruiter Proof Page** (78/110) — safest, clearest, thinnest.
**B · Live Agentic System First** (74/110) — strongest demo, highest execution risk, slowest to build.
**C · Senior Engineer + AI Transformation Story** (76/110) — best explains the pivot; highest risk of reading as AI-generated prose.
**D · Capability Evidence Dashboard** (86/110) — claim → verification level → link, plus a "Not built here" section; generated from the existing registry.
**E · The Requirements Mirror** (86/110) — mirrors real German JD vocabulary back with honest ✅/⚠️/❌ status per row; sharpest and fastest-decaying.

## RECOMMENDED DIRECTION
**Option D, opened by Option A's identity block.** Plain header (name, positioning, Berlin, English, current role) in the first 250px; evidence rows immediately below; "Not built here" below those; enterprise background and employers below that. **Option E becomes a second page** linked from D, not the front door. **Option C's case study** becomes the deep link behind the durable-workflow row.

## TOP 5 REASONS
1. Polish stopped carrying information; "claim → verification level → link" is the format that still does.
2. It shows what senior AI hiring actually tests — boundaries, evaluation, production awareness — above the fold.
3. The capability registry already exists (22 entries, verification levels, 45 validated links), so the page can be generated and cannot drift.
4. It fits the German evidence: a human decides, under GDPR caution and distrust of automated judgement.
5. A's header removes D's only two weak scores (HR first impression 5/10, overwhelming non-technical readers 4/10).

## OPEN OWNER DECISIONS
1. D+A hybrid, or E as the front door? · 2. Is Northern Trust part of the public employer list? · 3. Years of experience — state or omit? · 4. How to describe the platform's age (first commit 2026-09-08, 534 commits)? · 5. Approve publishing the "Not built here" list? · 6. State the German-language position on the first screen? · 7. Hold the Standing Interview back as a CTA until its fixes land? · 8. Make `/learn` and `/jd-match` genuinely unreachable first? · 9. CV file and LinkedIn URL — neither exists yet. · 10. Replace `/` directly, or use a new path with a redirect?

**Nothing was implemented, changed or committed. Awaiting your direction.**
