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
# real browser, covering only the login -> edit-email -> save -> reload
# flow specifically.
#
# BL-027 (2026-09-20) closed the broader gap those two items left open:
# e2e/customer-app-frontend.spec.js adds real coverage for the login gate
# (anonymous vs. USER vs. ADMIN view), the real USER cards (Overview,
# Account/Profile, Plan, Preferences, Appointments, Activity) actually
# rendering real data rather than staying stuck loading, a real
# Preferences write/read-after-reload flow, and real ADMIN list<->detail
# navigation + search. Both specs are mapped here so a change to
# index.html selects the full real coverage that exists today, not just
# the first, narrower spec.
# Sprint 15: ui-standards.spec.js checks the whole public surface at once --
# the shared 1200px shell, one body size, one h1 scale, a 12px legibility
# floor, and what is visible above a real browser fold. Every file that can
# move any of those has to be able to trigger it, which is why it is mapped
# from the shared stylesheets as well as from each page: the Owner's defects
# came from style.css and dashboard.css, not from the pages themselves.
_UI_STANDARDS = "e2e/ui-standards.spec.js"
# Sprint 16 added design-standards.spec.js and nothing mapped it, so the repo's
# own drift ratchet (test_test_impact_analysis.FrontendSpecMapDriftTestCase) went
# RED and stayed RED -- which is the guard working, not a nuisance. It measures
# the SAME nine public routes ui-standards.spec.js does, so every file that can
# move any of them maps to both.
_DESIGN_STANDARDS = "e2e/design-standards.spec.js"
# Two whole-surface sweeps, both of which crawl every public route rather than
# one page: link-integrity checks that every rendered <a href> resolves, and
# golden-journey checks each page renders its own real identity rather than
# merely returning 200. Any page or the shared navigation can break either.
_LINK_INTEGRITY = "e2e/link-integrity.spec.js"
_GOLDEN_JOURNEY = "e2e/golden-journey.spec.js"
# Sprint 17 adds three more whole-surface sweeps, each asserting a property that
# any public page can break: horizontal overflow and console errors at four
# widths; third-party font/tracker requests on load; and the public claims whose
# failure mode is a recruiter drawing a false conclusion.
_RESPONSIVE = "e2e/responsive-invariants.spec.js"
_THIRD_PARTY = "e2e/third-party-network.spec.js"
_COPY_CONTRACT = "e2e/copy-contract.spec.js"
# Gated OFF by default (VISUAL_REGRESSION=1), and still MAPPED rather than
# excluded: selecting a suite that self-skips costs nothing, and when the Owner
# does turn it on, the paths that can move a screenshot are already wired to it.
# Excluding it now would mean remembering to wire it later, which is the exact
# thing this map exists to stop depending on.
_VISUAL_REGRESSION = "e2e/visual-regression.spec.js"
_WHOLE_SURFACE = [_UI_STANDARDS, _DESIGN_STANDARDS, _LINK_INTEGRITY, _GOLDEN_JOURNEY,
                  _RESPONSIVE, _THIRD_PARTY, _COPY_CONTRACT, _VISUAL_REGRESSION]

