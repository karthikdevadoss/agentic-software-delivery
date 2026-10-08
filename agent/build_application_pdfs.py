#!/usr/bin/env python3
"""Build the CV and cover-letter PDFs an employer receives, from repo inputs only.

Ported verbatim from `cv-out/rebuild_review15.py`, which ran on one person's
computer from an absolute scratch path and was never committed. That was root
cause 1 of incident INC_2026-10-08 (DEVADOSS storage/incidents/): only the
*output* of this step was in version control, so nobody else could reproduce,
review or re-bake a document an employer reads.

Only the paths changed. The tailoring, the sealed skill blocks, the cover-letter
bodies and the Chrome print path are the original's, so the output is comparable
to the PDFs already baked. Inputs now live beside it in `application_sources/`:
the CV template, the 16 cover-letter sources, and each pack's posting and
fit-gaps text.

    python build_application_pdfs.py --check     # report missing inputs, render nothing
    python build_application_pdfs.py             # rebuild every pair

The testing rule this exists to satisfy: **no artifact used for a submit may come
from an uncommitted tool.**
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
SOURCES = AGENT_DIR / "application_sources"
ROOT = AGENT_DIR / "web"
BUILD = ROOT / "_pdf_build"
PDF = ROOT / "applications_pdf"
COVERS = SOURCES / "covers"
TEMPLATE = SOURCES / "cv_v1.html"
#: Pack text vendored into this repo, so the build needs no sibling checkout.
GOV50 = SOURCES / "packs"
GOV10 = SOURCES / "packs"
#: Optional hand-off copy; skipped when unset.
READY = None
#: Resolved at run time; overridable with --chrome.
CHROME = None
ASOF = date(2026, 10, 6)
EMAIL = "itskarthiksid@yahoo.com"
PHONE = "+49 1521 0924553"

# Sealed skill blocks (models line locked)
SKILL = {
    "AI architecture": (
        '<div class="k">AI architecture</div><div>AI solution design · human-approval &amp; '
        "capability boundaries · deterministic vs LLM decision split · RAG &amp; retrieval "
        "evaluation (recall/MRR) · MCP &amp; agent tool boundaries</div>"
    ),
    "AI stack": (
        '<div class="k">AI stack</div><div>Models used day-to-day: Claude Sonnet, Claude Code, '
        "Grok Bot, Fabel, GPT-4o / Azure OpenAI, Gemini · vector retrieval (production triage) · "
        "Python, Anthropic API, embeddings, Postgres, Playwright (personal project)</div>"
    ),
    "Backend": (
        '<div class="k">Backend</div><div>Java, Spring Boot, REST, GraphQL, JWT/FusionAuth, '
        "AWS Lambda/SAM, SQS, Oracle, Docker, Jenkins, JUnit, Kafka, FHIR, Apache Camel</div>"
    ),
}

# Final 15: keep current 8 that qualify + 7 newest TOP not already included; newest-first order
PACKS = [
    dict(
        company_slug="tavily",
        company="Tavily",
        title="Forward Deployed Engineer, Enterprise",
        location="London or Remote - Europe",
        posted="2026-09-24",
        loc_tier=1,
        batch="architect50-2026-10-06",
        source_rank=13,
        role_slug="tavily-forward-deployed-engineer-enterprise",
        url="https://job-boards.eu.greenhouse.io/tavily/jobs/4976971101?gh_jid=4976971101",
        fit_oneliner="Remote-Europe FDE for web-search/retrieval APIs used by agents; RAG, retrieval evals and backend integrations match.",
        headline="Forward Deployed Engineer (search &amp; agent infrastructure) | RAG &amp; backend foundation",
        skill_order=["AI stack", "AI architecture", "Backend"],
        gov=GOV50 / "tavily-forward-deployed-engineer-enterprise",
        suitability=5,
    ),
    dict(
        company_slug="oyster",
        company="Oyster",
        title="Senior AI Solutions Engineer - GTM",
        location="Remote (EMEA)",
        posted="2026-09-18",
        loc_tier=1,
        batch="architect50-2026-10-06",
        source_rank=19,
        role_slug="oyster-senior-ai-solutions-engineer-gtm",
        url="https://jobs.ashbyhq.com/oyster/440f7cfe-3649-411c-8009-3ad09213435d",
        fit_oneliner="Remote EMEA; owns AI agents/workflows from design to adoption — mirrors NRG multi-team AI triage adoption and personal agent platform.",
        headline="Senior AI Solutions Engineer (GTM) | Agents, workflows &amp; backend foundation",
        skill_order=["AI architecture", "AI stack", "Backend"],
        gov=GOV50 / "oyster-senior-ai-solutions-engineer-gtm",
        suitability=5,
    ),
    dict(
        company_slug="nebius",
        company="Nebius",
        title="Forward Deployed Engineer, Physical AI Infrastructure",
        location="Remote - Europe",
        posted="2026-09-17",
        loc_tier=1,
        batch="architect50-2026-10-06",
        source_rank=23,
        role_slug="nebius-fde-physical-ai-infrastructure",
        url="https://careers.nebius.com/?gh_jid=4976988101",
        fit_oneliner="Remote Europe FDE at an AI cloud; cloud/backend (AWS Lambda/SAM, SQS) and customer delivery.",
        headline="Forward Deployed Engineer (Physical AI Infrastructure) | Cloud &amp; backend foundation",
        skill_order=["Backend", "AI architecture", "AI stack"],
        gov=GOV50 / "nebius-fde-physical-ai-infrastructure",
        suitability=4,
    ),
    dict(
        company_slug="n8n",
        company="n8n",
        title="Forward Deployed Engineer - EMEA",
        location="Remote (Germany / Europe); company language English",
        posted="2026-09-15",
        loc_tier=1,
        batch="architect-2026-10-06",
        source_rank=1,
        role_slug="n8n-forward-deployed-engineer-emea",
        url="https://jobs.ashbyhq.com/n8n/c9fc97fa-a473-4133-b3cb-502785649ecd",
        fit_oneliner="Founding FDE on enterprise automation deployments; English company language; remote Germany; backend/API/integration depth matches NRG + personal agent platform.",
        headline="Forward Deployed Engineer (AI orchestration) | Backend &amp; integration foundation",
        skill_order=["Backend", "AI architecture", "AI stack"],
        gov=GOV10 / "n8n-forward-deployed-engineer-emea",
        suitability=5,
    ),
    dict(
        company_slug="moss",
        company="Moss",
        title="Applied AI Engineer",
        location="Berlin / Warsaw / London (hybrid)",
        posted="2026-09-01",
        loc_tier=2,
        batch="architect50-2026-10-06",
        source_rank=32,
        role_slug="moss-applied-ai-engineer-berlin",
        url="https://jobs.ashbyhq.com/moss/a4cd2807-aabc-4dfb-9256-0b3736582efe",
        fit_oneliner="Berlin hybrid; owns agent features end to end from architecture and evaluation through backend integration.",
        headline="Applied AI Engineer | Agents, evals &amp; backend foundation",
        skill_order=["AI architecture", "AI stack", "Backend"],
        gov=GOV50 / "moss-applied-ai-engineer-berlin",
        suitability=5,
    ),
    dict(
        company_slug="langchain",
        company="LangChain",
        title="Deployed Architect, Professional Services (Amsterdam)",
        location="Amsterdam, Netherlands — remote with up to 25% travel (NL-anchored); Owner exception 2026-10-07 for Review list",
        posted="2026-08-28",
        loc_tier=1,
        batch="architect-2026-10-06",
        source_rank=7,
        role_slug="langchain-deployed-architect-amsterdam",
        url="https://jobs.ashbyhq.com/LangChain/fc868832-3865-4f4a-8222-33422a7d3d96",
        fit_oneliner="Exact Deployed Architect title at LangChain; multi-agent/LangGraph/RAG/evals + customer PS; English; remote with travel.",
        headline="Deployed Architect (Agent platforms) | LangChain/RAG &amp; backend foundation",
        skill_order=["AI architecture", "AI stack", "Backend"],
        gov=GOV10 / "langchain-deployed-architect-amsterdam",
        suitability=5,
    ),
    dict(
        company_slug="runpod",
        company="RunPod",
        title="Forward Deployed Engineer EMEA",
        location="Remote - EMEA",
        posted="2026-08-25",
        loc_tier=1,
        batch="architect50-2026-10-06",
        source_rank=33,
        role_slug="runpod-forward-deployed-engineer-emea",
        url="https://jobs.ashbyhq.com/runpod/d9eca07a-a35b-4c31-8d8f-a243f05014ad",
        fit_oneliner="Remote EMEA FDE; customer integration and cloud backend work for GPU cloud platform.",
        headline="Forward Deployed Engineer (EMEA) | Cloud backends &amp; customer delivery",
        skill_order=["Backend", "AI stack", "AI architecture"],
        gov=GOV50 / "runpod-forward-deployed-engineer-emea",
        suitability=4,
    ),
    dict(
        company_slug="databricks",
        company="Databricks",
        title="Forward Deployed Engineer",
        location="Berlin or Munich, Germany (also Belgrade)",
        posted="2026-08-24",
        loc_tier=3,
        batch="architect-2026-10-06",
        source_rank=5,
        role_slug="databricks-forward-deployed-engineer-de",
        url="https://job-boards.greenhouse.io/databricks/jobs/8648494002",
        fit_oneliner="Owns architecture and design decisions for customer data+AI productions on Databricks; Berlin listed; English.",
        headline="Forward Deployed Engineer (Data &amp; AI) | Architecture &amp; backend foundation",
        skill_order=["Backend", "AI architecture", "AI stack"],
        gov=GOV10 / "databricks-forward-deployed-engineer-de",
        suitability=4,
    ),
    dict(
        company_slug="dbxfull",
        company="Databricks",
        title="Sr. Forward Deployed Engineer - FDE (Fullstack)",
        location="Berlin or Munich, Germany",
        posted="2026-07-29",
        loc_tier=3,
        batch="architect50-2026-10-06",
        source_rank=39,
        role_slug="databricks-sr-fde-fullstack-berlin",
        url="https://databricks.com/company/careers/open-positions/job?gh_jid=8645052002",
        fit_oneliner="Berlin-listed Sr FDE building full-stack apps on Databricks; English; customer-facing builder path.",
        headline="Sr. Forward Deployed Engineer (Fullstack) | Data, AI &amp; backend foundation",
        skill_order=["Backend", "AI architecture", "AI stack"],
        gov=GOV50 / "databricks-sr-fde-fullstack-berlin",
        suitability=4,
    ),
    dict(
        company_slug="taktilesa",
        company="Taktile",
        title="Solution Architect",
        location="Berlin / London (hybrid)",
        posted="2026-07-27",
        loc_tier=2,
        batch="architect50-2026-10-06",
        source_rank=40,
        role_slug="taktile-solution-architect-berlin",
        url="https://jobs.ashbyhq.com/taktile/abad6833-8790-4947-b4c9-b7daa99e093c",
        fit_oneliner="Berlin hybrid Solution Architect at an AI decisioning platform; architecture + backend integration.",
        headline="Solution Architect (AI decisioning) | Architecture &amp; backend foundation",
        skill_order=["AI architecture", "Backend", "AI stack"],
        gov=GOV50 / "taktile-solution-architect-berlin",
        suitability=4,
    ),
    dict(
        company_slug="taktilefde",
        company="Taktile",
        title="Forward Deployed Engineer",
        location="Berlin / London (hybrid)",
        posted="2026-07-19",
        loc_tier=2,
        batch="architect50-2026-10-06",
        source_rank=41,
        role_slug="taktile-forward-deployed-engineer-berlin",
        url="https://jobs.ashbyhq.com/taktile/594e7ab1-3c77-43b5-be3f-bc30d513c14c",
        fit_oneliner="Berlin hybrid FDE; agentic AI decisioning — strong fit at the right level.",
        headline="Forward Deployed Engineer (AI decisioning) | Python, APIs &amp; backend foundation",
        skill_order=["AI stack", "Backend", "AI architecture"],
        gov=GOV50 / "taktile-forward-deployed-engineer-berlin",
        suitability=5,
    ),
    dict(
        company_slug="taktilesr",
        company="Taktile",
        title="Senior Forward Deployed Engineer",
        location="Berlin / London (hybrid)",
        posted="2026-07-19",
        loc_tier=2,
        batch="architect50-2026-10-06",
        source_rank=42,
        role_slug="taktile-senior-forward-deployed-engineer-berlin",
        url="https://jobs.ashbyhq.com/taktile/d56d9c0d-5585-43d1-bc94-304bcc4ba11f",
        fit_oneliner="Berlin hybrid senior FDE; 4–6 years bar met; same decisioning platform as FDE role.",
        headline="Senior Forward Deployed Engineer (AI decisioning) | Customer delivery &amp; backend",
        skill_order=["Backend", "AI architecture", "AI stack"],
        gov=GOV50 / "taktile-senior-forward-deployed-engineer-berlin",
        suitability=4,
    ),
    dict(
        company_slug="taktilops",
        company="Taktile",
        title="Forward Deployed Engineer (Ops)",
        location="Berlin (hybrid)",
        posted="2026-07-14",
        loc_tier=2,
        batch="architect50-2026-10-06",
        source_rank=43,
        role_slug="taktile-forward-deployed-engineer-ops-berlin",
        url="https://jobs.ashbyhq.com/taktile/6c08e5fb-ae2f-4553-9c07-fd70f616396a",
        fit_oneliner="Berlin hybrid FDE (Ops); agentic AI for financial operations; customer success + engineering.",
        headline="Forward Deployed Engineer (Ops) | Decision platforms &amp; customer delivery",
        skill_order=["AI stack", "Backend", "AI architecture"],
        gov=GOV50 / "taktile-forward-deployed-engineer-ops-berlin",
        suitability=3,
    ),
    dict(
        company_slug="cohere",
        company="Cohere",
        title="Forward Deployed Engineer, Agentic Platform (Europe)",
        location="Europe hybrid (Berlin listed among locations)",
        posted="2026-05-12",
        loc_tier=2,
        batch="architect-2026-10-06",
        source_rank=3,
        role_slug="cohere-fde-agentic-platform-europe",
        url="https://jobs.ashbyhq.com/cohere/2d256112-b336-4539-8133-a0bf7f6698f0",
        fit_oneliner="Agentic platform FDE on North: RAG, multi-step agents, evals, production Python — Berlin among locations.",
        headline="Forward Deployed Engineer (Agentic AI) | RAG, agents &amp; backend foundation",
        skill_order=["AI architecture", "AI stack", "Backend"],
        gov=GOV10 / "cohere-fde-agentic-platform-europe",
        suitability=5,
    ),
    dict(
        company_slug="smartsheet",
        company="Smartsheet",
        title="Sr. Forward Deployed AI Engineer (Remote Eligible in Germany)",
        location="Remote from Germany (Munich hub listed)",
        posted="2026-05-01",
        loc_tier=1,
        batch="architect-2026-10-06",
        source_rank=4,
        role_slug="smartsheet-sr-fde-ai-germany",
        url="https://job-boards.greenhouse.io/smartsheet/jobs/7874013",
        fit_oneliner="Remote Germany FDE owning multi-agent architecture, MCP resource packs, evals/Deployment Kits.",
        headline="Forward Deployed AI Engineer | Multi-agent, MCP &amp; backend foundation",
        skill_order=["AI architecture", "AI stack", "Backend"],
        gov=GOV10 / "smartsheet-sr-fde-ai-germany",
        suitability=4,
    ),
]

assert len(PACKS) == 15
for p in PACKS:
    s = p["company_slug"]
    assert re.fullmatch(r"[a-z0-9]{1,10}", s), s
slugs = [p["company_slug"] for p in PACKS]
assert len(slugs) == len(set(slugs)), slugs


BRING = (
    "- About ten years of Java/Spring backend work, including US large-enterprise delivery: "
    "Marsh in Phoenix (Bluestream / Digital Broker for Affinity — ~95,000 colleagues across 130 countries) "
    "and BCBSA in Chicago (national hub connecting state Blue Cross Blue Shield plans, ~118 million members system-wide).\n"
    "- Since early 2026, one of a handful of engineers in an initial core AI team at a large retail-energy company: "
    "production AI triage with Azure OpenAI, vector retrieval, and a human approval step before any action, now used by several teams.\n"
    "- Own agentic software-delivery platform (live): approval-gated agents, RAG with labelled retrieval evals, "
    "MCP tool boundaries — public proof that AI systems work can hold up past a demo."
)

COVERS_BODY = {
    "tavily": None,  # use gold file
    "oyster": None,
    "nebius": dict(
        open_line=(
            "Nebius is building the AI cloud for teams that need serious compute and infrastructure, "
            "not another thin wrapper on someone else's GPUs. Physical AI Infrastructure FDE work sits "
            "exactly where customer systems meet that platform — and that is the seat I want next."
        ),
        fits=[
            "Cloud and backend depth (AWS Lambda/SAM, SQS, production Java/Spring) for customer integrations on an AI infrastructure stack.",
            "Comfortable embedding with customers on ambiguous delivery problems and turning them into repeatable patterns.",
            "Berlin / Remote Europe base, English day-to-day, used to US-timezone stakeholders from Marsh and BCBSA.",
        ],
        culture=(
            "Building AI that lives in the physical world needs the same production discipline I already use: "
            "human approval before action, clear tool boundaries, and measurable quality — not demos that fall over in week two."
        ),
        close=(
            "If Nebius is going to be the cloud physical-AI teams trust, the FDE seat is where that trust gets earned — "
            "and that is the work I want to do with your customers."
        ),
    ),
    "n8n": dict(
        open_line=(
            "n8n's bet is simple and sharp: give teams a fair-code automation platform they can actually own, "
            "then help enterprises put it into production without losing the flexibility that made them choose it. "
            "That is exactly the kind of customer-facing engineering I want to do next."
        ),
        fits=[
            "Production integrations, APIs, and event-driven backends — the same craft your founding FDE brief describes shipping with customers.",
            "Hands-on agentic automation from my own platform (approval gates, tool boundaries) plus NRG AI triage adopted by several teams.",
            "Remote Germany / Europe, English company language, ready to travel for embedded delivery.",
        ],
        culture=(
            "I like products where workflow ownership stays with the customer. That matches how I design: "
            "deterministic checks where they belong, LLM proposals where they help, and a human gate before action."
        ),
        close=(
            "Enterprises will keep asking for automation they can trust and extend — n8n is built for that, "
            "and I want to be the engineer who helps them get there."
        ),
    ),
    "moss": dict(
        open_line=(
            "Moss is modernising how companies control spend — and Applied AI here means shipping agent features "
            "that change how finance teams work, not bolting a chatbot onto yesterday's process. "
            "Berlin hybrid, end-to-end ownership: that is the shape of role I am aiming for."
        ),
        fits=[
            "Shipped production LLM capability with evaluation and a human-approval boundary; comfortable owning accuracy, latency, and UX tradeoffs.",
            "Strong Python/Java backend and API background for integrating agents into real services and data paths.",
            "Based in Berlin; English day-to-day; experience taking ambiguous problems from design through adoption.",
        ],
        culture=(
            "Spend and finance systems only earn trust when automation is careful with money and permissions. "
            "That is how I already design AI paths: clear capability boundaries and approval before action."
        ),
        close=(
            "If Moss is going to make AI part of how finance teams actually operate, I want to help build the features that prove it."
        ),
    ),
    "runpod": dict(
        open_line=(
            "RunPod gives builders GPU cloud without the usual friction — and Forward Deployed Engineer EMEA "
            "is the role that keeps that promise when a customer's workload gets real. "
            "Customer success plus platform feedback is the kind of loop I want to own."
        ),
        fits=[
            "Cloud/backend production experience (AWS, containers-adjacent delivery, APIs) for onboarding and troubleshooting customer stacks.",
            "Cross-functional delivery with sales, product, and engineering — not ticket-only support.",
            "Remote EMEA / Berlin base; English day-to-day; US-enterprise communication experience from Marsh and BCBSA.",
        ],
        culture=(
            "GPU cloud only works if the customer path is delightful under pressure. "
            "I like roles where technical depth and clear communication both matter on the same day."
        ),
        close=(
            "Builders choosing where to run AI will remember who made the hard parts feel simple — "
            "that is the RunPod FDE job, and it is the work I want next."
        ),
    ),
    "databricks": dict(
        open_line=(
            "Databricks sits at the centre of how serious teams put data and AI into production. "
            "Forward Deployed Engineer in Berlin means owning architecture and delivery with customers — "
            "the customer-facing builder path I am deliberately moving toward."
        ),
        fits=[
            "Took part in architecture discussions and design decisions with the lead; comfortable owning design choices on production systems.",
            "Backend depth (Java/Spring, APIs, cloud) plus hands-on AI triage with retrieval and approval gates.",
            "Berlin-listed role; English; experience delivering for large US enterprises (Marsh Phoenix, BCBSA Chicago).",
        ],
        culture=(
            "Lakehouse and AI platforms only matter when customer productions stay up. "
            "I want the seat where architecture decisions meet measurable delivery outcomes."
        ),
        close=(
            "If Databricks is how customers turn data into production AI, I want to be the FDE helping them get there in Berlin."
        ),
    ),
    "dbxfull": dict(
        open_line=(
            "The Sr. Forward Deployed Engineer (Fullstack) role is for builders who live at the intersection "
            "of technology and business impact — shipping full-stack applications on Databricks with customers. "
            "That customer-facing ownership is what I am selecting for next."
        ),
        fits=[
            "Hands-on delivery across backend services and AI features; used to scope, timelines, and measurable outcomes.",
            "Production AI triage adopted by several teams — translating fuzzy needs into something people actually use.",
            "Berlin-listed; English; large-enterprise delivery background in the US and remote-from-Berlin work.",
        ],
        culture=(
            "Full-stack FDE work rewards people who can hold the whole path: data, app, and the customer's definition of done. "
            "That is how I already ship."
        ),
        close=(
            "I want to build the Databricks applications customers keep — not just the slides that describe them."
        ),
    ),
    "taktilesa": dict(
        open_line=(
            "Taktile's decisioning platform is where AI meets regulated enterprise decisions — "
            "and Solution Architect in Berlin hybrid is the role that makes those architectures commercially and technically sound. "
            "That is the architect-adjacent seat I am building toward."
        ),
        fits=[
            "Took part in architecture discussions with the lead; strong integration patterns (APIs, events, messaging) from Marsh and BCBSA.",
            "Security-minded delivery on sensitive healthcare and insurance data paths; comfortable with auth, audit, and careful data handling.",
            "Berlin hybrid; English; experience across pre-sales-style technical conversations and post-delivery hardening.",
        ],
        culture=(
            "Decisioning in financial services only works when architecture is right for the customer and still commercially sound. "
            "I design with that tension in mind — not architecture theatre."
        ),
        close=(
            "If Taktile is going to be how enterprises make better decisions with AI, I want to help shape the architectures that hold up."
        ),
    ),
    "taktilefde": dict(
        open_line=(
            "Taktile brings agentic AI to decisioning — and Forward Deployed Engineer in Berlin hybrid "
            "is the hands-on path that puts Python, SQL, and REST integrations in front of real customer teams. "
            "That embedded delivery seat matches where I want to grow."
        ),
        fits=[
            "Production-grade backend and API work; Python-capable; REST integrations across complex domains.",
            "Shipped LLM-powered triage with evaluation and human approval — customer-facing technical delivery, not demos alone.",
            "Berlin hybrid; English; ready to partner directly with enterprise users.",
        ],
        culture=(
            "Decision platforms earn trust when the engineer in the room can debug the integration and explain the tradeoff. "
            "That is the FDE craft I want to practice at Taktile."
        ),
        close=(
            "Better decisions need better deployment partners — I want to be one of them on the Taktile team in Berlin."
        ),
    ),
    "taktilesr": dict(
        open_line=(
            "Senior Forward Deployed Engineer at Taktile is the higher-ownership version of embedding with customers "
            "on AI decisioning — more scope, same Berlin hybrid craft. I am writing for that senior FDE seat."
        ),
        fits=[
            "Ten years of backend engineering with recent production AI delivery and multi-team adoption.",
            "Comfortable leading technical deployment conversations and reviewing production Python/SQL/API work.",
            "Berlin hybrid; English; US large-enterprise delivery (Marsh Phoenix, BCBSA Chicago) plus remote-from-Berlin execution.",
        ],
        culture=(
            "Senior FDE work is judgment under ambiguity: what to build, what to refuse, and how to leave the customer stronger. "
            "That is the bar I want to be measured on."
        ),
        close=(
            "I want the senior seat where Taktile's decisioning platform meets the customer's hardest production constraints."
        ),
    ),
    "taktilops": dict(
        open_line=(
            "Forward Deployed Engineer (Ops) at Taktile sits with Engineering, Product, and Customer Success "
            "so customers get maximum value from the decision platform — prompt engineering, APIs, and day-to-day reliability. "
            "Berlin hybrid; that customer-value loop is attractive."
        ),
        fits=[
            "Strong REST/API and backend background; comfortable troubleshooting with enterprise users.",
            "Hands-on with agent-style workflows and approval-gated AI paths from NRG triage and my own platform.",
            "Berlin based; English; relationship-driven technical delivery.",
        ],
        culture=(
            "Ops-flavoured FDE work is still engineering: clear runbooks, careful changes, and users who feel heard. "
            "I like that combination."
        ),
        close=(
            "If Taktile's customers are going to feel the platform as a daily advantage, Ops FDE is where that feeling gets built — "
            "and I want that work."
        ),
    ),
    "langchain": dict(
        open_line=(
            "LangChain is the platform teams use to put agents, RAG, and evaluation into production — "
            "and Deployed Architect, Professional Services (Amsterdam) is the customer-facing architecture seat "
            "that makes those systems survive real deployments. That Deployed Architect title is the shape I want next."
        ),
        fits=[
            "Multi-agent / RAG / evaluation craft from production AI triage and a public agentic delivery platform (LangGraph-class patterns, labelled retrieval evals, MCP boundaries).",
            "Customer-facing technical delivery: architecture discussions with the lead plus backend depth for cloud/Python integrations.",
            "Berlin-based, English day-to-day; comfortable with remote collaboration and travel for professional-services engagements.",
        ],
        culture=(
            "Agent platforms only matter when evaluation and production discipline travel with the demo. "
            "That is already how I design."
        ),
        close=(
            "If LangChain customers are going to trust agents in production, Deployed Architect is where that trust gets earned — "
            "and that is the work I want to do."
        ),
    ),
    "cohere": dict(
        open_line=(
            "Cohere's North agentic platform is for enterprises that need RAG and multi-step agents in production — "
            "and Forward Deployed Engineer, Europe (Berlin listed) is the role that takes that platform into customer environments. "
            "That matches the work I have been doing hands-on."
        ),
        fits=[
            "Production RAG/triage with vector retrieval, Azure OpenAI, and human approval; plus personal platform with labelled retrieval evals and MCP boundaries.",
            "Production Python/backend craft for clean, testable, observable agent applications.",
            "Berlin among listed locations; English; comfortable with customer-facing technical discussions and travel.",
        ],
        culture=(
            "Agentic platforms only matter when evaluation and production discipline travel with the demo. "
            "That is already how I design."
        ),
        close=(
            "Enterprises will judge North by what survives contact with their data — I want to be the FDE who helps that survival happen."
        ),
    ),
    "smartsheet": dict(
        open_line=(
            "Smartsheet is putting multi-agent architecture and MCP-style tool packs into real customer deployments — "
            "and Sr. Forward Deployed AI Engineer (remote eligible in Germany) is the ownership seat for that work. "
            "Reusable Deployment Kits and evals are exactly the kind of craft I want to deepen."
        ),
        fits=[
            "Personal platform already uses MCP tool boundaries, approval gates, and labelled evals — closest public proof for Deployment Kit thinking.",
            "Production AI triage adopted by several teams; backend depth for durable integrations.",
            "Remote from Germany; English required; ready for customer-facing delivery with travel.",
        ],
        culture=(
            "Work management platforms win when AI agents are packaged so the next customer can reuse them. "
            "I like building patterns that survive the second deployment."
        ),
        close=(
            "If Smartsheet is going to make forward-deployed AI a productised practice, I want to help write the kits customers keep."
        ),
    ),
}


def age_days(posted: str) -> int:
    y, m, d = map(int, posted.split("-"))
    return (ASOF - date(y, m, d)).days


def assert_slug(s: str) -> None:
    assert re.fullmatch(r"[a-z0-9]{1,10}", s), s


def cv_name(slug: str) -> str:
    assert_slug(slug)
    return f"Karthikeyan_Devadoss_CV_{slug}.pdf"


def cl_name(slug: str) -> str:
    assert_slug(slug)
    return f"Karthikeyan_Devadoss_CoverLetter_{slug}.pdf"


def render_pdf(html_path: Path, pdf_path: Path) -> None:
    cmd = [
        CHROME,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--no-margins",
        f"--print-to-pdf={pdf_path}",
        # `.as_uri()` rather than an f-string: on Windows a bare path produces
        # file://C:\... which Chrome reads as a host called "c:".
        html_path.resolve().as_uri(),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    # Rewrite via pypdf to drop any residual Chrome stamp artifacts without wiping content
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    if reader.metadata:
        # keep title/author if any; strip producer noise by rewriting
        pass
    tmp = pdf_path.with_suffix(".tmp.pdf")
    with open(tmp, "wb") as f:
        writer.write(f)
    tmp.replace(pdf_path)


def _pdf_pages_and_text(pdf_path: Path):
    """Page count and extracted text, via pypdf.

    The original shelled out to poppler's `pdfinfo` and `pdftotext`. Those are a
    second pair of uncommitted external tools, absent on Windows, and the rule
    this file exists to satisfy is that an artifact used for a submit comes from
    committed tooling. pypdf is already a dependency of the rewrite step below,
    so using it here removes the dependency rather than adding one.
    """
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    return len(reader.pages), text


def assert_cv_pdf(pdf_path: Path) -> None:
    pages, text = _pdf_pages_and_text(pdf_path)
    assert pages == 1, (pdf_path.name, pages)
    assert "Madras University" in text, pdf_path.name
    assert "German" in text, pdf_path.name
    assert "Claude Code" in text and "Grok Bot" in text and "Fabel" in text, pdf_path.name
    assert "Live AI" in text or "Live AI platform" in text or "agentic-platform" in text, pdf_path.name
    # Live AI before GitHub in contact strip
    live_i = text.find("Live AI")
    if live_i < 0:
        live_i = text.find("agentic-platform")
    gh_i = text.find("github.com/karthikdevadoss")
    assert live_i >= 0 and gh_i >= 0 and live_i < gh_i, (pdf_path.name, live_i, gh_i)
    assert "high-criticality" not in text.lower()
    # Education/Languages not wiped
    assert "Education" in text or "EDUCATION" in text or "Madras" in text
    assert "Languages" in text or "LANGUAGES" in text or "German" in text


def tailor_cv_html(pack: dict, template: str) -> str:
    html = template
    # headline only — keep sealed contact order (Berlin · work-auth · Live AI · GitHub)
    html = re.sub(
        r'<div class="headline">.*?</div>',
        f'<div class="headline">{pack["headline"]}</div>',
        html,
        count=1,
        flags=re.S,
    )
    prefix = f'Applying for {pack["title"]} at {pack["company"]}. '
    html = re.sub(
        r'(<p class="summary">)(.*?)(</p>)',
        lambda m: m.group(1) + prefix + m.group(2) + m.group(3),
        html,
        count=1,
        flags=re.S,
    )
    skills_html = "\n  ".join(SKILL[k] for k in pack["skill_order"])
    html = re.sub(
        r'<div class="skills">.*?</div>\s*(?=<h2>Experience</h2>)',
        f'<div class="skills">\n  {skills_html}\n</div>\n\n',
        html,
        count=1,
        flags=re.S,
    )
    # slight tighten for long summary prefixes (content-only visual lock)
    html = html.replace(".job { margin-bottom: 5px; }", ".job { margin-bottom: 4.5px; }")
    html = html.replace("ul { margin: 3px 0 0 0; padding-left: 14px; }", "ul { margin: 2px 0 0 0; padding-left: 14px; }")
    return html


def write_cover_md(pack: dict) -> str:
    slug = pack["company_slug"]
    path = COVERS / f"{pack['role_slug']}.md"
    if slug in ("tavily", "oyster") and path.exists():
        # gold hybrid already copied
        text = path.read_text()
        # ensure Marsh Phoenix + BCBSA Chicago present
        assert "Marsh" in text and "Phoenix" in text
        assert "BCBSA" in text or "Blue Cross" in text
        assert "What I bring" in text and "How it fits" in text
        assert "I spent time on your website" not in text.lower()
        return text

    body = COVERS_BODY[slug]
    fits = "\n".join(f"- {x}" for x in body["fits"])
    text = f"""# Cover letter — {pack['title']} at {pack['company']}

