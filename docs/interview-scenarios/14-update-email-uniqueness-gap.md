# Interview Scenario: Update Email — A Real Missing-Validation Gap Found In "Already Done" Code

Derived from the actual implementation: `app/src/main/java/com/example/customer/service/CustomerService.java`, `app/src/main/java/com/example/customer/exception/DuplicateEmailException.java`, `app/src/main/java/com/example/customer/repository/CustomerRepository.java`. This is the project's original, long-deferred "Update Email" ticket (`PUT /customers/{id}`) — the endpoint already existed and was already tested for the happy path, 400, and 404 cases, but had never been checked against its own acceptance contract's uniqueness requirement until this pass (2026-09-20, BL-013).

## Business Why

An energy customer can change the email address used for billing and
notifications. Two customers ending up bound to the same email address is
a real correctness problem, not a cosmetic one: notifications would be
misdelivered, and the email effectively becomes an ambiguous identity key
across two different customer records.

## Requirement

- Email must be a well-formed address (already enforced via Bean
  Validation before this pass).
- 404 if the target customer does not exist (already enforced).
- **Email must be unique across customers** — rejecting a value already in
  use by a *different* customer, while still allowing a customer to
  re-submit their own current email unchanged.
- The update is actually persisted (visible on a subsequent `GET`).
- No other existing Customer behavior changes.

## The Real Gap

`CustomerService.updateEmail()` already existed, was already covered by
unit and integration tests, and both `CustomerControllerIntegrationTest`
and `CustomerServiceTest` already carried the comment "the project's
original, long-deferred 'Update Email' ticket, finally implemented." But
reading the actual implementation against its own written acceptance
contract (`docs/ACTION_QUEUE.json`'s `PHASE-3-UPDATE-EMAIL-BACKEND-DEMO`
entry, which explicitly lists "email must be unique") showed the
uniqueness rule was never implemented — the method simply set the new
value and saved, with no collision check at all:

```java
// before
public Customer updateEmail(Long id, String newEmail) {
    Customer customer = getById(id);
    customer.setEmail(newEmail);
    return customerRepository.save(customer);
}
```

A second customer could silently take over a first customer's email with
a plain `PUT`, and no existing test caught it — every existing test only
exercised a single customer's own update, never two customers colliding.
This is a real, general interview point: "all tests pass" proves the
tests are green, not that the tests cover the actual acceptance contract.

## Java/Spring Implementation

```java
public Customer updateEmail(Long id, String newEmail) {
    Customer customer = getById(id);
    if (customerRepository.existsByEmailAndIdNot(newEmail, id)) {
        throw new DuplicateEmailException("Email already in use: " + newEmail);
    }
    customer.setEmail(newEmail);
    return customerRepository.save(customer);
}
```

`existsByEmailAndIdNot(email, id)` is a Spring Data derived query —
excluding the customer's own current row is what lets a customer
re-submit their own unchanged email without a false 409. `GlobalExceptionHandler`
maps `DuplicateEmailException` to a clean `409 CONFLICT` with a structured
`{"error": "..."}` body, mirroring the exact pattern this codebase already
used for `EnrollmentInProgressException` — a new, narrow exception type
per real conflict class, not a generic catch-all.

## Failure Cases (real, tested)

| Case | Status | Test |
|---|---|---|
| Malformed email | 400 | `updateEmail_withMalformedEmail_returns400WithFieldError` (pre-existing) |
| Customer not found | 404 | `updateEmail_forNonExistentCustomer_returns404` (pre-existing) |
| Email already used by another customer | **409** | `updateEmail_toAnotherRealCustomersEmail_returns409AndLeavesBothUnchanged` (new) |
| Re-submitting own current email | 200 (no-op) | `updateEmail_reSubmittingOwnCurrentEmail_stillReturns200` (new) |
| Valid new, unused email | 200, persisted | `updateEmail_persistsAndIsReturnedOnSubsequentGet` (pre-existing) |

## Testing

Real evidence, not claimed: full `app/` regression suite run before and
after this change — `mvn test`, 152 tests, 0 failures, 0 errors, 21
skipped (Docker-dependent tests, no Docker on this dev machine, same as
every other Testcontainers-backed test in this project). Baseline (before
this change) was 148 tests; the 4 new tests above account for the
difference. One unrelated, pre-existing flaky test
(`AppointmentAvailabilityIntegrationTest.downstream400_isNeverRetried_failsFastWithExactlyOneCall`,
a WireMock call-count race) was observed on one run and passed cleanly on
the next — confirmed via `git stash` as pre-existing and unrelated to
this change, not a regression introduced here.

## Design Trade-offs

- **Service-layer check vs. a DB unique constraint.** A `@Column(unique = true)`
  constraint on `Customer.email` would be a stronger last line of defense
  (same philosophy as `ContractPlan`'s partial unique index), but was
  deliberately NOT added in this pass: `createCustomer()` also has no
  uniqueness enforcement today, and adding a DB-level constraint would
  silently change `POST /customers`' behavior too — out of this ticket's
  scope ("Update Email"), and a decision that deserves its own explicit
  review rather than riding in on an unrelated fix.
- **Exclude-self via `IdNot` rather than compare-then-skip in Java.** Doing
  the comparison in the query (`existsByEmailAndIdNot`) is one round trip
  and lets the database's own case/collation rules decide equality,
  rather than a Java `.equals()` that could quietly diverge from what the
  database considers a duplicate.

## Interview Questions This Answers

- "How do you find a bug in code that's already fully tested?" — read the
  implementation against its own written acceptance contract, not just
  against its own test file; a test suite only proves what someone
  thought to test.
- "Why a dedicated exception class instead of a generic conflict check
  inline in the controller?" — consistency with this codebase's existing
  pattern (`EnrollmentInProgressException`), and it keeps the 409 mapping
  centralized in `GlobalExceptionHandler` rather than duplicated per
  endpoint.
- "Why not just add a DB unique constraint?" — real trade-off discussion:
  stronger guarantee, but changes `createCustomer()`'s behavior too,
  which is out of scope for a ticket specifically about updating email.

## Live Demo / Evidence Links

- Commit: see this file's own commit for the exact SHA (recorded in
  `docs/BACKLOG.json`'s BL-013 entry).
- `docs/RETRO_LOG.md`'s sprint retro table (BL-009 through BL-015) carries
  the real estimate-vs-actual comparison for this item.
