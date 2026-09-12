"""
Builds agent/web/learn-tree.json — the ONE canonical recursive Learn
knowledge model consumed by both the interactive Learn UI (learn.js) and
the PDF book generator (learn_pdf.py). There is exactly one knowledge
source; nothing else should hand-author Learn content separately.

Migrates (never deletes):
  - the existing 127-topic / 15-section flat catalog (learn-data.json) —
    becomes reference-level leaf topics nested under reorganized domains.
  - the existing 10-topic / 3-domain deep-dive (learn-deep-topics.json) —
    full WHAT/WHY/HOW/WHEN/development_steps/interview content preserved
    verbatim, nested under new structural subdomains.

Adds real structural depth (Sections 10-14 of P0_PROMPT.txt):
  - System Design: Requirements/APIs/Networking/Compute/Databases/
    Caching/Distributed Systems/Security/Reliability/Observability/
    Cloud-Deployment/Performance, each with real children.
  - AI-Assisted Software Engineering: Human Role (Approval/Interruption/
    Clarification/Escalation) and AI Failure Modes, reusing existing
    deep-dive content where it already exists rather than duplicating it.

Experience classification is assigned honestly from actually-inspected
evidence (app/pom.xml, this project's own code), never invented:
  - CURRENT_PROJECT_EXPERIENCE only for concepts this repo's own code
    genuinely uses (JPA/HikariCP pooling, H2, REST, Docker, Railway, the
    event ledger, Skills/subagents, etc.)
  - LEARNED_UNDERSTOOD for real, correct general engineering knowledge
    not evidenced as this project's or the Creator's own professional
    usage (AWS/Lambda/Kafka/Redis/JWT/Spring Security/Oracle/Cognito/
    FusionAuth/Jenkins are NOT referenced anywhere in this repo or in
    docs/EXPERIENCE_EVIDENCE.md, so none of them are marked as
    professional experience -- see docs/EXPERIENCE_EVIDENCE.md's own
    "What is explicitly NOT here" section).
  - No REAL_PROFESSIONAL_EXPERIENCE claim is made anywhere in this
    generator, since no such evidence file exists in this repository.

Run: python agent/build_learn_tree.py
"""

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent / "web"
REPO_ROOT = Path(__file__).resolve().parent.parent

LEARNED = "LEARNED_UNDERSTOOD"
CURRENT = "CURRENT_PROJECT_EXPERIENCE"
PLANNED = "PLANNED_NOT_EXPERIENCED"


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "topic"


def leaf(title, what, classification=LEARNED, how=None, when=None, why=None, evidence=None, related=None):
    sections = {"what": what}
    if why:
        sections["why"] = why
    if how:
        sections["how"] = how
    if when:
        sections["when"] = when
    node = {
        "slug": slugify(title),
        "title": title,
        "kind": "topic",
        "short_overview": what,
        "experience_classification": classification,
        "children": [],
        "sections": sections,
    }
    if evidence:
        node["sections"]["evidence"] = evidence
    if related:
        node["related"] = related
    return node


def branch(title, overview, children, classification=None, sections=None):
    node = {
        "slug": slugify(title),
        "title": title,
        "kind": "topic",
        "short_overview": overview,
        "children": children,
    }
    if classification:
        node["experience_classification"] = classification
    if sections:
        node["sections"] = sections
    return node


def dedupe_slugs(nodes):
    """Ensure sibling slugs are unique (append -2, -3... on collision),
    and recurse into children. Mutates in place."""
    seen = {}
    for n in nodes:
        base = n["slug"]
        if base in seen:
            seen[base] += 1
            n["slug"] = f"{base}-{seen[base]}"
        else:
            seen[base] = 1
        if n.get("children"):
            dedupe_slugs(n["children"])
    return nodes


# ======================================================================
# SYSTEM DESIGN (P0_PROMPT.txt Section 10)
# ======================================================================

def build_system_design_requirements():
    return branch("Requirements", "What a system must do, how well, and under what constraints — decided before any design work starts.", [
        leaf("Functional Requirements", "What the system must actually do — the observable behaviors a user or another system can call and depend on (e.g. 'POST /customers creates a customer').", CURRENT,
             how="Captured as concrete, testable statements, not vague goals. This project's CustomerController endpoints are its functional requirements made real.",
             evidence=["app/src/main/java/com/example/customer/CustomerController.java"]),
        leaf("Non-Functional Requirements", "Quality attributes a system must have regardless of specific feature: latency, availability, security, cost, observability — the 'how well', not the 'what'.", LEARNED,
             how="Stated as measurable targets (e.g. p99 latency, uptime %) so they can be tested, not left as adjectives like 'fast' or 'scalable'."),
        leaf("Scale", "The expected volume (requests/sec, data size, concurrent users) a design must handle — determines whether a simple design suffices or a more complex one is justified.", LEARNED,
             how="Estimate real numbers before designing (back-of-envelope: requests/day / seconds/day = avg QPS, plus a peak multiplier) rather than assuming 'web scale' by default."),
        leaf("Constraints", "Fixed boundaries a design must work within — budget, team size, existing infrastructure, compliance, deadline — that are not requirements but shape which requirements are even achievable.", CURRENT,
             how="This project's own constraints (single-operator budget, no paid infra beyond Railway/Vercel free-ish tiers, no enterprise identity provider) directly shaped its architecture (H2 in-memory DB instead of managed Postgres for the Customer app, no auth layer yet)."),
        leaf("SLO/SLA Concepts", "SLI (a measured indicator, e.g. latency) -> SLO (an internal target for that indicator) -> SLA (an external, often contractual, commitment built on an SLO).", LEARNED),
        leaf("Acceptance Criteria", "The explicit, checkable conditions that decide whether a requirement is actually satisfied — the bridge between 'what we want' and 'can we prove it's done'.", CURRENT,
             how="This project's own Acceptance Contract (agent/acceptance_contract.py) formalizes exactly this idea for AI-driven changes: requirement_id, expected_observable_effect, required_gates, allowed_terminal_outcomes.",
             related=["acceptance-contracts"],
             evidence=["agent/acceptance_contract.py"]),
    ])