Karthikeyan Devadoss  
Berlin, Germany · {EMAIL} · {PHONE}  
{pack['url']}

Dear Hiring Team,

{body['open_line']} I am writing about the {pack['title']} role.

**What I bring**
{BRING}

**How it fits this role**
{fits}

{body['culture']} At this point in my career I want that customer-facing, architecture-adjacent seat more than another pure backend lane.

{body['close']}

Kind regards,  
Karthikeyan Devadoss
"""
    assert "I spent time on your website" not in text.lower()
    assert "What I bring" in text and "How it fits" in text
    assert "Marsh" in text and "Phoenix" in text
    assert "BCBSA" in text and "Chicago" in text
    path.write_text(text)
    return text


COVER_HTML_CSS = """
@page { size: A4; margin: 0; }
@page { @top-left { content: none; } @top-center { content: none; } @top-right { content: none; }
        @bottom-left { content: none; } @bottom-center { content: none; } @bottom-right { content: none; } }
:root { --accent: #1f4e79; --ink: #1d2329; --muted: #5a6470; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body { font-family: Carlito, "Liberation Sans", Arial, sans-serif; color: var(--ink);
  font-size: 10.5pt; line-height: 1.4; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.page { width: 210mm; padding: 18mm 18mm 16mm 18mm; }
h1 { font-size: 16pt; margin: 0 0 4px; color: var(--accent); }
.meta { color: var(--muted); font-size: 9pt; margin-bottom: 14px; }
.meta a { color: var(--accent); text-decoration: none; }
p { margin: 0 0 8px; }
b, strong { font-weight: 700; }
ul { margin: 4px 0 10px; padding-left: 18px; }
li { margin: 3px 0; }
li::marker { color: var(--accent); }
.sign { margin-top: 14px; }
"""


def cover_md_to_html(md: str, title: str) -> str:
    # Strip markdown heading line; keep body
    lines = md.strip().splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    # Simple conversion
    body_lines = []
    in_ul = False
    for line in lines:
        if line.startswith("**") and line.endswith("**"):
            if in_ul:
                body_lines.append("</ul>")
                in_ul = False
            body_lines.append(f"<p><b>{line.strip('*')}</b></p>")
        elif line.startswith("- "):
            if not in_ul:
                body_lines.append("<ul>")
                in_ul = True
            item = line[2:]
            item = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", item)
            body_lines.append(f"<li>{item}</li>")
        elif line.strip() == "":
            if in_ul:
                body_lines.append("</ul>")
                in_ul = False
        else:
            if in_ul:
                body_lines.append("</ul>")
                in_ul = False
            # header block (name/contact/url) as meta
            esc = line.replace("&", "&amp;")
            if "Karthikeyan Devadoss" == line.strip() and not any("h1" in b for b in body_lines):
                body_lines.append(f"<h1>{esc}</h1>")
            elif line.startswith("http") or "Berlin, Germany" in line:
                if line.startswith("http"):
                    body_lines.append(f'<div class="meta"><a href="{esc}">{esc}</a></div>')
                else:
                    body_lines.append(f'<div class="meta">{esc}</div>')
            else:
                esc2 = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc)
                cls = ' class="sign"' if line.startswith("Kind regards") or line.strip() == "Karthikeyan Devadoss" and "h1" in "".join(body_lines) else ""
                # avoid duplicate name as h1 then again
                if line.strip() == "Karthikeyan Devadoss" and any("<h1>" in b for b in body_lines):
                    body_lines.append(f"<p{cls}>{esc2}</p>")
                else:
                    body_lines.append(f"<p{cls}>{esc2}</p>")
    if in_ul:
        body_lines.append("</ul>")
    inner = "\n".join(body_lines)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<style>{COVER_HTML_CSS}</style></head><body><div class="page">
{inner}
</div></body></html>"""


def load_posting(pack: dict) -> str:
    p = pack["gov"] / "posting.md"
    if p.exists():
        return p.read_text()
    return f"# {pack['company']} — {pack['title']}\n\n- **URL:** {pack['url']}\n"


def load_fit_gaps(pack: dict) -> str:
    p = pack["gov"] / "fit_gaps.md"
    if p.exists():
        return p.read_text()
    return f"# Fit and gaps — {pack['company']} / {pack['title']}\n\n{pack['fit_oneliner']}\n"


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    PDF.mkdir(parents=True, exist_ok=True)
    COVERS.mkdir(parents=True, exist_ok=True)
    template = TEMPLATE.read_text()
    out_packs = []

    # Sort already newest-first in PACKS; verify
    dates = [p["posted"] for p in PACKS]
    assert dates == sorted(dates, reverse=True), dates

    for rank, pack in enumerate(PACKS, start=1):
        slug = pack["company_slug"]
        cover_md = write_cover_md(pack)
        # CV HTML + PDF
        cv_html = tailor_cv_html(pack, template)
        cv_html_path = BUILD / f"cv_{slug}.html"
        cv_html_path.write_text(cv_html)
        cv_pdf_path = PDF / cv_name(slug)
        render_pdf(cv_html_path, cv_pdf_path)
        assert_cv_pdf(cv_pdf_path)

        # Cover HTML + PDF
        cl_html = cover_md_to_html(cover_md, f"Cover — {pack['company']}")
        cl_html_path = BUILD / f"cl_{slug}.html"
        cl_html_path.write_text(cl_html)
        cl_pdf_path = PDF / cl_name(slug)
        render_pdf(cl_html_path, cl_pdf_path)
        cl_pages, _cl_text = _pdf_pages_and_text(cl_pdf_path)
        assert cl_pages >= 1, cl_pdf_path.name

        batch_prefix = "a50" if pack["batch"].startswith("architect50") else "a10"
        pack_id = f"{batch_prefix}-{pack['source_rank']:02d}-{pack['role_slug']}"
        # Prefer shorter id with company_slug for uniqueness across multi-role companies
        pack_id = f"{batch_prefix}-{slug}-{pack['role_slug']}"

        out_packs.append(
            {
                "id": pack_id,
                "batch": pack["batch"],
                "source_rank": pack["source_rank"],
                "slug": pack["role_slug"],
                "company_slug": slug,
                "company": pack["company"],
                "title": pack["title"],
                "location": pack["location"],
                "posted": pack["posted"],
                "age_days": age_days(pack["posted"]),
                "fit_oneliner": pack["fit_oneliner"],
                "url": pack["url"],
                "posting": load_posting(pack),
                "cover_letter": cover_md,
                "fit_gaps": load_fit_gaps(pack),
                "cv_pdf": cv_name(slug),
                "cover_pdf": cl_name(slug),
                "pdfs": [cv_name(slug), cl_name(slug)],
                "rank": rank,
                "loc_tier": pack["loc_tier"],
            }
        )
        print(f"{rank:02d} {slug} CV+CL ok pages_cv=1 cl_pages={cl_pages}")

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "as_of": "2026-10-06",
        "title": "Applications Review — location-filtered TOP",
        "description": (
            "Owner policy v32 / rule 62: remote Germany or remote worldwide/EU/EMEA, "
            "Berlin hybrid, or Berlin office; newest posted first. Sealed CV content + hybrid cover letters. "
            "PDF names: Karthikeyan_Devadoss_CV_<slug> / Karthikeyan_Devadoss_CoverLetter_<slug>. "
            "2026-10-07: LangChain Deployed Architect Amsterdam added by Owner exception (≤15; Cursor SA dropped)."
        ),
        "filter": {
            "policy": "v32",
            "rule": 62,
            "allow": [
                "remote Germany or remote worldwide/EU/EMEA",
                "Berlin hybrid full-time",
                "Berlin all-days office",
            ],
        },
        "count": len(out_packs),
        "packs": out_packs,
        "approve": {
            "one_tap": True,
            "records": ["owner_approved", "approved_at", "status=pending_apply"],
            "web_applies": False,
            "mahadeva": "employer careers form or email apply link only; no LinkedIn Easy Apply",
        },
        "naming": {
            "cv": "Karthikeyan_Devadoss_CV_<company_slug>.pdf",
            "cover_letter": "Karthikeyan_Devadoss_CoverLetter_<company_slug>.pdf",
            "slug_rule": "≤10 letters/digits, lowercase; unique per pack when same employer has multiple roles",
        },
        "dropped": [
            {
                "company": "Camunda",
                "title": "AI Process Forward Deployed Engineer",
                "posted": "2026-05-27",
                "why": "Location OK (remote) but outside ≤15 cap after keeping current 8 + 7 newer TOP packs",
            },
            {
                "company": "GitLab",
                "title": "Forward Deployed Engineer - EMEA",
                "posted": "2026-05-11",
                "why": "Location OK (remote Germany listed) but outside ≤15 cap",
            },
            {
                "company": "Exa",
                "title": "Forward Deployed Engineer, EMEA",
                "why": "London-only (tier 5) — fails location filter",
            },
            {
                "company": "Cursor (Anysphere)",
                "title": "Forward Deployed Engineer - EMEA",
                "why": "London-anchored posting — fails location filter",
            },
            {
                "company": "Cursor (Anysphere)",
                "title": "Solutions Architect, Central Europe",
                "posted": "2026-07-02",
                "why": "Dropped from ≤15 2026-10-07 to add LangChain (Owner-authorized); Cursor SA ATS 404 / unused closed slot preferred over removing submitted packs",
            },
            {
                "why": "All London/Stockholm/Munich-only/Paris/Amsterdam architect50 Other-EU rows — location filter (LangChain Amsterdam added 2026-10-07 by Owner exception)",
            },
        ],
    }
    out_json = ROOT / "applications.json"
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    # also refresh ready path for parent
    if READY is not None:
        shutil.copy2(out_json, READY)
    print("wrote", out_json, "count", payload["count"])


