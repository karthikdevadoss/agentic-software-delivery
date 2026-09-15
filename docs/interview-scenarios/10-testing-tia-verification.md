# Interview Scenario: Test Impact Analysis & Selective Regression — Explainable, Fail-Closed

Derived from the actual implementation: `agent/change_risk.py`, `agent/test_impact_analysis.py`, `agent/verify_change.py`, and `docs/TESTING_ARCHITECTURE_V1.md`.

## Business Why

An AI-assisted delivery pipeline that can propose and apply real code
changes needs a real answer to "how much should I test this change" —
running the *entire* test universe for a one-line CSS fix wastes minutes
per change and trains everyone to stop reading the output; running too
little risks shipping a real regression. The answer has to be
**explainable** (a human can see exactly why a test was or wasn't
selected) and **deterministic** (no ML/predictive black box) — this task
explicitly rejected a "smart" scoring model in favor of file-path
pattern rules and an explicit test-to-feature mapping.

## Architecture

```
git diff (real changed file paths)
   |
   v
change_risk.classify_change(paths)
   |-- per-file regex rules (first match wins), ordered specific -> general
   |-- returns: overall risk (LOW/MEDIUM/HIGH/CRITICAL),
   |            blast radius (LOCAL/MODULE/CROSS_MODULE/SYSTEM),
   |            unrecognized_paths (any file matching NO rule)
   v
test_impact_analysis.analyze(paths)
   |-- reuses change_risk's classification, does not re-derive risk
   |-- explicit JAVA_FILE_TO_TESTS mapping (file -> real, verified test class names)
   |-- mandatory cross-cutting triggers (security/Flyway/Kafka/Redis -> broader selection)
   |-- ANY unrecognized path -> FULL_REGRESSION (fail-closed, whole batch, not diluted)
   v
verify_change.build_plan / execute
   |-- prints the real changed files, classification, and selected-vs-skipped
   |   test plan WITH REASONS, before running anything
   |-- executes via the exact same real mvnw/unittest/node commands
   |   agent/dev_check.py already wraps -- no second execution mechanism
   |-- writes machine-readable evidence to agent/.verify_change_evidence/*.json
```

## The Classification Rules: Specific Before General

```python
RULES = [
    (r'^agent/risk_policy\.py$', "CRITICAL", "SYSTEM", "agent authorization / risk policy"),
    (r'^app/src/main/java/com/example/customer/security/', "HIGH", "CROSS_MODULE", "Spring Security / JWT auth config"),
    (r'^app/src/main/resources/db/migration/', "HIGH", "SYSTEM", "Flyway DB migration"),
    ...
    (r'^app/src/main/java/com/example/customer/(controller|service|repository|model|dto|integration)/', "MEDIUM", "MODULE", "business logic change"),
    (r'^app/src/test/', "LOW", "LOCAL", "test-only change"),
    (r'^app/src/main/resources/static/', "LOW", "LOCAL", "static frontend (HTML/CSS/JS)"),
    ...
]
```

Rules are ordered **first-match-wins, most-specific-first** — a file
under `security/` must be classified `HIGH`/`CROSS_MODULE` before it
could ever fall through to the general `MEDIUM`/`MODULE` "business
logic" bucket a few rules later. Each risk/blast-radius pairing was
grounded in a real, concrete example rather than invented in the
abstract: an isolated visible CSS fix is `LOW`/`LOCAL`; a real business
rule change is `MEDIUM`/`MODULE`; a DB migration or `SecurityConfig`
change is `HIGH`; `agent/risk_policy.py` itself (the Workbench's own
authorization gate) is `CRITICAL`/`SYSTEM` — a change to the thing that
decides what's safe to auto-execute is, definitionally, the highest-risk
class of change this repository can have.

## Fail-Closed: the Property That Actually Matters

```python
FULL_REGRESSION = "FULL_REGRESSION"  # sentinel: fail-closed, run everything in every language
```

An unrecognized path — `pom.xml`, a CI workflow file, `risk_policy.py`,
or literally any file that matches none of the ordered regex rules —
forces the **entire batch** to `FULL_REGRESSION`, never diluted by other
known-safe files changed in the same commit. This is the one property
that makes the whole system trustworthy: a selective-testing system that
silently under-tests an unrecognized file is worse than no selective
testing at all, because it looks safe while quietly not being safe.