def build_system_design_apis():
    return branch("APIs", "The contracts through which independently-deployed systems (or a frontend and backend) communicate.", [
        leaf("REST", "An architectural style using HTTP verbs (GET/POST/PUT/DELETE) over resource-shaped URLs, with each request self-contained (stateless).", CURRENT,
             how="This project's Customer app exposes REST endpoints (GET /customers/{id}, POST /customers) using Spring Boot's @RestController.",
             evidence=["app/src/main/java/com/example/customer/CustomerController.java"]),
        leaf("GraphQL", "A query language letting a client request exactly the fields it needs in one round trip, resolved server-side by field-level resolvers instead of fixed endpoint shapes.", LEARNED,
             how="Trades REST's simple caching/tooling for flexible, precise queries — better suited when clients have very different data needs (e.g. mobile vs. web) than when one shape serves everyone."),
        leaf("Contracts", "An explicit, versioned agreement (types, required/optional fields, error shapes) between an API and its callers, checked mechanically rather than left as a mutual assumption.", LEARNED),
        leaf("Validation", "Rejecting a malformed or unsafe request before it reaches business logic, with a clear error rather than a confusing downstream failure.", CURRENT,
             how="This project's Customer entity uses Jakarta Bean Validation (spring-boot-starter-validation) to reject invalid input at the boundary.",
             evidence=["app/pom.xml"]),
        leaf("Versioning", "How an API evolves without breaking existing callers — via URL path (/v2/...), header, or strictly-additive changes only.", LEARNED),
        leaf("Idempotency", "A request that can be safely retried without causing a second effect — critical for any client that might resend a request after a timeout (was it applied or not?).", LEARNED,
             how="Typically implemented via a client-supplied idempotency key the server deduplicates on, or by designing the operation itself to be naturally repeatable (e.g. 'set X to 5' vs. 'add 5 to X')."),
        leaf("Error Handling", "Returning a specific, actionable error (status code + machine-readable reason) instead of a generic failure, so a caller (human or another system) can react correctly.", CURRENT,
             how="This project's own qa-evaluator explicitly requires a specific failure reason to reach the caller (e.g. RepoToolError re-raised as MCP's ToolError) rather than a generic message — the same principle applied to AI tool design as to API design.",
             related=["independent-qa-evaluation"]),
    ])


def build_system_design_networking():
    return branch("Networking", "The layers a request travels through between a client and a server, and where each kind of failure/latency actually happens.", [
        leaf("DNS", "Translates a hostname (e.g. agentic-platform-backend-production.up.railway.app) into an IP address before any connection can be made — the first, often-overlooked point of failure or latency.", LEARNED,
             how="This project hit a real DNS failure: a Cloudflare Quick Tunnel registered successfully at the edge but its hostname never resolved in public DNS — confirmed via direct queries to Cloudflare's own resolver, not guessed.",
             related=["production-verification"]),
        leaf("TCP", "A reliable, ordered, connection-oriented transport protocol underlying HTTP — establishes a connection (three-way handshake) before any data flows.", LEARNED),
        leaf("TLS", "Encrypts and authenticates a connection (the 'S' in HTTPS) using a certificate proving the server's identity — a custom domain isn't fully live until its own certificate is provisioned.", CURRENT,
             how="This project's custom domain (agentic.karthikdevadoss.com) had its DNS configured but certificate provisioning was still pending — directly observed via a real TLS handshake failure (SEC_E_WRONG_PRINCIPAL), not assumed."),
        leaf("HTTP", "The application-layer protocol (request/response, methods, status codes, headers) almost all web APIs are built on.", CURRENT,
             how="Every route in this project's own Starlette backend (agent/web_server.py) and Spring Boot Customer app is an HTTP handler."),
        leaf("Proxy", "An intermediary that forwards requests on behalf of a client or server — used for caching, load balancing, TLS termination, or reaching a network the client can't reach directly.", CURRENT,
             how="This project reached its own event-ledger Postgres instance over a public TCP proxy (Railway's private DATABASE_URL isn't reachable from a laptop), and Cloudflare/ngrok tunnels were used as reverse proxies for temporary public access.",
             related=["event-ledger"]),
        leaf("Load Balancer", "Distributes incoming requests across multiple server instances for capacity and fault tolerance — not currently needed at this project's single-instance scale.", LEARNED),
        leaf("Timeout", "An explicit limit on how long to wait for a response before giving up — without one, a hung dependency can hang every caller indefinitely.", CURRENT,
             how="This project found a real bug where the Target Application panel could load forever because fetch() has no built-in timeout — fixed with an explicit Promise.race 8-second timeout.",
             related=["ai-guessing-and-failure"]),
        leaf("Retry", "Re-attempting a failed request, usually with backoff, when the failure is likely transient — must be paired with idempotency to be safe.", CURRENT,
             how="This project's event ledger retries a failed remote insert via a local outage spool with idempotent (ON CONFLICT DO NOTHING) retry, so a retry can never create a duplicate row.",
             related=["event-ledger"]),
    ])


