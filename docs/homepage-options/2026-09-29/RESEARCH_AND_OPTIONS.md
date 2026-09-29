# New public home page — market research and four options

**Date:** 2026-09-29 · **Repository:** `karthikdevadoss/agentic-software-delivery` @ `f5155e4`
**Status:** Research and mockups only. Nothing deployed. No existing page, route, navigation entry, prompt, test or registry file was changed.
**Mockups:** `index.html` in this folder links to all four. Each is a standalone static file, served by nothing.
**Browser verification:** 68 of 68 checks passed in real Chromium at 1280×900 and 390×844. Screenshots in `screenshots/`.

---

## Executive summary, in plain English

Hiring changed in a specific way in 2026, and it changed in Karthik's favour — but only if the page is built for it.

Employers are drowning. Application volumes exploded because candidates now generate applications with AI, and the things recruiters used to read as effort — a tailored CV, a polished cover letter, a neat portfolio — stopped being evidence of anything, because software produces them in seconds. One recruiting platform put it bluntly: recruiters know that only about thirty of a thousand applications are serious. The response has been to **add friction and demand proof**: more screening steps, skills assessments over CV screening, and a general shift from "what does this person claim" to "what can I check".

That is the whole opportunity. Karthik has something almost no applicant has: **systems a stranger can click on and verify in thirty seconds**, plus a public repository holding the code behind them. The job of the home page is not to impress. It is to be *checkable*, fast, and honest about its own edges — because in a market full of unverifiable polish, the thing that stands out is a claim with a link under it and a short list of things the candidate says he has *not* built.

### The ten findings that shaped these options

1. **Application volume exploded and screening tightened.** Roughly one in five hiring managers added at least one extra screening step specifically because of AI-generated applications. *(OPINION/industry reporting, global, 2026)*
2. **Skills-based hiring displaced CV screening.** Proof of ability now outranks a claim of ability for most roles. *(OPINION/industry, global, 2026)*
3. **The first scan is six to eight seconds; the whole first-pass decision is about a minute.** The opening statement and the first visible proof carry almost all the weight. *(OPINION/practitioner, global, undated–2026)*
4. **For AI roles specifically, four signals dominate, in order:** a README that reads like a product spec, an eval report with named metrics and numbers, a live deployment URL, and cost/latency figures. *(OPINION/practitioner, global, 2026)*
5. **The matching red flags are "just vibes" with no evals, no deployment, benchmark claims without numbers, and copy-paste demos.** *(same source)*
6. **"Reviewers won't clone your repo."** A live, clickable URL is repeatedly named as the single must-have. *(OPINION/practitioner, global, 2026)*
7. **Honesty about limits is now a trust signal, not a weakness.** Candidates presenting only successes read as either not taking risks or not being straight. *(OPINION, global, 2026)*
8. **In DACH, AI is used to assist recruiting but distrusted as a decider.** Automated candidate ranking sits at 12% adoption and 60%+ of users call it unreliable for independent decisions. A human still makes the call. *(DATA, DACH — Haufe Recruiting Trends 2025 via a 2026-03-21 analysis)*
9. **Berlin tech hiring runs in English.** 59% of German tech startups require no German and 54% use English as the official company language. *(DATA, DACH, Bitkom Startup Report 2023 — older, labelled)*
10. **The EU AI Act's high-risk rules for hiring tools were postponed** from 2026-08-02 to 2027-12-02 by the Digital Omnibus. Employers are not yet under the Annex III obligations. Context only — it changes nothing Karthik must do. *(DATA, EU, 2026)*

**What follows from this:** lead with a plain sentence a non-technical person understands, put a checkable thing in the first screen, carry real numbers from a real evaluation rather than adjectives, name the boundaries explicitly, and keep the page free of anything a reader cannot verify. All four options do this; they differ in how hard they push it.

---

## Part 1 — Research findings, with citations

Every row is labelled **DATA** (survey/measurement) or **OPINION** (post, article, practitioner commentary), and **DACH** or **global**. DACH sources are weighted above global ones where they conflict; none of them did conflict.

### 1.1 How screening changed

