"""
Testing & Verification Architecture V1 — deterministic Test Impact
Analysis (docs/TESTING_ARCHITECTURE_V1.md §C/§D). First practical TIA
implementation for this repository.

Input: a set of changed file paths (from a real `git diff`). Output: an
explicit, explainable selection of which test suites to run and why, plus
which large unrelated suites were intentionally skipped and why —
"explainable/deterministic... file/module mapping, dependency
relationships, explicit architecture rules, test-to-feature mapping," per
this task's own instruction. No ML/predictive selection.

Deliberately reuses agent/change_risk.py's classification rather than
re-deriving risk from scratch.
"""

import re
from dataclasses import dataclass, field

import change_risk

ALL_JAVA_MODULE_TESTS = "ALL_JAVA_MODULE_TESTS"  # sentinel: run every Java test in app/
FULL_REGRESSION = "FULL_REGRESSION"  # sentinel: fail-closed, run everything in every language


@dataclass
class ImpactSelection:
    java_tests: list = field(default_factory=list)  # explicit test class names, or [ALL_JAVA_MODULE_TESTS]
    python_tests: list = field(default_factory=list)
    node_tests: list = field(default_factory=list)
    playwright_specs: list = field(default_factory=list)
    reasons: list = field(default_factory=list)  # human-readable "why selected" lines
    skipped: list = field(default_factory=list)  # human-readable "why skipped" lines
    fail_closed: bool = False
    fail_closed_reason: str = ""
    classification: change_risk.ChangeClassification = None


# Explicit file -> Java test class mapping, by naming convention, checked
# against the real files that exist in this repository (see
# docs/TESTING_ARCHITECTURE_V1.md for the full table). Kept as a literal
# dict rather than a generic "guess *Test.java exists" convention because
# several source files map to a shared integration test class, and a
# guessed name that doesn't exist would silently select nothing.
JAVA_FILE_TO_TESTS = {
    "Customer.java": ["CustomerControllerIntegrationTest", "CustomerServiceTest"],
    "CustomerController.java": ["CustomerControllerIntegrationTest"],
    "CustomerService.java": ["CustomerServiceTest", "CustomerControllerIntegrationTest"],
    "CustomerRepository.java": ["CustomerControllerIntegrationTest", "CustomerServiceTest"],
    "CustomerEmailUpdateRequest.java": ["CustomerControllerIntegrationTest"],
    "CustomerPreference.java": ["CustomerPreferenceControllerIntegrationTest", "CustomerPreferenceServiceTest"],
    "CustomerPreferenceController.java": ["CustomerPreferenceControllerIntegrationTest"],
    "CustomerPreferenceService.java": ["CustomerPreferenceServiceTest", "CustomerPreferenceControllerIntegrationTest"],
    "CustomerPreferenceRepository.java": ["CustomerPreferenceControllerIntegrationTest"],
    "CustomerPreferenceResponse.java": ["CustomerPreferenceControllerIntegrationTest"],
    "CustomerPreferenceUpdateRequest.java": ["CustomerPreferenceControllerIntegrationTest"],
    "CustomerPreferenceUpdatedEvent.java": ["CustomerPreferenceEventFlowIntegrationTest"],
    "CustomerPreferenceEventConsumer.java": ["CustomerPreferenceEventFlowIntegrationTest"],
    "NotificationChannel.java": ["CustomerPreferenceControllerIntegrationTest"],
    # TriageScenarioAIntegrationTest added to ContractPlan/ContractPlanService/
    # ContractPlanStatus (Base Architecture V3 Section 8, real symbol/caller
    # analysis, docs/CODE_INTELLIGENCE_EVALUATION.md): TriageScenarioAService's
    # "fixed" path calls ContractPlanService.enroll() directly (a real,
    # grep-verified caller, not a hypothetical one) -- a change to this file
    # that ContractPlanServiceTest's mocks miss but a real end-to-end run
    # would catch (as this session's own mutation testing proved both test
    # classes independently detect) deserves this real caller in its
    # selective-regression set, not just the fail-closed full suite.
    "ContractPlan.java": ["ContractPlanControllerIntegrationTest", "ContractPlanServiceTest", "TriageScenarioAIntegrationTest"],
    "ContractPlanController.java": ["ContractPlanControllerIntegrationTest"],
    "ContractPlanService.java": ["ContractPlanServiceTest", "ContractPlanControllerIntegrationTest", "TriageScenarioAIntegrationTest"],
    "ContractPlanRepository.java": ["ContractPlanControllerIntegrationTest"],
    "ContractPlanEnrollRequest.java": ["ContractPlanControllerIntegrationTest"],
    "ContractPlanResponse.java": ["ContractPlanControllerIntegrationTest"],
    "ContractPlanStatus.java": ["ContractPlanControllerIntegrationTest", "ContractPlanServiceTest", "TriageScenarioAIntegrationTest"],
    "ContractPlanCacheService.java": ["ContractPlanCacheIntegrationTest"],
    "RedisCacheConfig.java": ["ContractPlanCacheIntegrationTest"],
    "AppointmentController.java": ["AppointmentControllerIntegrationTest"],
    "AppointmentAvailabilityClient.java": ["AppointmentAvailabilityIntegrationTest", "AppointmentControllerIntegrationTest"],
    "AppointmentAvailabilityConfig.java": ["AppointmentAvailabilityIntegrationTest", "AppointmentControllerIntegrationTest"],
    "AppointmentAvailabilityService.java": ["AppointmentAvailabilityIntegrationTest", "AppointmentControllerIntegrationTest"],
    "AppointmentAvailabilityStatus.java": ["AppointmentAvailabilityIntegrationTest", "AppointmentControllerIntegrationTest"],
    "AppointmentAvailabilityResult.java": ["AppointmentAvailabilityIntegrationTest", "AppointmentControllerIntegrationTest"],
    "DemoAppointmentProviderController.java": ["AppointmentControllerIntegrationTest"],
    "SecurityConfig.java": ["SecurityIntegrationTest"],
    "DemoJwtIssuer.java": ["SecurityIntegrationTest"],
    "DemoAuthController.java": ["SecurityIntegrationTest"],
    "OutboxEvent.java": ["CustomerPreferenceEventFlowIntegrationTest"],
    "OutboxEventEnvelope.java": ["CustomerPreferenceEventFlowIntegrationTest"],
    "OutboxEventRepository.java": ["CustomerPreferenceEventFlowIntegrationTest"],
    "OutboxPublisher.java": ["CustomerPreferenceEventFlowIntegrationTest"],
    "ProcessedEvent.java": ["CustomerPreferenceEventFlowIntegrationTest"],
    "ProcessedEventRepository.java": ["CustomerPreferenceEventFlowIntegrationTest"],
    "KafkaMessagingConfig.java": ["CustomerPreferenceEventFlowIntegrationTest"],
    "CustomerApplication.java": ["CustomerApplicationTests"],
}