def build_system_design_compute():
    return branch("Compute", "The runtime resources (processes, threads, CPU, memory) a program actually executes on.", [
        leaf("Process", "An OS-level unit of execution with its own memory space — this project's Spring Boot app and its Python agent run as separate processes.", CURRENT),
        leaf("Thread", "A unit of execution within a process, sharing its memory — Spring Boot's embedded Tomcat handles each HTTP request on its own thread by default.", LEARNED),
        leaf("CPU", "The physical resource actually executing instructions — a bottleneck when work is computation-heavy (e.g. embedding generation) rather than I/O-bound.", LEARNED),
        leaf("Memory", "RAM available to a process — a JVM's heap size, or a Python process's working set, both bounded by real memory the host actually has.", LEARNED, related=["java-jvm-memory"]),
        leaf("JVM", "The Java Virtual Machine — compiles Java bytecode to native execution, manages memory (heap/garbage collection) and threading for this project's Spring Boot Customer app.", CURRENT,
             how="This project's app/ directory is a real Spring Boot 4.1.1 / Java 17 application running on a real JVM, compiled and tested via Maven (mvnw).",
             evidence=["app/pom.xml"]),
        leaf("Concurrency", "Multiple logical tasks making progress over the same time period — via threads, async I/O, or separate processes — each with different tradeoffs for shared-state safety.", CURRENT,
             how="This project's Starlette backend uses async request handlers plus background threads (for run execution) and a lock-guarded background sync trigger for the event ledger spool, to avoid blocking the fast synchronous telemetry path.",
             related=["event-ledger"]),
    ])


def build_system_design_databases():
    return branch("Databases", "Systems of record for persistent, structured data — how it's stored, queried, and kept consistent.", [
        leaf("Relational DB", "Stores data in tables with defined schemas and relationships, queried via SQL — this project uses H2 (in-memory, for the Customer app demo) and Postgres (durable, for the event ledger).", CURRENT,
             evidence=["app/pom.xml", "infra/event-ledger/schema.sql"]),
        leaf("Oracle", "A widely-used enterprise relational database — not used anywhere in this project's own code; general knowledge only.", LEARNED),
        leaf("JDBC", "Java's standard low-level API for connecting to and querying a relational database — JPA is built on top of it.", CURRENT,
             how="Spring Data JPA (used by this project's Customer app) uses JDBC underneath via Hibernate."),
        leaf("JPA", "Java Persistence API — an ORM standard mapping Java objects to relational rows, implemented here by Hibernate via Spring Data JPA.", CURRENT,
             how="This project's Customer entity/CustomerRepository use Spring Data JPA directly.",
             evidence=["app/pom.xml", "app/src/main/java/com/example/customer/"]),
        leaf("Transactions", "A group of database operations that either all succeed or all roll back together (ACID) — prevents a partial, inconsistent write from ever being visible.", LEARNED),
        leaf("Indexing", "A data structure (typically a B-tree) letting the database find rows without scanning the whole table — the standard fix for a slow query on a large table.", LEARNED),
        leaf("Connection Pooling", "Reuses a fixed set of already-open database connections across requests instead of opening/closing one per request — opening a real DB connection is expensive.", CURRENT,
             how="Spring Boot defaults to HikariCP as its connection pool whenever spring-boot-starter-data-jpa is on the classpath, as it is in this project's Customer app, even without explicit pool configuration.",
             evidence=["app/pom.xml"],
             related=["hikaricp", "pool-sizing"]),
        leaf("Replication", "Copying a database's data to one or more additional nodes for read scaling and/or failover — not used in this project's current single-instance setup.", LEARNED),
        leaf("Partitioning", "Splitting a large table's data across multiple physical segments (by range, hash, etc.) so no single segment grows unbounded — a scale technique this project's current data volume doesn't yet need.", LEARNED),
    ])


def build_system_design_caching():
    return branch("Caching", "Storing a cheap-to-read copy of expensive-to-compute or expensive-to-fetch data, at the cost of it potentially going stale.", [
        leaf("Redis", "An in-memory key-value store commonly used for caching, sessions, and pub/sub — not used anywhere in this project's own code; general knowledge only.", LEARNED),
        leaf("Cache-Aside", "The application checks the cache first; on a miss, it reads the real source, then populates the cache for next time — the most common caching pattern.", LEARNED),
        leaf("TTL", "Time-to-live — an expiration after which a cached value is considered stale and must be refreshed, bounding how wrong a cache can be.", LEARNED),
        leaf("Invalidation", "Actively removing/updating a cached value the moment its source changes, rather than waiting for TTL expiry — famously one of the two hard problems in computer science.", CURRENT,
             how="This project's own PDF book cache (learn_pdf.py) invalidates by content hash of the canonical Learn tree rather than a fixed TTL, so a stale book is never served after Learn content genuinely changes.",
             related=["pdf-generation"]),
        leaf("Consistency", "How quickly and reliably a cache's value matches its underlying source of truth after a write — a real tradeoff against caching's whole performance benefit.", LEARNED),
    ])