FRONTEND_PATH_TO_SPECS = {
    # Sprint 14: the recruiter-facing home page and the durable-agent case
    # study. nav.js is mapped here too -- it renders the canonical navigation
    # that home.spec.js asserts, so a nav change must be able to trigger it.
    "agent/web/home.html": ["e2e/home.spec.js"] + _WHOLE_SURFACE,
    "agent/web/case-study-durable-agent.html": ["e2e/home.spec.js"] + _WHOLE_SURFACE,
    "agent/web/nav.js": ["e2e/home.spec.js", "e2e/nav-consistency.spec.js"] + _WHOLE_SURFACE,
    # The shared shell and type scale. A one-line change in either of these
    # moves every page at once -- which is exactly what happened in Sprint 15.
    "agent/web/style.css": [_UI_STANDARDS, _DESIGN_STANDARDS, _RESPONSIVE, _THIRD_PARTY,
                            _VISUAL_REGRESSION, "e2e/nav-consistency.spec.js"],
    "agent/web/dashboard.css": [_UI_STANDARDS, _DESIGN_STANDARDS, _RESPONSIVE, _VISUAL_REGRESSION],
    "agent/web/showcase.css": [_UI_STANDARDS, _DESIGN_STANDARDS, _RESPONSIVE, _VISUAL_REGRESSION],
    "agent/web/showcase.js": [_UI_STANDARDS, _DESIGN_STANDARDS, "e2e/interview-walkthrough.spec.js", _LINK_INTEGRITY],
    # Sprint 17: showcase.html had no entry at all, so the page that carries the
    # densest technical evidence on the public site could be edited without
    # selecting a single browser spec.
    "agent/web/showcase.html": ["e2e/interview-walkthrough.spec.js"] + _WHOLE_SURFACE,
    # The Interview Walkthrough section renders this file's real contents, and
    # a link in it that 404s is exactly the AEQ-022 defect class.
    "docs/INTERVIEW_WALKTHROUGH.yaml": ["e2e/interview-walkthrough.spec.js", _LINK_INTEGRITY],
    "agent/web/dashboard.html": [_UI_STANDARDS, _DESIGN_STANDARDS, _LINK_INTEGRITY],
    "agent/web/standing-interview.html": _WHOLE_SURFACE,
    "agent/web/workbench.html": ["e2e/workbench-catalogue.spec.js"] + _WHOLE_SURFACE,
    "agent/web/workbench.js": ["e2e/workbench-catalogue.spec.js"],
    "agent/web/workbench.css": ["e2e/workbench-catalogue.spec.js", _UI_STANDARDS,
                                _DESIGN_STANDARDS, _RESPONSIVE],
    "agent/web/usage.html": ["e2e/usage.spec.js"] + _WHOLE_SURFACE,
    "agent/web/usage.js": ["e2e/usage.spec.js", _UI_STANDARDS, _DESIGN_STANDARDS],
    "agent/web/usage.css": [_UI_STANDARDS, _DESIGN_STANDARDS, _RESPONSIVE, _VISUAL_REGRESSION],
    # Sprint 17: Triage and Ask the Codebase were both entirely absent from this
    # map. Triage is one of the three pages the Owner sends recruiters to.
    "agent/web/triage.html": _WHOLE_SURFACE,
    "agent/web/triage.js": [_GOLDEN_JOURNEY, _LINK_INTEGRITY],
    "agent/web/triage.css": [_UI_STANDARDS, _DESIGN_STANDARDS, _RESPONSIVE, _VISUAL_REGRESSION],
    "agent/web/triage-b.html": [_GOLDEN_JOURNEY, _LINK_INTEGRITY],
    "agent/web/triage-b.js": [_GOLDEN_JOURNEY],
    "agent/web/triage-c.html": [_GOLDEN_JOURNEY, _LINK_INTEGRITY],
    "agent/web/triage-c.js": [_GOLDEN_JOURNEY],
    "agent/web/ask-codebase.html": ["e2e/ask-codebase.spec.js"] + _WHOLE_SURFACE,
    "agent/web/ask-codebase.js": ["e2e/ask-codebase.spec.js", _LINK_INTEGRITY],
    "agent/web/ask-codebase.css": ["e2e/ask-codebase.spec.js", _UI_STANDARDS,
                                   _DESIGN_STANDARDS, _RESPONSIVE],
    # The zero-LLM query surface behind /ask-codebase. Same precedent as
    # agent/jd_match.py below: a backend validation change is exactly what the
    # rendered-result spec has to catch.
    "agent/ask_codebase.py": ["e2e/ask-codebase.spec.js"],
    "agent/web/learn.html": ["e2e/learn.spec.js"],
    "agent/web/learn.js": ["e2e/learn.spec.js"],
    # Sprint 13 / BL-097: JD Match. The backend module is mapped too, because a
    # validation change is exactly what the rendered-result spec must catch.
    "agent/web/jd-match.html": ["e2e/jd-match.spec.js"],
    "agent/web/jd-match.js": ["e2e/jd-match.spec.js"],
    "agent/web/jd-match.css": ["e2e/jd-match.spec.js"],
    "agent/jd_match.py": ["e2e/jd-match.spec.js"],
    "app/src/main/resources/static/index.html": [
        "e2e/customer-app-update-email.spec.js",
        "e2e/customer-app-frontend.spec.js",
    ],
    # Sprint 17: /profile's privacy is enforced by ROUTE REGISTRATION, not by
    # any file under agent/web/ -- so the one spec that proves a recruiter
    # cannot reach the old resume page could not be selected by editing the
    # thing that would break it. The two whole-surface sweeps belong here for
    # the same reason: they assert what the public route table actually serves.
    "agent/web_server.py": ["e2e/profile.spec.js", _GOLDEN_JOURNEY, _LINK_INTEGRITY],
}

# Specs deliberately NOT selected by any source path, each with the real reason.
#
# This exists because "unmapped" previously meant two different things that
# looked identical -- a spec nobody had wired up yet, and a spec that must
# never be selected automatically. Sprint 17 split them: anything absent from
# FRONTEND_PATH_TO_SPECS must appear here with a reason, or the drift ratchet in
# test_test_impact_analysis.py fails. Adding an entry here to silence that test
# is the failure mode it exists to prevent; the reason has to be real.
INTENTIONALLY_UNMAPPED_SPECS = {
    "e2e/pdf.spec.js": (
        "Covers /learn's Download Complete Book control, and /learn is not a "
        "public route -- it is registered only when PRIVATE_SURFACES_ENABLED is "
        "set (agent/web_server.py). The spec self-skips otherwise, so selecting "
        "it from a public-page change would only ever produce skips."
    ),
    "e2e/workbench-real-acceptance.spec.js": (
        "Submits a REAL requirement through the real Workbench pipeline, which "
        "commits, pushes and deploys a real change to the production Customer "
        "App. It is a deliberate, operator-initiated acceptance run -- never "
        "something a file edit should be able to trigger. Tagged `live` in "
        "docs/testing-matrix.json."
    ),
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