# Cross-cutting mandatory triggers — added on top of the direct file
# mapping regardless of blast_radius, per this task's own "change-aware
# mandatory rules" instruction (§F). These fire on a PATTERN, not a single
# file, so a new file added to an existing package still triggers them.
MANDATORY_TRIGGERS = [
    (re.compile(r'^app/src/main/java/com/example/customer/security/'), ["SecurityIntegrationTest"],
     "security config changed -> full auth matrix"),
    (re.compile(r'^app/src/main/resources/db/migration/'), ["PostgresFlywayIntegrationTest"],
     "Flyway migration changed -> real Postgres migration check"),
    (re.compile(r'^app/src/main/java/com/example/customer/(messaging|outbox)/'), ["CustomerPreferenceEventFlowIntegrationTest"],
     "Kafka/outbox changed -> event flow + idempotency/dead-letter tests"),
    (re.compile(r'^app/src/main/java/com/example/customer/cache/'), ["ContractPlanCacheIntegrationTest"],
     "Redis cache layer changed -> cache hit/miss/invalidation/down tests"),
]

# Playwright specs that exercise the deployed agentic-platform-backend
# pages this project actually has E2E coverage for today.
#
# BL-012 (2026-09-20): the Customer App's OWN frontend
# (app/src/main/resources/static/index.html) used to have NO dedicated
# Playwright spec at all -- see docs/TESTING_ARCHITECTURE_V1.md's open
# gaps and docs/ACTION_QUEUE.json's TESTING-ARCH-V1-GAPS item. BL-013
# (same day) added the first one, e2e/customer-app-update-email.spec.js,
# as a real side effect of proving the Update Email feature works in a
# real browser -- mapped here so that origin is now closed, not left
# undiscovered by this file's own skip-reason logic below. Honest scope
# note: this spec covers the login -> edit-email -> save -> reload flow
# specifically, not every page/control on index.html -- a future change
# to an unrelated part of the page (customer creation, preferences, admin
# views) would still only be covered by this one spec's incidental
# overlap, not a purpose-built one. Broader golden-path coverage for this
# page remains real, separate future work, not claimed as done here.
FRONTEND_PATH_TO_SPECS = {
    "agent/web/workbench.html": ["e2e/workbench-catalogue.spec.js"],
    "agent/web/workbench.js": ["e2e/workbench-catalogue.spec.js"],
    "agent/web/workbench.css": ["e2e/workbench-catalogue.spec.js"],
    "agent/web/usage.html": ["e2e/usage.spec.js"],
    "agent/web/usage.js": ["e2e/usage.spec.js"],
    "agent/web/learn.html": ["e2e/learn.spec.js"],
    "agent/web/learn.js": ["e2e/learn.spec.js"],
    "app/src/main/resources/static/index.html": ["e2e/customer-app-update-email.spec.js"],
}

# Paths that, if changed, mean "this cannot be confidently bounded by V1's
# deterministic rules" — dependency/build/infra/authorization files where
# even 'run everything for this one app' isn't clearly sufficient (e.g. a
# pom.xml change can affect what compiles at all; a CI workflow change
# needs the workflow itself exercised, not just app tests).
FAIL_CLOSED_PATTERNS = [
    re.compile(r'^app/pom\.xml$'),
    re.compile(r'^\.github/workflows/'),
    re.compile(r'^agent/risk_policy\.py$'),
    re.compile(r'^(Dockerfile|app/Dockerfile)$'),
    re.compile(r'^\.gitattributes$'),
]