def build_system_design_distributed():
    return branch("Distributed Systems", "Systems whose components run on separate machines/processes and communicate over an unreliable network — different failure assumptions than a single process.", [
        leaf("Availability", "The fraction of time a system successfully responds to requests — often traded against consistency under network partition (CAP theorem).", LEARNED),
        leaf("Consistency", "Whether every reader sees the same (and most recent) data at the same time — strong consistency is expensive across a network; many real systems choose eventual consistency deliberately.", LEARNED),
        leaf("Retry", "See System Design -> Networking -> Retry — the same idempotency-paired principle applies across service boundaries.", LEARNED, related=["retry"]),
        leaf("Idempotency", "See System Design -> APIs -> Idempotency — critical at scale, since network partitions make 'did that request actually land?' a routine question, not an edge case.", LEARNED, related=["idempotency"]),
        leaf("Queues", "A durable buffer decoupling a producer from a consumer, so the consumer can process work at its own pace and survive being temporarily down.", LEARNED),
        leaf("Kafka", "A distributed, partitioned, replicated log used as a high-throughput event streaming/queueing backbone — not used anywhere in this project's own code; general knowledge only.", LEARNED),
        leaf("Event-Driven Architecture", "Components react to events (facts that already happened) rather than being directly called — this project's own event ledger is a lightweight, single-table instance of the same core idea (append-only, consumers read from it independently).", CURRENT,
             how="agent/event_ledger.py's delivery_events table is an append-only log every part of this platform (Dashboard, Usage, Learn's knowledge-candidate pipeline) reads from independently, rather than services calling each other directly.",
             related=["event-ledger"]),
    ])


def build_system_design_security():
    return branch("Security", "Protecting a system's data, identity, and actions from unauthorized access or use.", [
        leaf("Authentication", "Verifying who is making a request (login, tokens, API keys) — not yet implemented anywhere in this project's own Customer app (explicitly out of scope so far).", PLANNED),
        leaf("Authorization", "Deciding what an already-authenticated identity is allowed to do — distinct from authentication, and the concept this project's risk_policy.py applies to AI actions rather than human identities (what is this agent allowed to auto-execute).", CURRENT,
             how="agent/risk_policy.py deterministically gates auto-execution by risk/complexity, structurally separate from the reasoning it gates — the same 'authorization is a separate deterministic decision' principle as classic app authorization.",
             related=["human-role-and-approval-matrix"]),
        leaf("JWT", "A signed, self-contained token (JSON Web Token) commonly used to carry identity/claims between services without a shared session store — not used anywhere in this project's own code; general knowledge only.", LEARNED),
        leaf("Spring Security", "Spring's authentication/authorization framework — not used in this project's Customer app (no auth layer implemented yet); general knowledge only.", LEARNED),
        leaf("Cognito", "AWS's managed identity/user-pool service — not used anywhere in this project; general knowledge only.", LEARNED),
        leaf("FusionAuth", "A self-hostable identity/auth server — not used anywhere in this project; general knowledge only.", LEARNED),
        leaf("Secrets", "Credentials/keys that must never be committed, logged, or exposed to a model's output — this project actively enforces this (redact_secrets(), .env gitignored, key rotation after one real exposure).", CURRENT,
             how="tools.redact_secrets() deterministically redacts credential-shaped values before anything reaches a log, trace, or the event ledger — applied at the shared boundary so every consumer benefits automatically.",
             evidence=["docs/PROJECT_STATE.json (agent/.env / rotated key entries)"]),
        leaf("Least Privilege", "Granting only the access actually needed for a task, nothing more — this project's qa-evaluator subagent is a direct application: Read/Glob/Grep/Bash/WebFetch only, Write/Edit explicitly disallowed.", CURRENT,
             how="`.claude/agents/qa-evaluator.md`'s disallowedTools (Write/Edit/NotebookEdit) enforces least privilege structurally for an AI subagent, the same principle as scoping a service account's IAM permissions.",
             related=["independent-qa-evaluation"],
             evidence=[".claude/agents/qa-evaluator.md"]),
    ])


def build_system_design_reliability(deep_topics_by_id):
    children = [
        leaf("Failure Modes", "The specific, enumerable ways a system can go wrong — naming them explicitly (timeout vs. crash vs. wrong-data vs. partial-success) is what makes them detectable and preventable rather than a vague 'something broke'.", CURRENT, related=["ai-guessing-and-failure"]),
        leaf("Retry", "See Networking -> Retry.", LEARNED, related=["retry"]),
        leaf("Timeout", "See Networking -> Timeout.", LEARNED, related=["timeout"]),
        leaf("Circuit Breaker", "Stops calling a dependency that's already failing repeatedly, for a cooldown period, instead of piling up more failing/slow calls on top of an already-struggling system.", LEARNED),
    ]
    if "production-verification" in deep_topics_by_id:
        children.append(deep_topics_by_id["production-verification"])
    else:
        children.append(leaf("Deployment Verification", "Confirming a deployed change's specific requested effect is genuinely live — not just that the server responds.", CURRENT))
    children.append(leaf("Rollback", "Reverting to a known-good prior version when a deployment is found to be bad — requires that prior version to actually still be deployable/available.", LEARNED))
    children.append(leaf("Recovery", "Restoring correct operation after a failure — for data, this means a tested restore path, not just a backup that has never been proven to actually restore.", CURRENT,
             how="This project's event ledger has a manual on-demand portable backup that has exported real rows successfully, but a restore has explicitly NOT yet been tested — an honestly-tracked open gap, not assumed solved.",
             evidence=["docs/PROJECT_STATE.json (missing_capabilities: PITR/tested restore drill)"]))
    return branch("Reliability", "Keeping a system correct and available in the presence of real failures, not just under ideal conditions.", children)


