# Interview Scenario: Plan Enrollment — Transactions, Concurrency, Idempotency

Derived from the actual implementation: `app/src/main/java/com/example/customer/service/ContractPlanService.java`, `app/src/main/java/com/example/customer/model/ContractPlan.java`, and a real gap found by code inspection during the 2026-09-15 portfolio session (fixed in commit `2155a8a`).

## Business Why

An energy customer enrolls in exactly one plan at a time — enrolling in a
new plan must supersede (not delete) the old one, keep plan history
queryable, and — critically — must not treat a duplicate submission of
the same action as if the customer had taken two separate actions.
Duplicate submissions are not hypothetical: a slow network causing a
double-click, or a client retrying a request after a timeout whose
original call actually succeeded server-side, are both routine in
production.

## Requirement

- A customer has at most one `ACTIVE` `ContractPlan` at any time.
- Enrolling in a new plan cancels the previous active plan (end-dated on
  the new plan's start date) and creates a new active one — never deletes
  history.
- A repeat of the *exact same* enrollment request, while it is already the
  active plan, must be a no-op — not a second churn event.

## Architecture

```
POST /customers/{id}/plan
   |
   v
ContractPlanService.enroll(customerId, request)
   |-- customerService.getById(customerId)          -- 404s if missing
   |-- find currently ACTIVE plan (single query, reused below)
   |-- IDEMPOTENCY CHECK: same planName/rate/startDate as request?
   |      yes -> return the existing ACTIVE plan unchanged (no-op)
   |-- else: cancel existing ACTIVE plan (saveAndFlush)
   |-- create + save new ACTIVE plan
   v
uq_contract_plan_one_active_per_customer (Postgres partial unique index)
   -- last-line-of-defense constraint, independent of the Java logic above
```

## Java/Spring Implementation

```java
Optional<ContractPlan> currentlyActive =
        contractPlanRepository.findByCustomerIdAndStatus(customerId, ContractPlanStatus.ACTIVE);

if (currentlyActive.filter(existing -> isSameTerms(existing, request)).isPresent()) {
    return currentlyActive.get();   // idempotent no-op
}

currentlyActive.ifPresent(existing -> {
    existing.cancel(request.effectiveStartDate());
    contractPlanRepository.saveAndFlush(existing);   // see flush-order note below
});

ContractPlan newPlan = new ContractPlan(customerId, request.planName(), request.ratePerKwh(), request.effectiveStartDate());
return contractPlanRepository.save(newPlan);
```

`isSameTerms()` compares `planName` by `.equals()`, `ratePerKwh` by
`BigDecimal.compareTo() == 0` (never `.equals()` — `0.14` and `0.140` are
mathematically equal but not `.equals()`-equal in `BigDecimal`, a classic
correctness trap), and `effectiveStartDate` by `.equals()`.

## Database/Data Flow

`ContractPlan` rows are never deleted, only status-transitioned
(`ACTIVE` → `CANCELLED`), so plan history is always queryable. A real
Postgres **partial unique index** (`uq_contract_plan_one_active_per_customer`,
`WHERE status = 'ACTIVE'`) is the actual last line of defense against two
ACTIVE rows ever coexisting for one customer — the Java-level idempotency
check above is a *business-correctness* fix (don't create meaningless
duplicate churn), not the only thing standing between the database and a
data-integrity violation.

## Two Real Bugs Found In This Same Method, At Two Different Layers

This single 15-line method has now had two real, independently-discovered
defects — a good illustration that transactional correctness has more
than one dimension:

1. **Flush-ordering bug** (found earlier, via a genuine Postgres
   Testcontainers test — invisible on H2): Hibernate's default flush order
   runs all pending INSERTs before any pending UPDATEs in one transaction,
   regardless of Java call order. Plain `save()` on the cancelled plan let
   the new plan's INSERT reach Postgres before the old plan's cancellation
   UPDATE did, briefly creating two ACTIVE rows and tripping the partial
   unique index with a 500. Fixed with `saveAndFlush()`.
2. **Idempotency gap** (found by code inspection during this session — no
   existing test covered a repeated identical call): before the fix above,
   a duplicate submission of the same enrollment cancelled the plan the
   *first* call had just activated and created a second, identical one —
   two CANCELLED rows plus a duplicate ACTIVE row for one real customer
   action. Not a crash, not caught by the unique index (each call still
   only ever has one ACTIVE row *at a time*) — a silent business-data
   duplication bug, the kind that is invisible until someone actually
   reads the plan history and asks "why does this customer appear to have
   churned twice in the same second?" Fixed by treating an identical
   repeat as a no-op.

## Failure Cases (real, tested)

- Enrolling a customer that doesn't exist → 404, before any plan-table
  query runs (`enroll_whenCustomerDoesNotExist_throwsBeforeTouchingPlanRepository`).
- First enrollment with no prior active plan → one ACTIVE row created,
  zero cancellations.
- Enrolling in a *different* plan while one is active → old plan
  cancelled+flushed, new plan created — real churn, correctly handled.
- Re-submitting the *exact same* enrollment while it's already active →
  no-op: same object returned, zero repository writes
  (`enroll_whenIdenticalRequestSubmittedTwice_isIdempotentNoOp`).

## Testing

`ContractPlanServiceTest` (Mockito, 6 tests) covers all four cases above
plus the exact flush-ordering (`InOrder`) assertion.
`PostgresFlywayIntegrationTest` proves the partial unique index itself
exists and is enforced against a real Postgres (Testcontainers).
`ContractPlanControllerIntegrationTest` covers the HTTP-layer contract
(H2). Full Java regression re-run clean after this fix: 104 tests, 0
failures, 12 skipped (Docker-dependent, this dev machine has none — same
class of test as the Postgres/Flyway suite throughout this project).

## Design Trade-offs

- **Idempotency-by-comparing-current-state (chosen)** vs. a client-supplied
  `Idempotency-Key` header cached server-side: the header approach is the
  textbook payments-API pattern (Stripe-style) and handles a broader class
  of duplicates (e.g. two *different* new-plan requests that should still
  collapse to one), but requires client changes and a dedup-cache with its
  own TTL/storage. Comparing against current state requires zero client
  changes and correctly handles the actual failure mode this app can
  produce today (retry-of-the-same-action) — the right-sized fix for the
  real, current requirement, not a speculative general-purpose mechanism.
- Returning the existing plan silently (chosen) vs. a `409 Conflict`/
  distinct "already enrolled" response: a silent no-op matches normal REST
  idempotency semantics (a repeat of the same request should look the same
  to the client as if it were the first), and avoids forcing every client
  to special-case a response that isn't actually an error from the
  customer's point of view.

## What Changes at 10x Scale

- The idempotency check is a point-in-time read-then-decide inside one
  `@Transactional` method — correct under Postgres's default
  READ_COMMITTED isolation only because the partial unique index is the
  real concurrency safety net; two *simultaneous* enroll calls for
  different terms would still correctly serialize on that constraint (one
  succeeds, one gets a constraint-violation exception), but that failure
  path is not yet mapped to a clean HTTP response — a real next
  improvement at higher concurrency (`@Retryable` on the constraint
  violation, or a `SELECT ... FOR UPDATE` row lock on the customer's plan
  row before the check-then-act sequence).
- At high request volume, a client-supplied idempotency-key cache (Redis,
  short TTL) would generalize this beyond "identical-terms-to-current-active"
  to "identical request I've seen in the last N minutes," closing the
  broader class of duplicate this simpler fix doesn't cover.

## Interview Questions This Answers

- "Tell me about a real idempotency bug you found and fixed."
- "How do you make a state-changing endpoint safe against duplicate
  submission — and what are the trade-offs of the approaches?"
- "Walk me through `@Transactional` flush ordering and why it can bite you
  in Postgres but not H2."
- "Why compare `BigDecimal` values with `compareTo()` instead of `.equals()`?"
- "What's the difference between a data-integrity bug (caught by a
  constraint) and a business-correctness bug (silent duplication, no
  constraint violation) — and how do you even notice the second kind?"

## Live Demo / Evidence Links

- `app/src/main/java/com/example/customer/service/ContractPlanService.java` (real source)
- `app/src/test/java/com/example/customer/service/ContractPlanServiceTest.java` (real tests, incl. the new idempotency case)
- Commit `2155a8a` (the idempotency fix + regression test)
- This scenario is also the design basis for Incident Triage Lab Scenario A (`docs/TRIAGE_LAB_DESIGN.md`) — the same real defect class, reframed as an interactive diagnose-and-fix demo.
