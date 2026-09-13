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
)