def build_system_design_observability(deep_topics_by_id):
    children = [
        leaf("Logs", "Discrete, timestamped records of what happened — this project's own safe trace (tool name, sanitized input, status) is a deliberately narrow log designed to never leak secrets or file contents.", CURRENT),
        leaf("Metrics", "Aggregated numeric measurements over time (counts, durations, rates) — this project's agent/metrics.py captures tool-call/RAG-index/retrieval events as structured, queryable data.", CURRENT,
             evidence=["agent/metrics.py"]),
        leaf("Traces", "Following one request's full path across components/services — this project doesn't yet have distributed tracing (single-process scope so far), though its event ledger's run_id/session_id fields serve a similar correlating purpose within one run.", LEARNED),
        leaf("Correlation IDs", "A single ID (run_id, session_id) attached to every event belonging to one logical operation, so its full trajectory can be reconstructed later from otherwise-independent log lines.", CURRENT,
             how="This project's event ledger reconstructs a full run's trajectory purely from its run_id, proven by a dedicated test.",
             related=["event-ledger"]),
    ]
    if "event-ledger" in deep_topics_by_id:
        children.append(deep_topics_by_id["event-ledger"])
    return branch("Observability", "Being able to answer 'what is this system actually doing right now, and what did it just do' from real captured evidence, not from guessing.", children)


def build_system_design_cloud_deployment():
    return branch("Cloud / Deployment", "Getting code from a repository into a running, reachable production instance, and knowing whether that actually worked.", [
        leaf("AWS", "Amazon Web Services — not used anywhere in this project (Railway and Vercel are used instead); general knowledge only.", LEARNED),
        leaf("Lambda", "AWS's serverless compute service (functions triggered by events, no server to manage) — not used in this project; general knowledge only.", LEARNED),
        leaf("API Gateway", "AWS's managed entry point for routing, throttling, and authenticating API requests to backend services (e.g. Lambda) — not used in this project; general knowledge only.", LEARNED),
        leaf("CloudFormation", "AWS's infrastructure-as-code service, defining cloud resources declaratively in templates — not used in this project; general knowledge only.", LEARNED),
        leaf("Docker", "Packages an application and its dependencies into a portable container image — this project's platform backend is built and deployed as a real Docker image.", CURRENT,
             how="A real deploy-time defect was found and fixed this way: Docker's COPY from a Windows build host didn't preserve the POSIX executable bit on mvnw, causing a real production failure, fixed with an explicit RUN chmod +x.",
             evidence=["Dockerfile", "docs/LESSONS.md"]),
        leaf("Jenkins", "A widely-used self-hosted CI/CD automation server — not used in this project; general knowledge only.", LEARNED),
        leaf("CI/CD", "Continuous Integration/Continuous Deployment — automatically building, testing, and deploying on every change. This project currently deploys manually (`railway up`) rather than via an automated pipeline.", PLANNED),
        leaf("Railway", "The cloud platform this project's Customer app, event-ledger Postgres, and platform backend are actually deployed on.", CURRENT,
             how="Chosen because the platform backend is a long-running process with in-memory state, SSE streams, and background threads that shells out to git/mvnw/the railway CLI — none of which fits a serverless function, making a persistent container host the correct fit.",
             evidence=["docs/DECISIONS.md", "docs/RESOURCE_REGISTRY.md"]),
        leaf("Production Verification", "See AI-Assisted Engineering -> Production Verification for the full deep topic — confirming a deployed change's requested effect is genuinely live, not just that the deploy command exited 0.", CURRENT, related=["production-verification"]),
    ])


def build_system_design_performance():
    return branch("Performance", "How fast a system responds and how much load it can carry, and where the actual bottleneck is.", [
        leaf("Latency", "How long a single request takes end to end — the metric a user directly feels.", LEARNED),
        leaf("Throughput", "How many requests a system can handle per unit time — can be high even when individual latency is mediocre, via concurrency.", LEARNED),
        leaf("Concurrency", "See Compute -> Concurrency — the mechanism that lets throughput exceed what serial processing alone could achieve.", LEARNED, related=["concurrency"]),
        leaf("Bottlenecks", "The single slowest real constraint limiting a system's overall throughput/latency — optimizing anything else first wastes effort.", LEARNED,
             how="This project found a real one directly: a LOW-confidence cost estimate undershot a real run's actual token spend by 126% because investigation cost (reading a file + a real compile) dominated a supposedly tiny requirement — the estimate model's blind spot, not the run itself, was the actual bottleneck to fix.",
             evidence=["docs/LESSONS.md"]),
        leaf("DB Connections", "See Databases -> Connection Pooling — a frequent real bottleneck once concurrent request volume exceeds the pool size.", LEARNED, related=["connection-pooling"]),
        leaf("Pool Sizing", "How many pooled connections/threads to actually allocate — too few queues requests unnecessarily, too many can overwhelm the downstream resource (e.g. the database itself).", LEARNED,
             how="HikariCP's own guidance (Spring Boot's default pool) is that a smaller pool sized close to (core_count * 2) + effective_spindle_count often outperforms an oversized one, since contention/context-switching costs exceed the benefit of more connections beyond the real bottleneck resource's own capacity."),
        leaf("Resource Cost", "The actual dollar/compute cost of a design choice — this project's own token/cost economics work (ledger-backed, versioned pricing) is a direct real-world instance of tracking this rigorously instead of guessing.", CURRENT, related=["token-cost-economics"]),
    ])


def build_system_design_domain(deep_topics_by_id):
    node = branch(
        "System Design",
        "How to design software systems that meet real functional and non-functional requirements under real constraints — from a single request's network path through to production deployment and reliability.",
        [
            build_system_design_requirements(),
            build_system_design_apis(),
            build_system_design_networking(),
            build_system_design_compute(),
            build_system_design_databases(),
            build_system_design_caching(),
            build_system_design_distributed(),
            build_system_design_security(),
            build_system_design_reliability(deep_topics_by_id),
            build_system_design_observability(deep_topics_by_id),
            build_system_design_cloud_deployment(),
            build_system_design_performance(),
        ],
    )
    node["kind"] = "domain"
    return node


# ======================================================================
# AI-ASSISTED SOFTWARE ENGINEERING (P0_PROMPT.txt Sections 11-14)
# ======================================================================

