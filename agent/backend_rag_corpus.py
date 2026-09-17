"""
Curated document corpus for the backend-requirement RAG/MCP vertical slice.

Deliberately NOT the whole repository (see agent/rag_index.py for the
existing whole-repo index, used by the separate V3 CLI agent). This is a
small, explicitly-curated set of documents that materially help answer
one real question: "given a backend (Java/Spring) requirement, what
code/tests/architecture knowledge is relevant?" -- scoped to the one
supported backend scenario (agent/backend_catalogue.py's
customer_not_found_message operation and its surrounding
controller/service/repository/model/exception-handler/tests).

Adding a document here is a deliberate curation decision, not something
any code path does automatically -- see docs/DECISIONS.md.
"""

import dataclasses

SOURCE_CODE = "SOURCE_CODE"
TEST = "TEST"
ARCHITECTURE_DOC = "ARCHITECTURE_DOC"
INCIDENT_LESSON = "INCIDENT_LESSON"


@dataclasses.dataclass(frozen=True)
class CorpusDocument:
    source_path: str  # repo-relative
    source_type: str
    content_type: str  # "java" | "markdown" | "json" -- selects the chunker


CORPUS_DOCUMENTS = (
    CorpusDocument(
        "app/src/main/java/com/example/customer/controller/CustomerController.java",
        SOURCE_CODE, "java",
    ),
    CorpusDocument(
        "app/src/main/java/com/example/customer/service/CustomerService.java",
        SOURCE_CODE, "java",
    ),
    CorpusDocument(
        "app/src/main/java/com/example/customer/repository/CustomerRepository.java",
        SOURCE_CODE, "java",
    ),
    CorpusDocument(
        "app/src/main/java/com/example/customer/model/Customer.java",
        SOURCE_CODE, "java",
    ),
    CorpusDocument(
        "app/src/main/java/com/example/customer/exception/GlobalExceptionHandler.java",
        SOURCE_CODE, "java",
    ),
    CorpusDocument(
        "app/src/test/java/com/example/customer/service/CustomerServiceTest.java",
        TEST, "java",
    ),
    CorpusDocument(
        "app/src/test/java/com/example/customer/controller/CustomerControllerIntegrationTest.java",
        TEST, "java",
    ),
    CorpusDocument(
        "docs/ACTION_QUEUE.json",
        ARCHITECTURE_DOC, "json",
    ),
    CorpusDocument(
        "docs/WORKBENCH_RELIABILITY_GAP_ANALYSIS.md",
        ARCHITECTURE_DOC, "markdown",
    ),
    CorpusDocument(
        "docs/LESSONS.md",
        INCIDENT_LESSON, "markdown",
    ),

    # --- "Ask the Codebase" expansion (2026-09-17) -- a deliberate
    # curation decision, not automatic whole-repo indexing. The original
    # 10 documents above were scoped to one historical demo scenario
    # (customer_not_found_message) and could not answer the breadth of
    # real interview topics this project has evidence for. Adds the real
    # source files most directly asked about, plus every existing
    # docs/interview-scenarios/*.md write-up (already real, already
    # markdown -- chunked by the existing heading-boundary chunker with
    # zero new code). Python source (agent/*.py -- e.g. Test Impact
    # Analysis, the write/execution-tool boundary) is NOT chunked here:
    # no Python chunker exists yet (java/markdown/json only), so those
    # topics are covered via their own interview-scenario narrative docs
    # instead of raw source excerpts -- a real, disclosed scope limit,
    # not silently worked around.
    CorpusDocument(
        "app/src/main/java/com/example/customer/security/SecurityConfig.java",
        SOURCE_CODE, "java",
    ),
    CorpusDocument(
        "app/src/main/java/com/example/customer/security/WorkspaceAccessGuard.java",
        SOURCE_CODE, "java",
    ),
    CorpusDocument(
        "app/src/main/java/com/example/customer/outbox/OutboxPublisher.java",
        SOURCE_CODE, "java",
    ),
    CorpusDocument(
        "app/src/main/java/com/example/customer/messaging/CustomerPreferenceEventConsumer.java",
        SOURCE_CODE, "java",
    ),
    CorpusDocument(
        "app/src/main/java/com/example/customer/cache/ContractPlanCacheService.java",
        SOURCE_CODE, "java",
    ),
    CorpusDocument(
        "app/src/main/java/com/example/customer/integration/appointment/AppointmentAvailabilityClient.java",
        SOURCE_CODE, "java",
    ),
    CorpusDocument(
        "app/src/main/java/com/example/customer/service/ContractPlanService.java",
        SOURCE_CODE, "java",
    ),
    CorpusDocument(
        "app/src/main/java/com/example/customer/controller/AdminCustomerController.java",
        SOURCE_CODE, "java",
    ),
    CorpusDocument("docs/interview-scenarios/01-rbac-and-workspace-isolation.md", ARCHITECTURE_DOC, "markdown"),
    CorpusDocument("docs/interview-scenarios/02-postgres-search-pagination.md", ARCHITECTURE_DOC, "markdown"),
    CorpusDocument("docs/interview-scenarios/03-agentic-ai-software-delivery.md", ARCHITECTURE_DOC, "markdown"),
    CorpusDocument("docs/interview-scenarios/04-plan-enrollment-idempotency.md", ARCHITECTURE_DOC, "markdown"),
    CorpusDocument("docs/interview-scenarios/05-kafka-transactional-outbox.md", ARCHITECTURE_DOC, "markdown"),
    CorpusDocument("docs/interview-scenarios/06-redis-cache-aside.md", ARCHITECTURE_DOC, "markdown"),
    CorpusDocument("docs/interview-scenarios/07-appointment-resilience.md", ARCHITECTURE_DOC, "markdown"),
    CorpusDocument("docs/interview-scenarios/08-security-attack-matrix.md", ARCHITECTURE_DOC, "markdown"),
    CorpusDocument("docs/interview-scenarios/09-observability-production-debugging.md", ARCHITECTURE_DOC, "markdown"),
    CorpusDocument("docs/interview-scenarios/10-testing-tia-verification.md", ARCHITECTURE_DOC, "markdown"),
)