## Explicit Test Mapping, Not a Guessed Convention

```python
JAVA_FILE_TO_TESTS = {
    "Customer.java": ["CustomerControllerIntegrationTest", "CustomerServiceTest"],
    "CustomerController.java": ["CustomerControllerIntegrationTest"],
    "CustomerService.java": ["CustomerServiceTest", "CustomerControllerIntegrationTest"],
    ...
}
```

Kept as a literal dict, checked against the real test classes that exist
in this repository — deliberately **not** a generic "guess
`*Test.java` exists for this source file" convention, because several
source files legitimately map to a *shared* integration test class
(changing `Customer.java` should also re-run the controller test that
exercises it end to end), and a guessed name that doesn't actually exist
would silently select nothing rather than erroring loudly.

## Real Dogfooding, Not Simulated

`verify_change.py --base <ref>` was run against this project's own real
commits — e.g., a Preferences/Appointment commit correctly classified
`HIGH`/`CROSS_MODULE` (because `SecurityConfig` + `application.properties`
were both in the diff), correctly escalated to "ALL Java tests" rather
than a narrow selection, and genuinely ran the real always-on smoke
class followed by the real full `mvnw test` — both real invocations
exiting 0, with evidence JSON written to disk for later inspection. Not
a simulated demo run: the actual selective-regression engine, exercised
against the actual history of the repository it protects.

## Design Trade-offs

- **Deterministic file-pattern rules (chosen)** vs. a learned/predictive
  test-selection model: explainability was the explicit priority for
  this task — a human (or an AI proposing a change) can read exactly
  which rule matched and why, rather than trusting an opaque score.
  Historical/statistical intelligence was deliberately deferred, not
  rejected outright, as a possible future layer on top of this
  explainable baseline.
- **Fail-closed on any unrecognized path (chosen)** vs. best-effort
  partial selection: costs more test time on genuinely novel file types,
  but a testing system that can be silently wrong is a liability, not a
  convenience.
- **Reusing `change_risk`'s classification inside `test_impact_analysis`**
  rather than each module re-deriving its own risk notion — one source
  of truth for "how risky is this file," consumed by two different
  downstream decisions (what to test, and separately, what a human
  reviewer should pay closest attention to).

## What's Deliberately NOT Built Yet (Honest Open Items)

Per `docs/TESTING_ARCHITECTURE_V1.md`'s own "Open items" section: no
dedicated Playwright spec for the Customer App's own static frontend yet
(the single most valuable next addition); Test Impact Analysis is
Java-only today (a Python `agent/*.py` change is currently flagged into
the fail-closed full-regression path, not mapped to specific test
modules); `verify_change.py` is not wired into `.github/workflows/ci.yml`
as an authoritative gate (CI's own full suites remain sole authority,
deliberately not silently swapped without separate explicit approval);
no mutation/property/fuzz/performance/chaos tooling; per-run evidence
JSON exists but isn't yet aggregated across runs into first-pass-yield/
rework/cost metrics. Recorded honestly as `TESTING-ARCH-V1-GAPS` in
`docs/ACTION_QUEUE.json`, not silently dropped.

## Interview Questions This Answers

- "How would you avoid running the full test suite for every small
  change, without risking under-testing a risky one?"
- "What does 'fail-closed' mean in a testing/selection system, and why
  does it matter more than the selection logic being clever?"
- "Why choose deterministic pattern rules over a learned model for test
  selection?"
- "How do you prove a testing tool actually works, beyond unit-testing
  it in isolation?"
- "What would you build next, and why is it prioritized that way?"

## Live Demo / Evidence Links

- `agent/change_risk.py`, `agent/test_impact_analysis.py`, `agent/verify_change.py` (real source)
- `docs/TESTING_ARCHITECTURE_V1.md` (the full design write-up, including honest open items)
- `docs/ACTION_QUEUE.json`'s `TESTING-ARCH-V1-GAPS` entry
- `agent/.verify_change_evidence/*.json` (real per-run machine-readable evidence, gitignored)