APPROVAL_INTERRUPTION_CLARIFICATION_ESCALATION = [
    leaf(
        "Approval",
        "The AI recognizes an action exceeds its delegated authority and asks a human before doing it — known in advance, not a reaction to something going wrong.",
        CURRENT,
        why="Capability is not authority: an AI agent can be technically able to do something (deploy, spend budget, touch production) without being authorized to decide that it should, right now, without a human saying yes.",
        how="A deterministic, code-level gate (not a prompt instruction) decides what needs approval before any agent reasoning happens — this project's risk_policy.py classifies risk/complexity and only then decides auto-execute vs. 'needs Owner authorization', so the same model can't argue its way around the gate.",
        when="Material ambiguity, destructive/irreversible actions, security-boundary changes, spending above budget authority, production actions with real customer impact.",
        evidence=["agent/risk_policy.py", "docs/CONSTITUTION.md §11"],
    ),
    leaf(
        "Interruption",
        "A human observes the AI drifting or creating risk mid-run and stops or reorients it — reactive, not planned in advance like approval.",
        LEARNED,
        why="Even a well-scoped task can go wrong in ways no upfront gate anticipated — scope creep, a misunderstood requirement, or a tool being used in an unintended way.",
        how="Requires the human to actually have visibility into what the AI is doing while it's doing it (a live event stream, a visible run log) — interruption is impossible if the only evidence arrives after the fact.",
        when="When observed behavior diverges from the actual intent, even if no explicit rule was technically broken.",
    ),
    leaf(
        "Clarification",
        "The AI recognizes its own requirement or context is insufficient to proceed correctly, and asks rather than guessing.",
        CURRENT,
        why="Guessing under genuine ambiguity is exactly the failure mode this project's own AI-guessing-and-failure lessons document repeatedly — a wrong assumption stated confidently is worse than a question.",
        how="Distinguish 'I could technically proceed with an assumption' from 'the ambiguity materially changes what correct looks like' — only the second genuinely warrants stopping to ask.",
        when="Requirement text is genuinely ambiguous, evidence needed to proceed correctly doesn't exist yet, or a decision belongs to the human by policy (see Human Role).",
        related=["ai-guessing-and-failure"],
    ),
    leaf(
        "Escalation",
        "The AI recognizes a decision belongs outside its authority entirely (not just 'I'm unsure', but 'this isn't mine to decide') and routes it to a human rather than acting or even asking a narrow clarifying question.",
        LEARNED,
        why="Some decisions (business purpose, ethical boundaries, architecture direction, legal/financial commitments) are categorically the human's to make regardless of how confident or capable the AI is.",
        how="A recognizable trigger list (see Human Role -> Human Owns) rather than case-by-case judgment calls, so escalation is consistent rather than arbitrary.",
        when="Business-purpose questions, ethical/dharmic uncertainty, legal/customer commitments, architecture-direction changes, anything the Owner has reserved by policy.",
        related=["human-role-and-approval-matrix"],
    ),
]

AI_FAILURE_MODE_TOPICS_WITH_EVIDENCE = {
    # slug-ish key -> (title, real_project_example, evidence)
    "hallucinated-apis-wrong-assumptions": (
        "Hallucinated APIs / Wrong Framework Assumptions",
        "An implementer confidently claimed 'propose_source_change only allows .java files' (false — verified by reading the real source). Separately, a Spring Boot 4.1.1 test suite assumed com.fasterxml.jackson.databind classes that had actually moved to tools.jackson.* in Jackson 3.x, plus TestRestTemplate/AutoConfigureMockMvc were not on this exact classpath — settled in minutes by mvn dependency:tree, not by guessing from training-data memory of Spring Boot 3.x.",
        ["docs/ARCHITECTURE_V2_EVALUATION_PLAN.md (Trial #1 attempt-1 entry)", "app/pom.xml + resolved dependency:tree"],
    ),
    "false-completion-self-evaluation-optimism": (
        "False Completion / Self-Evaluation Optimism",
        "Workbench reported 'Deployment: VERIFIED (HTTP 200)' while the real Customer App still showed old content — HTTP 200 proved the server was reachable, not that the requested content had actually changed.",
        ["docs/LESSONS.md", "agent/web_server.py::_decide_deployment_outcome"],
    ),
    "deployment-races": (
        "Deployment Races",
        "A deploy-wait loop exited early on a Railway CLI 'Online' status that actually described the PREVIOUS deployment still serving traffic while the new one built in the background — a real activation race, not a hypothetical one.",
        ["docs/LESSONS.md"],
    ),
    "environment-mismatch": (
        "Environment Mismatch",
        "Docker's COPY from a Windows build host silently dropped mvnw's POSIX executable bit, causing a real deploy-time permission-denied failure that only manifested in the container, not locally. Separately, Python's zoneinfo raised ZoneInfoNotFoundError for Europe/Berlin on this Windows machine because Windows ships no system IANA tz database.",
        ["docs/LESSONS.md"],
    ),
    "weak-tests": (
        "Weak Tests",
        "This project's own testing states used to collapse 'no test files exist yet' into the same label as 'this genuinely can't be tested' (NOT_APPLICABLE) — hiding an actionable coverage gap behind a label that sounded like a deliberate, correct decision.",
        ["agent/web_server.py::_determine_testing_state", "docs/LESSONS.md"],
    ),
    "context-and-authorization-assumptions": (
        "Authorization Assumptions",
        "A custom qa-evaluator subagent was assumed to be registered simply because its definition file existed and was committed — it was not actually invokable in two separate long-running sessions that predated the file, only confirmed working in a genuinely fresh session (ACT-006).",
        ["docs/ACTION_QUEUE.json (ACT-006)"],
    ),
    "incorrect-cost-estimates": (
        "Incorrect Cost Estimates",
        "A LOW-confidence pre-run token/cost estimate (3,000-9,000 tokens) undershot a real run's actual usage by 126%, because investigation cost (reading a file + a real compile) dominated a supposedly tiny requirement's real spend.",
        ["docs/LESSONS.md"],
    ),
    "multi-agent-coordination-errors": (
        "Multi-Agent Coordination Errors",
        "A benchmark trial designed to elicit an UNKNOWN verdict from an independent evaluator instead produced a well-evidenced FAIL, because the missing-evidence criterion was conclusively rule-out-able (provably absent from full git history) rather than genuinely unreachable by the evaluator's tools — a trial-design flaw between orchestrator and evaluator roles, not an evaluator defect.",
        ["docs/ARCHITECTURE_V2_EVALUATION_PLAN.md (Trial #3 section)"],
    ),
}