| # | Finding | Type | Region | Source | Date |
|---|---|---|---|---|---|
| F1 | Recruiters are deliberately adding friction; ~1 in 5 hiring managers added an extra screening step because of AI-generated applications. Gating via skills assessments and application essays is the recommended response. | OPINION | global | [skillfuel.com](https://www.skillfuel.com/recruiters-friction-job-applications-ai-hiring/) | 2026 (month not stated) |
| F2 | Volume shifted from dozens to "hundreds and hundreds" per posting; a recruiting platform reported recruiters knowing only ~30 of 1,000 applications are serious. Verification steps now include identity checks, skills tests and a return to referral networks. Trusted signals named: direct skill measurement, real-time collaboration, job-relevant evidence over AI-polished CVs. | OPINION (reports DATA) | global | [ptechpartners.com](https://www.ptechpartners.com/2026/09/09/ai-resumes-meet-ai-recruiters-dispatches-from-the-automated-hiring-cycle/) | **2026-09-09** |
| F3 | Developer-side survey data: 76% say AI makes technical assessments easier to fool; 78% say hiring assessments don't measure real work. | DATA (HackerRank 2025, cited secondhand) | global | same as F2 | study 2025, cited 2026-09-09 |
| F4 | ~85% of employers use skills-based hiring; skills-based approaches outperform CV screening because they show proof instead of claims. | DATA (cited secondhand, primary not located) | global | [skillfuel.com](https://www.skillfuel.com/recruiters-friction-job-applications-ai-hiring/) | 2026 |
| F5 | 67% of managers say AI résumés are actively slowing the hiring process. | DATA (survey) | global | [Forbes / Rachel Wells](https://www.forbes.com/sites/rachelwells/2026/03/18/ai-resumes-are-sabotaging-the-hiring-process-67-of-managers-reveal/) | **2026-03-18** |
| F6 | First-hand reporting on the flood of AI-generated applications, impersonators and scams reaching real job postings. | OPINION (first-hand reporting) | global | [The Markup](https://themarkup.org/hello-world/2026/01/24/we-posted-a-job-then-came-the-ai-slop-impersonator-and-recruiter-scam) | **2026-01-24** |

### 1.2 What senior AI-engineering hiring actually tests

| # | Finding | Type | Region | Source | Date |
|---|---|---|---|---|---|
| F7 | Hiring leaders separate signal from noise as follows. **Signal:** problem decomposition, system boundaries (what the agent can and cannot do), evaluation discipline with test cases and error analysis, production awareness (latency, cost, observability), and communication of trade-offs. **Noise:** tool familiarity alone — stated as "tool knowledge on its own is weak signal now" — polished output with no control mechanism, happy-path-only demos, generic AI-fluency claims, AI-assisted résumés with no evidence. Demos should show "one successful path and one controlled failure path". Human-in-the-loop and observability described as non-negotiable in production agentic systems. | OPINION (practitioner/CPTO synthesis) | global | [provn.co](https://provn.co/blog/2026/06/agentic-engineer-hiring-requirements) | **2026-06-03** |
| F8 | Four signals in priority order: (1) a README that reads like a product spec, (2) an eval report with named metrics and numbers, (3) a live deployment URL, (4) cost and latency figures. Red flags: "just vibes" with no evals, no deploy, benchmark claims without numbers, copy-pasted demos. "A live, clickable URL is one of the most-cited must-haves, because reviewers won't clone your repo." A 200-line decisions document described as often more valuable than 2,000 lines of commented code. | OPINION (practitioner) | global | surfaced via search across [alexeygrigorev/ai-engineering-field-guide](https://github.com/alexeygrigorev/ai-engineering-field-guide), [landedjobs/projects-to-land-an-ai-job](https://github.com/landedjobs/projects-to-land-an-ai-job), [slategit.com](https://slategit.com/blog/github-profile-for-ai-engineer-roles-2026), [trycrucible.io](https://trycrucible.io/blog/how-to-get-hired-as-ai-engineer-2026) | 2026 (months not stated) |
| F9 | Eval literacy repeatedly named as the clearest discriminator between people who have shipped LLM systems and people who have not; the distinguishing question is whether an agent survives production rather than whether the demo is slick. | OPINION (vendor commentary) | global | [KORE1](https://www.kore1.com/agentic-ai-hiring-2026/), [HeroHunt](https://www.herohunt.ai/blog/how-to-recruit-ai-evals-engineers-2026/) | 2026 (months not stated) |
| F10 | Candidates with only success stories read as not taking risks or not being honest; portfolios, live coding and behavioural interviews gain weight relative to paper claims. | OPINION | global | [HeroHunt](https://www.herohunt.ai/blog/emerging-skill-sets-ai-era-hiring-managers-guide-2026/) | 2026 |

### 1.3 How a personal site is actually consumed

| # | Finding | Type | Region | Source | Date |
|---|---|---|---|---|---|
| F11 | Practitioner accounts converge on: ~6–8 seconds for the first scan; ~55 seconds to evaluate CV plus portfolio together; the CV is read first, then the portfolio link is clicked; on landing, the reader scans the positioning statement before anything else. | OPINION (practitioner, no methodology published) | global | [uxuniversity newsletter](https://newsletter.uxuniversity.io/p/a-hiring-manager-will-spend-6-seconds), [Presentum](https://presentum.io/design/hiring-explained/evaluating-portfolio-and-resume) | 2026 / undated |
| F12 | Repeated advice, low evidential weight: the portfolio link is clicked before the experience section is read; deployed beats notebooks; generative AI and RAG are now table stakes on an AI CV rather than differentiators. | OPINION (SEO content) | global | [dataexpert.io](https://www.dataexpert.io/blog/ultimate-guide-ai-engineering-portfolios), [CVWon](https://cvwon.com/blog/ai-engineer-cv-2026), [Hakia](https://hakia.com/skills/building-portfolio/) | undated / 2026 |

**Honest handling of the "6 seconds" number.** It appears everywhere and is sourced nowhere. It is used in this report only as a directional design constraint — *the first screen must work alone* — and never presented as a measurement. The same caution applies to "80% more engagement with runnable code" and "68% of first views are mobile", which are quoted in the same content cluster with no methodology. **None of those three figures appears on any mockup.**

### 1.4 DACH specifics

| # | Finding | Type | Region | Source | Date |
|---|---|---|---|---|---|
| F13 | German employers use AI to *assist*, not to decide: automated CV screening 31% adoption, semantic matching 17%, automated ranking 12% — and 60%+ rate automated ranking "unreliable for independent decisions". Barriers named: GDPR concerns 68%, lack of expertise 54%, EU AI Act uncertainty 41%. Only 11% deploy AI specifically in recruiting. | **DATA** (Bitkom New Work 2025, Haufe Recruiting Trends 2025, LinkedIn Talent Insights DACH 2025 — underlying studies are 2025) | **DACH** | [yena.ai analysis](https://www.yena.ai/de/blog/ki-im-recruiting-studie-dach-2026) | analysis **2026-03-21**, underlying studies 2025 |
| F14 | Skills-first framing in DACH: capabilities weighted over formal qualifications; recruiters search for skills rather than complete application dossiers. 55% of German employers reported using AI in recruiting; 67% of German job seekers use generative AI on their applications. | DATA (secondhand, "Talent Trends 2026") | **DACH** | [karriere.at](https://www.karriere.at/c/a/arbeitstrends-2026), [Michael Page DE](https://www.michaelpage.de/personalberatung/management-tipps/ki-im-recruiting) | 2026 (months not stated) |
| F15 | Berlin tech works in English by default; 59% of German tech startups require no German, 54% use English as official company language. Munich skews larger, more German-speaking, more traditional. Application processes run long (two to six months typical for international candidates). | DATA (Bitkom Startup Report 2023 — **older, labelled**) + OPINION | **DACH** | [migaku](https://migaku.com/blog/language-fun/how-to-find-english-speaking-jobs-in-berlins-tech-scene), [tribexyz](https://www.tribexyz.com/blog/tech-hiring-germany-2026) | 2026 article, 2023 study |
| F16 | Named active AI/ML hirers in Berlin include Zalando, JetBrains, Scalable Capital, DeepL, Parloa, Helsing, Aleph Alpha, plus the fintech cluster (N26, Trade Republic, Raisin, Solaris, Mambu). Java named among in-demand backend languages for English-speaking hires. | OPINION (market colour) | **DACH** | same as F15 | 2026 |

**On German cultural preference (directness, substance, modesty).** Searches for this specifically returned nothing citable. **No claim about German cultural communication preferences is made in this report**, and no mockup was designed against an uncited cultural assumption. What *is* evidenced is F13: DACH employers distrust automated judgement and keep a human in the loop — which argues for a page written for a human reader rather than for keyword matching.

### 1.5 EU AI Act — context only

| # | Finding | Type | Source | Date |
|---|---|---|---|---|
| F17 | Annex III high-risk obligations — which cover AI used to filter job applications and evaluate candidates — were scheduled for 2026-08-02. The Digital Omnibus on AI **postponed them by 16 months to 2027-12-02**. Provisional agreement reached 2026-05-07; European Parliament approved 2026-06-16; Council approval and publication followed. | DATA | [Gibson Dunn](https://www.gibsondunn.com/eu-ai-act-omnibus-agreement-postponed-high-risk-deadlines-and-other-key-changes/), [Ogletree](https://ogletree.com/insights-resources/blog-posts/eu-nears-approval-of-agreement-to-delay-rules-for-ai-use-in-employment-decisions/), [ActuIA](https://www.actuia.com/en/news/hr-tools-and-artificial-intelligence-europe-delays-high-risk-obligations-to-december-2027/), [Annex III text](https://artificialintelligenceact.eu/annex/3/) | 2026 |

**Relevance to Karthik: none directly.** He is the candidate, not the deployer. Two indirect consequences worth knowing: employers screening him are *not yet* bound by the Annex III transparency duties, so he should not assume he will be told when AI screened him; and F13's "EU AI Act uncertainty" is already suppressing full automation in DACH, which means **a human is probably reading the page** — which is exactly who these options are designed for.

Note one source (`yena.ai`, 2026-03-21) states the high-risk obligations take effect August 2026. That was accurate when written and is now **superseded** by the Digital Omnibus. Recorded rather than silently dropped.

---

## Part 2 — What the mockups are allowed to claim

Every claim and number on every mockup traces to a row here. Verified on 2026-09-29 against this repository at `f5155e4` and against live production.

| Claim as shown | Used on | Verified source |
|---|---|---|
| Name, Berlin, target roles, English | all | Owner input (task Part 2) |
| NRG Energy (current), Blue Cross Blue Shield Association, Marsh, Northern Trust — **names only, no dates** | all | Owner input |
| "multi-million-customer retail energy systems" | all | Owner input, exact permitted phrasing |
| Java 21 | A, B, D | `app/pom.xml` → `<java.version>21</java.version>` |
| Spring Boot · PostgreSQL · JPA/Hibernate · Flyway · BCrypt + JWT + RBAC · Resilience4j, running | A, B, D | `PORTFOLIO_CAPABILITIES.yaml`: `java-spring-rest-api`, `postgres-jpa-flyway`, `security-jwt-rbac`, `downstream-resilience` — all `PRODUCTION_VERIFIED`; live app returned **200** |
| Approval bound by hash to exact path+content; approve/reject absent from the model's tool schema; asserted by tests | A, B, C, D | `hitl-hash-bound-write-boundary` (`PRODUCTION_VERIFIED`) + its evidence note: "Tests prove a content substitution and a path substitution after approval are each rejected, and that approve/reject are absent from the tool schemas" |
| Crash drill **22 / 22** in one run; killed after the commit, before the checkpoint; one commit only | B, C, D | `durable-langgraph-workflow` (`PRODUCTION_VERIFIED`) evidence note |
| Survived a **real container restart** while waiting for approval, in production | A, B, C, D | same entry, evidence note dated 2026-09-29 |
| **Recall@3 0.83 · Recall@5 0.92 · MRR 0.83 · routing accuracy 1.0** | A, B, D | `rag-mcp-embeddings` evidence note: `recall_at_3=0.833, recall_at_5=0.917, mrr=0.826, routing_accuracy=1.0`. Rounded down/nearest for display |
| "twelve labelled cases" | A, B, D | `agent/evals/retrieval_dataset.json` → 12 entries in `cases`, counted |
| Eval runs in CI and blocks the build | A, B, D | `.github/workflows/ci.yml` runs `eval_runner.py all` as a blocking step |
| Single model boundary, purpose allowlist, zero-LLM kill switch | B, D | `reasoning-gateway-kill-switch` (`PRODUCTION_VERIFIED`); allowlist and `LLM_MODE=DISABLED` in `reasoning_gateway.py` |
| A build-failing test caught a feature bypassing the gateway | B | `standing_interview.py` source comment recording exactly that, plus the registry note |
| Write-through event ledger, spools locally during an outage, real token counts | B, C, D | `durable-event-ledger` (`PRODUCTION_VERIFIED`); live `/usage` returned **200** |
| Grounded answers from a private corpus; refuses below a grounding threshold; no corpus text in the public repo | B | `standing-interview-grounded-rag` (`PRODUCTION_VERIFIED`); threshold gate at `standing_interview.py:983-985`; registry note "No book text in the public repository" |
| "I audit my own systems and publish the result" + the audit's three named defects | D | `docs/audits/SI_AUDIT_2026-09-29.md`, committed at `f5155e4` |
| **PARTIAL:** transactional outbox, RS256/JWKS, aggregator fan-out — implemented, tested, not in production | B | registry `verification_level: TESTED` on `kafka-outbox`, `asymmetric-jwt-jwks`, `bff-aggregator-fan-out` |
| **NOT BUILT:** second model provider / routing / failover; managed vector DB, hybrid search, reranking; automated deployment | B, C, D | Owner constraint list; absence confirmed in repo — one provider behind one gateway, cosine similarity in `standing_interview.py`, deploys via `scripts/deploy_platform_with_si_corpus.sh` triggered by hand |
| Honest limit on C: one crash case proven locally only; lost workspace fails safely; no durable remote for the branch | C | `SI_AUDIT`-era Sprint 13 record and `PROJECT_STATE.json`'s explicit "NOT VERIFIED on production" note |
| All live URLs | all | `curl` on 2026-09-29: `/`, `/standing-interview`, `/showcase/senior-java-ai-transformation`, `/ask-codebase`, `/triage`, `/usage`, `/workbench` and the customer app all returned **200**; GitHub repo returned **200** (public) |

### Claims deliberately NOT made, and why

| Not used | Why |
|---|---|
| "15 years of experience" | **The Owner supplied no years figure**, and years-of-experience is a timeline claim he explicitly deferred. An early draft of these mockups contained it; it was removed. Now Owner decision #3. |
| "For the past year I have built this platform" | **False.** The repository's first commit is **2026-09-08**; there are 534 commits to 2026-09-29 — about three weeks. An early draft said "a year". Removed from all four mockups. Now Owner decision #4. |
| "15/15 on the Standing Interview acceptance gate" | The registry records it, but the audit committed the same day found that gate has **no quality oracle** and passes answers the Owner rejects. Quoting it as showcase material would be an overclaim. |
| CI test counts (e.g. "715 tests") | Not independently re-verified in this session. `ci_python_tests.py` only asserts a floor of 520. |
| Any Standing Interview answer text | Owner constraint — the surface is mid-fix. Mockups link to it; none quotes it. |
| Learn, JD Match | Owner constraint — becoming private. **Neither is linked from any mockup.** (Note: both currently return 200 to a direct URL; see Owner decision #7.) |
| Kafka in any employer sentence | The repo's `kafka-outbox` is this platform's own, `TESTED`, not production. Placed in the PARTIAL section on Option B, far from any employer paragraph. |
| Certifications, awards, personal details, phone, address, salary | Owner constraint |

---

## Part 3 — The four options

### Option A — "Thirty Seconds"
**Folder:** `option-a-recruiter-30s/` · **Look:** warm off-white, deep green accent, single reading column, sans-serif.

**Concept.** A brief, not a portfolio. Three pieces of proof, each one sentence of plain English with a link, then everything else below a hard rule. Built on the assumption that the first screen has to work entirely on its own (F11) and that a reader who is checking rather than admiring wants a link, not adjectives (F8).

**Target reader:** HR screener first, recruiter second.

| Depth | What they get |
|---|---|
| **10 s** | Name; one sentence — "I build backend systems, and the agentic AI that ships them"; Berlin; Java and Spring; currently NRG Energy. |
| **30 s** | Three proof blocks: the approval gate the model cannot open, the workflow that survives a crash, retrieval with real eval numbers. Each ends in a link to a running system or to source. |
| **2 min** | Full stack line, four employers, an explicit "what this platform is and is not" box, and the capability map. |

**Findings applied:** F11 (first screen stands alone) · F8 (live URL per claim) · F7 (boundaries stated, not implied) · F3/F12 (plain enough for a non-technical reader).

**Strengths.** Lowest risk of being misread. Fastest to build. Reads like a person wrote it. Works identically on a phone.

**Weaknesses.** Three proof blocks is thin for an architect-level screener — they will jump to GitHub quickly. It is the least memorable of the four.

**Overclaim risk: low.** Every claim is a link. The only soft phrase is "I build backend systems, and the agentic AI that ships them", which is accurate: the delivery agent does ship changes into this repository.

---

### Option B — "The Proof Wall"
**Folder:** `option-b-proof-wall/` · **Look:** dark, dense, three-column status/claim/evidence rows, colour-coded LIVE / PARTIAL / NOT BUILT.

**Concept.** The direct answer to the 2026 problem. Every claim carries a verification level and links to the running thing; then a section titled **"Not built here"** lists, in the same visual language, the things that do not exist — second model provider, managed vector DB / hybrid search / reranking, automated deployment. It is the one page in this set that a reader can *fail* to disprove.

**Target reader:** technical recruiter and hiring manager.

| Depth | What they get |
|---|---|
| **10 s** | "Every claim on this page links to the running thing." Name, Berlin, senior/lead, NRG Energy. A pointer telling them the last two rows are the interesting ones. |
| **30 s** | Six LIVE rows scanned by status colour — approval gate, durable workflow with 22/22, eval numbers, model boundary with kill switch, grounded answering, metered ledger. |
| **2 min** | The PARTIAL row, the three NOT BUILT rows with reasons, and a short note explaining why the absences are published. |

**Findings applied:** F1/F2/F5/F6 (verification is the scarce thing) · F7 (system boundaries; controlled failure path) · F8 (eval numbers; live URLs) · F9 (eval literacy) · F10 (honesty as trust signal) · F13 (a human is reading).

**Strengths.** Hardest of the four to fake and the most distinctive. Gives a technical screener everything they need without leaving the page. The "Not built here" section is genuinely rare and does the most work.

**Weaknesses.** Dense and dark — a non-technical HR screener may bounce. Three grey "NOT BUILT" rows can be misread as three gaps if skimmed. Only credible if the statuses stay true, which means the live version must be generated from `PORTFOLIO_CAPABILITIES.yaml` rather than hand-maintained.

**Overclaim risk: lowest of the four** — it is structurally an anti-overclaim page. The inverse risk is *underselling*: a reader in a hurry may weight the absences too heavily.

---

### Option C — "One System, In Depth"
**Folder:** `option-c-one-system/` · **Look:** serif body text, warm paper, editorial long-form with a three-figure banner.

**Concept.** One engineering story told properly: *what happens when the machine dies halfway through an AI-written change?* Problem, design decision, the reasoning behind idempotency, the crash drill, the three real defects it found, what it does in production, and an explicit statement of the limit that is still only proven locally. This is F8's "README that reads like a product spec" and F7's "communication of trade-offs" rendered as a page, and it is the only option that shows **how he thinks** rather than **how much he has**.

**Target reader:** hiring manager, staff/architect-level interviewer.

| Depth | What they get |
|---|---|
| **10 s** | A real engineering question as the headline, plus three figures: 22/22 crash drill, survived a restart, zero duplicate writes. |
| **30 s** | The problem framed in two sentences, and the pull-quote carrying the actual insight — the idempotency key had to be derivable from the work itself, because the crash can land between doing the work and recording it. |
| **2 min** | The full narrative, the four drill scenarios, the three defects found, a production behaviour table, source links, and an honest-limits box. |

**Findings applied:** F7 (decomposition, boundaries, trade-off communication, controlled failure path) · F8 (spec-quality writing; the "200-line decisions document") · F9 (production survival over demo polish) · F10 (limits stated).

**Strengths.** By far the strongest signal of seniority. Self-selects for the reader who actually decides. Memorable — a manager can retell this story.

**Weaknesses.** An HR screener will not read it and may not learn what role he wants. It bets everything on one system; if the reader does not care about durable execution, there is no second door. Longest to read.

**Overclaim risk: low, but with one sharp edge** — the page must keep its honest-limits box, because without it a reader could infer employer-scale production operation. The box is present and explicit.

---

### Option D — "What Are You Hiring For?"
**Folder:** `option-d-what-are-you-hiring-for/` · **Look:** light, structured, three columns, deep blue accent, native `<details>` disclosure.

**Concept.** Skills-based screening made literal (F4, F14). The reader is matching a requirements list, not reading a biography — so the page asks which role they are filling and maps the *same* real evidence three ways: backend/Java lead, agentic/GenAI lead, platform/architect. A shared "true in every case" block carries the employment-vs-own-platform boundary and the not-built list, so no door can overstate.

**Target reader:** recruiter working from a requirements list; also serves HR and hiring manager.

| Depth | What they get |
|---|---|
| **10 s** | "Same engineer. Pick the role you are filling." Name, Berlin, English, open to Lead/Senior/Architect. |
| **30 s** | Three labelled doors with one-line descriptions; the first is open by default showing three pieces of backend evidence with links. |
| **2 min** | Any or all doors opened, plus the shared honesty block and the explicit not-built list. |

**Findings applied:** F4/F14 (skills-based matching) · F16 (both backend and AI demand are real in Berlin) · F8 (a live link per evidence row) · F10 (shared honesty block) · F15 (English stated up front).

**Strengths.** Answers the reader's actual question — *is this person right for my req?* — in one glance. Covers the dual positioning without splitting the identity, because the doors share one evidence base. Keyboard-accessible with no JavaScript.

**Weaknesses.** Real risk of reading as a generalist rather than as strong at the intersection — mitigated by the single opening sentence, but not eliminated. Three doors is three surfaces to keep true. An HR screener may not realise the doors are clickable, even with the "Evidence ↓" cue.

**Overclaim risk: low.** The shared block is doing the safety work; if it were ever removed, the architect door in particular could imply employer-scale platform ownership.

---

## Part 4 — Comparison and recommendation

Criteria are derived from the findings, not invented. 1 = weak, 5 = strong (Overclaim risk and Build cost are inverted — 5 is *lowest* risk / *lowest* cost).

| Criterion | Finding | A · 30 Seconds | B · Proof Wall | C · One System | D · Hiring For? |
|---|---|:--:|:--:|:--:|:--:|
| First screen works alone | F11 | **5** | 4 | 3 | 4 |
| Checkable proof in 30 s | F2, F6, F8 | 4 | **5** | 3 | 4 |
| Depth for a hiring manager | F7, F9 | 2 | 4 | **5** | 4 |
| Counters AI-slop suspicion | F1, F5, F6, F10 | 3 | **5** | 4 | 4 |
| Readable by non-technical HR | F3, F13 | **5** | 2 | 2 | 4 |
| Matches a requirements list | F4, F14 | 3 | 4 | 2 | **5** |
| Shows eval literacy with numbers | F8, F9 | 4 | **5** | 4 | 4 |
| Low overclaim risk | F7, F10 | 4 | **5** | 4 | 4 |
| Low build + upkeep cost | — | **5** | 3 | 4 | 3 |
| Memorable after the tab closes | F7 | 2 | 4 | **5** | 3 |
| **Total (max 50)** | | **37** | **41** | **36** | **39** |

### Recommended: **Option B — The Proof Wall**, with two changes borrowed from A

Reasons, in order of weight:

1. **The role level decides the reader.** Karthik is applying for Lead / Senior / Lead Expert / Architect roles in agentic-GenAI. At that level a technical person screens the portfolio, and F7 and F8 say precisely what that person looks for: boundaries, evals with numbers, a live URL, cost and observability. Option B is the only one that puts all four in the first screen.
2. **Verifiability is the scarce good in 2026.** F1, F2, F5 and F6 all describe the same market: polish is free, so proof is the differentiator. B is built as proof and nothing else.
3. **The "Not built here" section is the rarest thing in this set.** F10 says candidates with only successes read as not being straight. Almost nobody publishes their absences. It costs Karthik nothing — the absences are defensible scope decisions — and it makes every LIVE row above it more believable.
4. **It removes the biggest failure mode of the current site.** The root URL is the Workbench today (`agent/web_server.py:2264`, `Route("/", workbench_page)`); an HR person landing on an internal delivery console is the worst version of the first thirty seconds.

**The two changes to make before it goes live:**
- **Lift A's opening sentence above B's table.** B's current headline — "Every claim on this page links to the running thing" — is a promise about the page, not a statement about the person. It should be preceded by one plain sentence saying what he does, so the 10-second HR read still works. This is the single biggest weakness in B's score (readable by non-technical HR: 2/5).
- **Generate the statuses from `PORTFOLIO_CAPABILITIES.yaml`.** The registry already carries `verification_level` on all 22 entries and 45 validated evidence links. A hand-typed proof wall will drift, and a drifted proof wall is worse than none.

**Second choice: Option D**, if Karthik applies mostly through recruiters and agencies rather than directly. It scores 39 and is the strongest on requirements-list matching, which is what an agency recruiter is actually doing.

**Option C should be built regardless — but as a linked page, not the home page.** It is the best writing in the set and the strongest seniority signal; it is simply the wrong first screen. Make it the destination behind B's durable-workflow row.

---

## Part 5 — Legal and compliance for the live version

**This is a summary of what the sources say, not legal advice. Two points below are genuinely unsettled and are flagged as such.**

### Impressum (§ 5 DDG)
The **DDG (Digitale-Dienste-Gesetz)** replaced the TMG on **2024-05-14**, and the TTDSG became the **TDDDG**. The § 5 duties are substantially the same as the old § 5 TMG. ([e-recht24](https://www.e-recht24.de/news/datenschutz/13296-webseitenbetreiber-aufgepasst-das-tmg-wird-zum-digitale-dienste-gesetz-aktualisieren-sie-jetzt-ihr-impressum.html), [dabonline](https://www.dabonline.de/recht/website-impressum-korrekt-tmg-ddg), [IHK Nürnberg](https://www.ihk-nuernberg.de/ihr-unternehmen/rechtsinformationen-fuer-unternehmen/internetrecht-recht-des-e-commerce/impressumspflicht))

The obligation attaches to *geschäftsmäßige* digital services. Purely private pages are generally outside it; sources specifically name advertising or income as what pulls a private page in. **UNCERTAIN:** a personal site whose purpose is to obtain employment sits in a grey area, and no source found addresses it directly. The pragmatic reading — and this is a judgement, not a citation — is that a job-search page without advertising, monetisation or freelance solicitation is not obviously *geschäftsmäßig*, but that adding an Impressum costs little and removes the question. **If Karthik ever offers freelance or contract services through the site, the grey area disappears and an Impressum is required.**

If added, required content: name, a postal address, and an email plus a second fast contact route — since the 2022 amendment an email address alone is not sufficient; a phone number or a guaranteed-fast contact form is needed. Fines for § 5 breaches can reach €50,000. ([fuer-gruender.de](https://www.fuer-gruender.de/wissen/unternehmen-gruenden/website-erstellen/impressum-erstellen/), [gesetz-ratgeber.de](https://gesetz-ratgeber.de/rechtsgebiete/datenschutz-it-recht/impressumspflicht-datenschutzerklaerung-website))

**Direct conflict with the Owner's own rule:** an Impressum requires a postal address, and the task explicitly forbids showing a home address. A business/c-o address would be needed. That is Owner decision #6.

### Privacy notice (Art. 13 GDPR)
A privacy notice is required on **every** website that processes personal data. Server access logs containing IP addresses are generally treated as personal data, so in practice a privacy notice is needed even for a page with no forms and no analytics. It must cover the hosting provider as processor.

**UNCERTAIN and worth real attention:** the platform is hosted on **Railway**, a US provider. International-transfer disclosure (Art. 44 ff. / Art. 13(1)(f)) would need to be addressed, and the current hosting arrangement's transfer basis has not been checked as part of this work.

### Cookies and consent (§ 25 TDDDG)
Consent is required for storing or accessing information on a user's device beyond what is strictly necessary.

**The four mockups need no consent banner at all**, and this was a design decision rather than an accident: no cookies, no `localStorage`, no analytics, no third-party scripts, no external fonts, no trackers, no embedded media. Everything is inline in a single HTML file. Verified — the browser pass recorded zero failed network requests and zero external hosts. **Keeping it that way is the cheapest compliance posture available**, and it also makes the page fast, which serves F11.

### What the live version would need
1. A privacy notice covering hosting, server logs and the US transfer position.
2. A decision on the Impressum (see #6 below), with a non-home address if yes.
3. No analytics — or, if Karthik wants visit data, a consent-free, non-tracking server-side count rather than a third-party script.
4. If the Standing Interview stays linked: a line saying what happens to a typed question. Questions are currently written to a private event ledger, which is a processing activity a privacy notice should name.

---

## Part 6 — Owner decisions required

| # | Decision | Why it cannot be settled here |
|---|---|---|
| 1 | **Headline wording.** A: "I build backend systems, and the agentic AI that ships them." B: "Every claim on this page links to the running thing." C: the crash question. D: "Same engineer. Pick the role you are filling." Which voice is yours? | It is the sentence the whole page hangs on, and it is a matter of how you want to sound. |
| 2 | **Which option to build** — or the recommended B-with-A's-opener hybrid. | Product judgement; the comparison table narrows it, it does not decide it. |
| 3 | **Years of experience.** No figure was supplied, so none is shown. State the number, or leave it off deliberately? | An early draft said "fifteen years" with no source. Removed. Your fact to give. |
| 4 | **How to describe the platform's age.** The first commit is 2026-09-08 — about three weeks and 534 commits. An early draft claimed "the past year"; that was false and is gone. Options: say nothing (current), or state it truthfully as recent and fast. The git history is public, so whatever is said must match it. | Positioning judgement with a real trade-off: velocity signal vs "toy project" risk. |
| 5 | **Employment timeline.** Dates are shown nowhere per your instruction. Confirm the dates and the order, or keep names only? | You deferred this explicitly. |
| 6 | **Impressum.** Add one — which needs a postal address you are willing to publish, and your rule forbids the home one — or rely on the private-page exemption and accept the grey area? | Legal exposure plus a privacy trade-off. Not mine to decide. |
| 7 | **`/learn` and `/jd-match` are still reachable.** Both return **200** to a direct URL; they are only absent from the nav. A new front door raises traffic. Make them genuinely private before or with the home page? | Already tracked as `BL-099`; it is a sequencing call. |
| 8 | **CV file and LinkedIn URL.** Both are `#cv-download-TODO` / `#linkedin-TODO` placeholders. Where does the PDF live, and is it ATS-safe separately? | No CV artefact exists in this repository. |
| 9 | **Does `/` become the new page, or a new path with `/` redirecting?** | The former is cleaner; the latter is reversible in one line. |
| 10 | **Publishing the "Not built here" list.** It is the strongest trust signal in the research and the one element that states your limits publicly. | It is your reputation. I will not put it live on judgement alone. |

---

## Part 7 — Research limitations

Stated plainly, because several of them matter.

1. **Post-2026-09-01 evidence is thin.** Exactly **one** source found is dated after 2026-09-01 and substantive: [ptechpartners.com, 2026-09-09](https://www.ptechpartners.com/2026/09/09/ai-resumes-meet-ai-recruiters-dispatches-from-the-automated-hiring-cycle/). The strongest source on agentic hiring specifically is **2026-06-03**. Everything else is Jan–Jul 2026 or undated, and labelled with what it is.
2. **LinkedIn, X and Reddit produced nothing citable.** The available search tool is US-indexed and returned SEO content rather than posts from r/cscareerquestionsEU, r/berlin, r/germany, r/recruitinghell, r/ExperiencedDevs or r/MachineLearning. **No Reddit, LinkedIn or X source is cited anywhere in this report, and no claim is attributed to them.** Community sentiment — which is where DACH candidate-side reality actually lives — is a real gap that needs a manual pass.
3. **No German-language primary sources were reachable.** heise, t3n, Stepstone's own research pages and XING/New Work did not surface with usable dated content. The DACH data here comes through a single German-language secondary analysis (yena.ai, 2026-03-21) that cites Bitkom, Haufe, LinkedIn Talent Insights and IAB. **Those underlying studies are 2025**, and the citation is secondhand — the primary PDFs were not retrieved.
4. **One widely-repeated figure could not be verified and is not used.** A "100 → 1,000+ applicants per role" figure attributed to WIRED, August 2026, did not resolve to a locatable article; search returned 240–300+ per posting as the more commonly cited range. **The unverified figure appears nowhere in this report or on any mockup.**
5. **The "6-second scan" family of numbers has no methodology** in any source found. Used only as a directional constraint; never shown on a mockup.
6. **No evidence was found on German cultural communication preferences** in hiring. No claim about directness, modesty or self-promotion is made, and no mockup was designed against one.
7. **ATS vendor data was not obtained.** Nothing published by Workday/HiredScore, Greenhouse, SmartRecruiters or Personio was retrieved directly; the one Greenhouse figure quoted reaches this report secondhand through the 2026-09-09 article.
8. **The legal section is a summary of secondary sources**, several of them commercial blogs, and two questions in it are genuinely unsettled (the private-page Impressum exemption for a job-search site; the US-hosting transfer basis). It is not legal advice.

---

## Verification record

Real Chromium via Playwright 1.63.0, 2026-09-29, at 1280×900 and 390×844. Full results in `screenshots/verification.json`.

**68 of 68 checks passed** across all five pages (chooser + four options), covering: page loads, an `h1` is present, the MOCKUP label renders, no horizontal overflow at either width, no console errors, no uncaught page errors, all four chooser links resolve to real files, clicking through navigates, the back-link returns to the chooser, and Option D's disclosure widget opens from the keyboard.

Screenshots: `screenshots/<option>--desktop.png` and `--mobile.png`, full-page, ten files.

**Two defects were found and fixed during verification**, recorded here rather than quietly corrected: Option D's three role cards stretched to the height of the tallest when one was opened, leaving two tall empty boxes (fixed with `align-items: start`); and a stray character in Option B's CSS left an invalid declaration (removed).