def _basename(path: str) -> str:
    return path.replace("\\", "/").rsplit("/", 1)[-1]


def analyze(paths) -> ImpactSelection:
    """The Change Impact Analysis + Selective Test Plan step, combined.
    Never raises. Deterministic: the same input always produces the same
    selection."""
    paths = [p.replace("\\", "/") for p in paths]
    selection = ImpactSelection()
    selection.classification = change_risk.classify_change(paths)

    if not paths:
        selection.skipped.append("no changed files -> no tests selected")
        return selection

    for pattern in FAIL_CLOSED_PATTERNS:
        matched = [p for p in paths if pattern.search(p)]
        if matched:
            selection.fail_closed = True
            selection.fail_closed_reason = (
                f"changed path(s) {matched} affect build/CI/authorization definitions that "
                "this V1's deterministic rules cannot safely bound to a partial test set"
            )
            return selection

    if selection.classification.has_unrecognized_paths:
        selection.fail_closed = True
        selection.fail_closed_reason = (
            f"unrecognized path(s) with no matching classification rule: "
            f"{selection.classification.unrecognized_paths} -- cannot confidently bound impact"
        )
        return selection

    java_tests = set()
    java_changed = False
    for p in paths:
        if not p.startswith("app/src/main/java/"):
            continue
        java_changed = True
        name = _basename(p)
        mapped = JAVA_FILE_TO_TESTS.get(name)
        if mapped:
            java_tests.update(mapped)
            selection.reasons.append(f"{p} -> {mapped} (direct file/test mapping)")
        else:
            selection.reasons.append(f"{p} -> no direct mapping known; covered by cross-module/full-suite fallback below")

    for pattern, tests, reason in MANDATORY_TRIGGERS:
        if any(pattern.search(p) for p in paths):
            before = set(java_tests)
            java_tests.update(tests)
            if java_tests - before:
                selection.reasons.append(f"mandatory rule: {reason} -> added {sorted(java_tests - before)}")

    radius = selection.classification.blast_radius
    if java_changed and radius in ("CROSS_MODULE", "SYSTEM"):
        selection.java_tests = [ALL_JAVA_MODULE_TESTS]
        selection.reasons.append(
            f"overall blast_radius={radius} across changed Java files -> a single shared/cross-cutting "
            "component changed; no bounded subset of test classes can safely stand in for the whole "
            "customer-app suite, so ALL Java tests are selected instead of guessing which callers are affected"
        )
    elif java_tests:
        selection.java_tests = sorted(java_tests)
    elif java_changed:
        # A Java file changed but has no known mapping and didn't trigger
        # cross-module escalation (e.g. a brand-new file with no test yet)
        # -- the honest, safe answer is the whole module, not silence.
        selection.java_tests = [ALL_JAVA_MODULE_TESTS]
        selection.reasons.append("Java file(s) changed with no known direct test mapping -> ALL Java tests selected as the safe default")

    any_java_test_changed = any(p.startswith("app/src/test/java/") for p in paths)
    if any_java_test_changed and not selection.java_tests:
        selection.java_tests = [ALL_JAVA_MODULE_TESTS]
        selection.reasons.append("test-only change with no corresponding main-code impact tracked -> run the whole Java suite to confirm the test itself is valid")

    for p in paths:
        specs = FRONTEND_PATH_TO_SPECS.get(p)
        if specs:
            selection.playwright_specs.extend(s for s in specs if s not in selection.playwright_specs)
            selection.reasons.append(f"{p} -> {specs}")

    if any(p.startswith("app/src/main/resources/static/") for p in paths) and not selection.playwright_specs:
        selection.skipped.append(
            "app/src/main/resources/static/** changed but this repository has no dedicated Playwright "
            "spec for the Customer App's own frontend yet -- honest gap, not a silent pass "
            "(see docs/TESTING_ARCHITECTURE_V1.md/docs/ACTION_QUEUE.json)"
        )

    if any(p.startswith("agent/") and p.endswith(".py") for p in paths):
        selection.skipped.append(
            "Python agent/ changes were present but this V1 pass only implements Java Test Impact "
            "Analysis so far -- python-regression is not auto-selected; run it explicitly "
            "(python agent/dev_check.py python-regression) until Python TIA is built"
        )

    if ALL_JAVA_MODULE_TESTS not in selection.java_tests:
        if "CustomerPreferenceEventFlowIntegrationTest" not in selection.java_tests:
            selection.skipped.append("Kafka/outbox event-flow suite skipped -- no dependency path from the changed files")
        if "ContractPlanCacheIntegrationTest" not in selection.java_tests:
            selection.skipped.append("Redis cache suite skipped -- no dependency path from the changed files")
        if "PostgresFlywayIntegrationTest" not in selection.java_tests:
            selection.skipped.append("Postgres/Flyway migration suite skipped -- no dependency path from the changed files")

    return selection