AI_FAILURE_MODE_GENERIC = [
    "Ambiguous Requirements", "Missing Context", "Stale Documentation",
    "Long-Task Drift", "Context Loss", "Scope Explosion",
    "Security Blind Spots", "Prompt Injection", "Tool-Output Misunderstanding",
]


def build_ai_failure_modes(deep_topics_by_id):
    children = []
    if "ai-guessing-and-failure" in deep_topics_by_id:
        children.append(deep_topics_by_id["ai-guessing-and-failure"])
    for key, (title, example, evidence) in AI_FAILURE_MODE_TOPICS_WITH_EVIDENCE.items():
        children.append(leaf(
            title,
            f"A real failure mode this project directly encountered and root-caused, not a hypothetical.",
            CURRENT,
            how="Detected by independently re-checking the actual claim against real source/runtime evidence rather than trusting a prior statement (including the AI's own).",
            evidence=evidence,
        ))
        children[-1]["sections"]["real_incidents"] = example
    for title in AI_FAILURE_MODE_GENERIC:
        children.append(leaf(
            title,
            "A recognized, general AI-agent failure category — real and well-documented in the field, but not yet directly evidenced by a specific incident in this project's own history.",
            LEARNED,
            how="Prevented by independent verification against real evidence, deterministic gates outside the model's own reasoning, and asking for clarification rather than guessing under genuine ambiguity.",
        ))
    return branch(
        "AI Failure Modes",
        "The recurring ways an AI agent can be confidently wrong, organized by category, so they can be detected and prevented rather than discovered painfully in production.",
        children,
        classification=CURRENT,
    )


def build_human_role(deep_topics_by_id):
    human_owns = leaf(
        "Human Owns",
        "Purpose, business intent, priorities, budget, architecture boundaries, risk tolerance, security/production authority, ethical boundaries, and final accountability — decisions capability alone does not transfer.",
        CURRENT,
        why="An AI agent can be technically capable of making a change without being the right authority to decide whether that change SHOULD be made — capability is not authority (docs/CONSTITUTION.md).",
        evidence=["docs/CONSTITUTION.md §11"],
    )
    ai_may_execute = leaf(
        "AI May Execute Within Authority",
        "Repository investigation, implementation, bounded refactoring, test generation, evidence collection, documentation, debugging hypotheses, isolated experiments — the HOW, once the human has set the WHAT and WHY.",
        CURRENT,
        why="Routine, reversible, well-specified execution work is exactly where delegating to an AI agent creates real leverage without transferring a decision that was never the AI's to make.",
    )
    children = [human_owns, ai_may_execute] + APPROVAL_INTERRUPTION_CLARIFICATION_ESCALATION
    if "human-role-and-approval-matrix" in deep_topics_by_id:
        children.append(deep_topics_by_id["human-role-and-approval-matrix"])
    return branch(
        "Human Role, Approval, and Interruption",
        "The explicit division between what a human owns and what an AI may execute within delegated authority, and the four distinct mechanisms (approval, interruption, clarification, escalation) governing when a human must be involved.",
        children,
        classification=CURRENT,
    )


def build_ai_assisted_engineering_domain(deep_topics_by_id):
    core_topics_order = [
        "acceptance-contracts", "independent-qa-evaluation",
        "evaluator-uncertainty-and-verdict-design", "skills-and-subagents",
        "token-cost-economics",
    ]
    children = []
    for tid in core_topics_order:
        if tid in deep_topics_by_id:
            children.append(deep_topics_by_id[tid])
    for title in [
        "Requirements with AI", "Context Engineering", "Repository Grounding",
        "Prompting", "Agent Loops", "Deterministic Gates", "Testing / Evals",
        "Deployment", "Debugging", "Multi-Agent Systems",
        "Progressive Autonomy", "Continuous Learning",
    ]:
        children.append(leaf(
            title,
            f"A core practice area in building software with AI agents; general knowledge and, where this project's own code demonstrates it, real project experience.",
            LEARNED,
        ))
    children.append(build_human_role(deep_topics_by_id))
    children.append(build_ai_failure_modes(deep_topics_by_id))
    node = branch(
        "AI-Assisted Software Engineering",
        "How to build software WITH AI agents responsibly: what the AI should decide vs. execute, how to define success before implementation starts, how to independently verify results, and how to recognize and prevent AI failure modes.",
        children,
        classification=CURRENT,
    )
    node["kind"] = "domain"
    return node


# ======================================================================
# MIGRATE EXISTING CATALOG (learn-data.json, 15 sections / 127 topics)
# ======================================================================