def missing_inputs() -> list:
    """Everything that stops a full rebuild from this repository alone."""
    problems = []
    if not TEMPLATE.is_file():
        problems.append("CV template missing: " + str(TEMPLATE))
    for pack in PACKS:
        cover = COVERS / (pack["role_slug"] + ".md")
        if not cover.is_file():
            problems.append("cover source missing: " + cover.name)
        if not (pack["gov"] / "posting.md").is_file():
            problems.append("posting text missing: " + pack["gov"].name)
    return problems


def _resolve_chrome(explicit=None):
    import shutil as _shutil

    if explicit:
        return explicit
    for name in ("google-chrome-stable", "google-chrome", "chromium",
                 "chromium-browser", "chrome"):
        found = _shutil.which(name)
        if found:
            return found
    return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Rebuild application PDFs")
    parser.add_argument("--check", action="store_true",
                        help="report missing inputs and exit; renders nothing")
    parser.add_argument("--chrome", default=None, help="path to a Chrome binary")
    args = parser.parse_args()

    problems = missing_inputs()
    if args.check:
        if problems:
            print("NOT fully buildable from the repository:")
            for problem in problems:
                print("  -", problem)
            raise SystemExit(1)
        print("every pack is buildable from repo-only inputs:", len(PACKS), "packs")
        raise SystemExit(0)

    if problems:
        print("REFUSED: inputs missing; run --check")
        raise SystemExit(1)
    CHROME = _resolve_chrome(args.chrome)
    if not CHROME:
        print("REFUSED: no Chrome binary found; pass --chrome")
        raise SystemExit(1)
    main()
