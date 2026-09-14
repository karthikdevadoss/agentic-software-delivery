"""
Testing & Verification Architecture V1 — deterministic change risk /
blast-radius classification (docs/TESTING_ARCHITECTURE_V1.md §B).

Distinct from agent/risk_policy.py: that module classifies a Workbench
requirement's raw TEXT before any code exists, as a hard authorization
gate. This module classifies a set of ALREADY-CHANGED FILE PATHS (from a
real `git diff`), after implementation, to drive test selection — a
different question (how big is the blast radius of what changed) for a
different purpose (what to test), not a duplicate of that gate.

Deliberately simple, explainable, and file-path-pattern-based — no
ML/predictive scoring (per this task's own instruction: "start explainable
/deterministic... historical intelligence can come later").
"""

import re
from dataclasses import dataclass, field

RISK_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
BLAST_RADIUS_ORDER = ["LOCAL", "MODULE", "CROSS_MODULE", "SYSTEM"]


@dataclass
class FileClassification:
    path: str
    risk: str
    blast_radius: str
    label: str
    matched: bool = True


@dataclass
class ChangeClassification:
    risk: str
    blast_radius: str
    files: list = field(default_factory=list)
    unrecognized_paths: list = field(default_factory=list)

    @property
    def has_unrecognized_paths(self) -> bool:
        return bool(self.unrecognized_paths)


# Ordered rules: (regex, risk, blast_radius, label). First match wins per
# file. Order matters — more specific patterns must come before general
# ones (e.g. a security-package file must not fall through to the general
# "business logic" bucket).
#
# The paired examples this task itself gave were used directly where
# applicable: "CSS / isolated visible message: LOW + LOCAL", "business-
# rule change: MEDIUM + MODULE", "DB migration: HIGH", "SecurityConfig:
# HIGH/CRITICAL + CROSS_MODULE", "agent authorization: CRITICAL", "shared
# infrastructure/config: HIGH/SYSTEM".
RULES = [
    (r'^agent/risk_policy\.py$', "CRITICAL", "SYSTEM",
     "agent authorization / risk policy"),
    (r'^agent/(demo_catalogue|backend_catalogue|demo_execution|backend_execution|web_server)\.py$', "HIGH", "CROSS_MODULE",
     "Workbench execution/authorization pipeline"),
    (r'^app/src/main/java/com/example/customer/security/', "HIGH", "CROSS_MODULE",
     "Spring Security / JWT auth config"),
    (r'^app/src/main/resources/db/migration/', "HIGH", "SYSTEM",
     "Flyway DB migration"),
    (r'^\.github/workflows/', "HIGH", "SYSTEM",
     "CI pipeline definition"),
    (r'^app/pom\.xml$', "HIGH", "SYSTEM",
     "dependency / build definition"),
    (r'^(Dockerfile|app/Dockerfile)$', "HIGH", "SYSTEM",
     "deployment image definition"),
    (r'^app/src/main/resources/application[^/]*\.properties$', "HIGH", "CROSS_MODULE",
     "shared application configuration"),
    (r'^app/src/main/java/com/example/customer/exception/', "MEDIUM", "CROSS_MODULE",
     "shared exception handling (affects every endpoint's error response shape)"),
    (r'^app/src/main/java/com/example/customer/(messaging|outbox)/', "MEDIUM", "MODULE",
     "Kafka / event-driven messaging"),
    (r'^app/src/main/java/com/example/customer/cache/', "MEDIUM", "MODULE",
     "Redis cache-aside layer"),
    (r'^app/src/main/java/com/example/customer/(controller|service|repository|model|dto|integration)/', "MEDIUM", "MODULE",
     "business logic change"),
    (r'^app/src/test/', "LOW", "LOCAL",
     "test-only change"),
    (r'^app/src/main/resources/static/', "LOW", "LOCAL",
     "static frontend (HTML/CSS/JS)"),
    (r'^agent/test_.*\.py$', "LOW", "LOCAL",
     "Python test-only change"),
    (r'^agent/web/', "LOW", "LOCAL",
     "agentic-platform-backend frontend (HTML/CSS/JS)"),
    (r'^e2e/', "LOW", "LOCAL",
     "Playwright E2E spec"),
    (r'^agent/.*\.py$', "MEDIUM", "MODULE",
     "Python agentic-platform-backend business logic"),
    (r'^(docs/|.*\.md$)', "LOW", "LOCAL",
     "documentation"),
    (r'^\.claude/', "LOW", "LOCAL",
     "Claude Code project config"),
    (r'^\.gitignore$', "LOW", "LOCAL",
     "git ignore rules (repo hygiene only, no runtime effect)"),
]

_COMPILED_RULES = [(re.compile(pattern), risk, radius, label) for pattern, risk, radius, label in RULES]


def classify_file(path: str) -> FileClassification:
    """Classify one changed file path (posix-style, repo-relative).
    Never raises — an unrecognized path returns matched=False with
    risk/blast_radius both "UNKNOWN", which callers must treat as
    "cannot confidently bound," never as LOW."""
    normalized = path.replace("\\", "/")
    for pattern, risk, radius, label in _COMPILED_RULES:
        if pattern.search(normalized):
            return FileClassification(path=path, risk=risk, blast_radius=radius, label=label)
    return FileClassification(path=path, risk="UNKNOWN", blast_radius="UNKNOWN", label="unrecognized path — no rule matched", matched=False)


def classify_change(paths) -> ChangeClassification:
    """Classify a whole changed-file set. Overall risk/blast_radius is the
    MAX across all files (a change is only as safe as its riskiest touched
    file) — never averaged or diluted by unrelated small files in the same
    commit."""
    paths = list(paths)
    if not paths:
        return ChangeClassification(risk="LOW", blast_radius="LOCAL", files=[], unrecognized_paths=[])

    classifications = [classify_file(p) for p in paths]
    unrecognized = [c.path for c in classifications if not c.matched]

    known = [c for c in classifications if c.matched]
    if known:
        overall_risk = max((c.risk for c in known), key=RISK_ORDER.index)
        overall_radius = max((c.blast_radius for c in known), key=BLAST_RADIUS_ORDER.index)
    else:
        overall_risk, overall_radius = "UNKNOWN", "UNKNOWN"

    if unrecognized:
        # An unrecognized path can't be proven safe — never let known-safe
        # files dilute the overall verdict. This is the deterministic
        # "fail closed when impact cannot be confidently bounded" behavior.
        overall_risk, overall_radius = "UNKNOWN", "UNKNOWN"

    return ChangeClassification(
        risk=overall_risk, blast_radius=overall_radius,
        files=classifications, unrecognized_paths=unrecognized,
    )