def migrate_reference_catalog(learn_data):
    domains = []
    for section in learn_data["sections"]:
        topics = []
        for t in section["topics"]:
            node = leaf(
                t["name"],
                t["definition"],
                classification=None,
            )
            # Preserve legacy status badge as metadata, not a content substitute.
            node["status"] = t.get("evidence_status")
            if t.get("related"):
                node["related"] = t["related"]
            topics.append(node)
        domains.append(branch(section["title"], f"Reference index — {len(topics)} topic(s) migrated from the original Learn catalog.", topics))
        domains[-1]["kind"] = "domain"
        domains[-1]["slug"] = section["id"]  # preserve original stable ids
    return domains


# ======================================================================
# FLATTEN DEEP-DIVE TOPICS FOR RE-USE (learn-deep-topics.json)
# ======================================================================

def convert_deep_topic(t):
    node = {
        "slug": t["id"],
        "title": t["name"],
        "kind": "topic",
        "short_overview": t["what"],
        "experience_classification": t.get("experience_classification", LEARNED),
        "children": [],
        "sections": {
            "what": t.get("what"),
            "why": t.get("why"),
            "how": t.get("how"),
            "when": t.get("when"),
            "real_experience": t.get("our_experience"),
            "development_steps": t.get("development_steps") or [],
            "failure_modes": t.get("failures_lessons") or [],
            "evidence": t.get("evidence") or [],
        },
        "related": t.get("related_topics") or [],
    }
    if t.get("interview"):
        iv = t["interview"]
        node["sections"]["interview"] = {
            "question": iv.get("question"),
            "short_answer": iv.get("short_answer"),
            "deep_answer": iv.get("deep_answer"),
            "real_incident_story": iv.get("real_incident_story"),
        }
    # Drop empty-list/None sections so we never render fake filler.
    node["sections"] = {k: v for k, v in node["sections"].items() if v not in (None, [], "")}
    return node


def load_deep_topics_flat():
    deep = json.loads((WEB_DIR / "learn-deep-topics.json").read_text(encoding="utf-8"))
    flat = {}
    for domain in deep["domains"]:
        for t in domain["topics"]:
            flat[t["id"]] = convert_deep_topic(t)
    return flat


# ======================================================================
# MAIN BUILD
# ======================================================================

def git_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:
        return "UNKNOWN"


def count_nodes(nodes):
    total = 0
    deep = 0
    domains = 0
    exp_counts = {CURRENT: 0, LEARNED: 0, PLANNED: 0,
                  "REAL_PROFESSIONAL_EXPERIENCE": 0, "STUDY_SCENARIO": 0}
    def walk(ns, depth):
        nonlocal total, deep, domains
        for n in ns:
            if n.get("kind") == "domain":
                domains += 1
            else:
                total += 1
                sections = n.get("sections") or {}
                if len(sections) >= 4:
                    deep += 1
                cls = n.get("experience_classification")
                if cls in exp_counts:
                    exp_counts[cls] += 1
            if n.get("children"):
                walk(n["children"], depth + 1)
    walk(nodes, 0)
    return {
        "total_reference_topics": total,
        "total_deep_topics": deep,
        "total_domains": domains,
        **{f"{k.lower()}_topics": v for k, v in exp_counts.items()},
    }


def main():
    learn_data = json.loads((WEB_DIR / "learn-data.json").read_text(encoding="utf-8"))
    deep_topics_by_id = load_deep_topics_flat()

    domains = migrate_reference_catalog(learn_data)

    system_design = build_system_design_domain(deep_topics_by_id)
    ai_assisted = build_ai_assisted_engineering_domain(deep_topics_by_id)

    # Master Interview Book V1 (P0_PROMPT.txt "JOB-FIRST MASTER INTERVIEW
    # BOOK"): imported here, not at module scope, so interview_topics.py's
    # own top-level `from build_learn_tree import leaf, branch` succeeds
    # against a fully-initialized module rather than a circular partial one.
    import interview_topics
    new_deep = interview_topics.all_new_deep_topics()
    system_design["children"].extend([
        new_deep["system-design-capacity-estimation"],
        new_deep["cap-theorem-pacelc"],
        new_deep["system-design-interview-methodology"],
    ])
    ai_assisted["children"].extend([
        new_deep["ai-context-engineering-tokenization"],
        new_deep["ai-agent-tool-calling-loop"],
    ])
    interview_broad_domains = interview_topics.build_broad_domains(new_deep)

    # Attach the remaining un-placed deep topics (testing-truthfulness-states)
    # to a Testing / Quality domain so nothing from the existing deep-dive
    # seed is ever lost.
    placed_ids = {"production-verification", "event-ledger", "acceptance-contracts",
                  "independent-qa-evaluation", "evaluator-uncertainty-and-verdict-design",
                  "human-role-and-approval-matrix", "ai-guessing-and-failure",
                  "skills-and-subagents", "token-cost-economics"}
    remaining = [v for k, v in deep_topics_by_id.items() if k not in placed_ids]
    domains_final = [system_design, ai_assisted] + interview_broad_domains + domains
    if remaining:
        testing_domain = branch("Testing / Quality (Deep Dive)", "Evidence-backed deep topics about this project's own testing truthfulness.", remaining)
        testing_domain["kind"] = "domain"
        domains_final.append(testing_domain)

    dedupe_slugs(domains_final)

    metrics = count_nodes(domains_final)
    metrics["total_domains"] = len(domains_final)

    tree = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "metrics": metrics,
        "domains": domains_final,
    }

    out_path = WEB_DIR / "learn-tree.json"
    out_path.write_text(json.dumps(tree, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out_path} — {metrics}")


if __name__ == "__main__":
    main()
