# Interview Scenario: PostgreSQL Search/Pagination — and a Real Production 500

Derived from the actual implementation: `app/src/main/java/com/example/customer/repository/CustomerRepository.java`, `AdminCustomerController.java`, and a real, root-caused production incident (see docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml AEQ-012).

## Business Why

An ADMIN needs to find a specific customer among potentially many, by
partial name or email, without downloading the entire customer table to
the browser and filtering client-side (which doesn't scale and leaks the
full dataset to the client regardless of what's displayed).

## Requirement

- Server-side, paginated, case-insensitive partial-match search by
  customer id / name / email, each filter independently optional.
- Scoped to the real demo workspace (customers bound to an actual
  `demo_identity` row), never every `Customer` row ever created — see the
  Javadoc comment in the real source, which explains why an unscoped
  `SELECT *` would have surfaced unrelated historical clutter from an
  earlier, pre-login-gate version of the app that auto-created ephemeral
  customers on every anonymous visit.

## Architecture

```
GET /admin/customers?name=...&email=...&customerId=...&page=0&size=20
   |
   v
AdminCustomerController
   |-- builds a Pageable (page clamped >= 0, size clamped to [1, MAX_PAGE_SIZE], sorted by id)
   |-- likePattern(name)  -> already-lowercased "%value%" String, or null if blank
   |-- likePattern(email) -> same
   v
CustomerRepository.searchWorkspaceCustomers(customerId, namePattern, emailPattern, pageable)
   |-- JPQL: scoped to demo_identity-bound customer ids
   |-- each filter: "(:param IS NULL OR <column-comparison>)"
   v
Page<Customer>  (Spring Data: content + total count + page metadata)
```

## Java/Spring Implementation

The critical implementation detail — and the one that caused a real
production incident — is **where the `LOWER()`/pattern-building happens**:

```java
// AdminCustomerController.java
private static String likePattern(String value) {
    if (value == null || value.isBlank()) return null;
    return "%" + value.trim().toLowerCase() + "%";   // built in Java
}
```

```java
// CustomerRepository.java
"AND (:namePattern IS NULL OR LOWER(c.name) LIKE :namePattern) "
```

The bind parameter (`:namePattern`) is a **plain, already-lowercased,
already-wildcarded String** — `LOWER()` is applied to the *column*
(`c.name`), never to the parameter itself. This looks like a small detail,
but it is the exact fix for a real production 500 (see below).

## Database/Data Flow

The query is scoped via a correlated `IN (SELECT ... FROM DemoIdentity ...)`
subquery, not a JOIN — chosen because each `Customer` maps to at most one
`DemoIdentity`, so a subquery expresses "is this customer's id present in
the demo workspace" without needing to worry about join fan-out affecting
`Page`'s total-count calculation.

## The Real Production Incident (worth knowing cold for an interview)

**Symptom:** the full local H2 test suite passed cleanly. The first real
`curl` against live production's `GET /admin/customers?name=...` returned
a genuine HTTP 500:
```
org.postgresql.util.PSQLException: ERROR: function lower(bytea) does not exist
```

**Root cause, confirmed via real `railway logs`, not guessed:** an earlier
version of the JPQL wrapped the *bind parameter itself* in `LOWER(CONCAT('%', :name, '%'))`.
Hibernate translates JPQL `CONCAT` to Postgres's `||` operator. PostgreSQL's
JDBC driver (pgjdbc) infers a bind parameter's SQL type from how it's used
in the statement — and could not infer a concrete type for a **nullable**
String parameter flowing through a `||` concatenation, defaulting it to
`bytea`. `LOWER(bytea)` doesn't exist as a Postgres function — hence the
500. **H2 has no equivalent type-inference gap, so nothing local could have
caught this.**

**Fix:** never wrap a bind parameter itself in `CONCAT`/`LOWER` inside the
query — pre-build the full pattern in Java (already lowercased, already
wildcarded) and bind it as a plain String, applying `LOWER()` only to the
column being compared. This sidesteps the ambiguous-type inference
entirely, because the parameter is now a simple, unambiguous String bind
with no surrounding function call for pgjdbc to reason about.

**Regression protection:** a real Testcontainers-backed Postgres test
(`adminCustomerSearch_byNameAndEmail_worksAgainstRealPostgres_notJustH2` in
`PostgresFlywayIntegrationTest`) was added specifically so CI's real Docker
runner proves this going forward — this dev machine has no local Docker
daemon, so this exact class of bug can ONLY be caught in CI, never locally,
which is itself a load-bearing fact about this project's testing strategy.

## Thread/Concurrency Behavior

Each search request is independently executed against the connection pool;
no shared mutable state. Pagination via `Pageable`/`Page<Customer>` issues
two real queries under the hood (the page content, and a `COUNT(*)` for
total elements) — both scoped identically, so total counts are always
consistent with the actual filtered/scoped result set.

## Failure Cases (real, tested)

- Empty search (`name`/`email`/`customerId` all null) → returns all
  workspace customers, paginated — **not an error.**
- No-result search (a genuinely unmatched pattern) → an empty `Page`, HTTP
  200 — **not an error.**
- USER role on the ADMIN endpoint → 403 (see interview-scenarios/01).
- The exact bug above → now a regression-tested non-issue.

## Testing

`AdminCustomerControllerIntegrationTest` (11 tests, H2) covers the
application-level behavior (pagination math, filter combinations,
authorization). `PostgresFlywayIntegrationTest`'s real Testcontainers test
covers the one thing H2 structurally cannot: real Postgres type-inference
behavior around nullable bind parameters and string functions.

## Production Observability

Found and fixed within minutes of the bad deploy: direct `curl` against
production surfaced the 500 → `railway logs` gave the exact
`PSQLException` message and stack → root cause identified from the
exception text itself (a genuine Postgres error message, not an opaque
framework wrapper) → fixed → redeployed (`b52652dc`, SUCCESS) →
independently re-verified live that empty/name/email/customerId/no-result
searches all return correct 200s.

## Design Trade-offs

- LIKE-pattern search (chosen) vs. Postgres full-text search (`tsvector`/`tsquery`)
  or an external search index: LIKE is simple, requires no extra
  infrastructure, and is entirely adequate at demo/small-table scale — the
  explicit trade-off documented in "What Changes at 10x Scale" below.
- Building the pattern in Java vs. in JPQL: building in Java isn't just
  the fix for the pgjdbc type-inference bug — it also makes the exact
  matching semantics (case-folding, wildcard placement) visible and
  testable in one small, pure function (`likePattern()`), rather than
  buried inside a JPQL string.

## What Changes at 10x Scale

- A `LIKE '%value%'` pattern (leading wildcard) cannot use a standard
  B-tree index — Postgres must scan every scoped row. At meaningfully
  larger customer counts, this becomes a real latency/CPU cost, at which
  point the correct move is a real search mechanism: Postgres full-text
  search with a GIN index (`tsvector` column + `@@` query), a trigram
  index (`pg_trgm`, supports LIKE-style partial match with an index), or
  an external search service (Elasticsearch/OpenSearch) if the search
  requirements grow beyond what Postgres does well.
- The `IN (SELECT ...)` scoping subquery would benefit from an explicit
  index on `demo_identity.customer_id` at scale (trivial at demo size,
  worth verifying via `EXPLAIN ANALYZE` before it matters).

## Interview Questions This Answers

- "Walk me through a real production bug you found and fixed — what was your process?"
- "Why would a query pass on H2 but fail on real Postgres — what's the general lesson?"
- "How do you implement case-insensitive partial-match search safely with bind parameters?"
- "When would you reach for Postgres full-text search or an external search index instead of LIKE?"
- "How do you regression-test a bug that only reproduces against a real database, not an in-memory one?"

## Live Demo / Evidence Links

- https://agentic-delivery-customer-app-production.up.railway.app/admin/customers (ADMIN persona)
- `app/src/main/java/com/example/customer/repository/CustomerRepository.java` (real source, with the incident documented in its own Javadoc)
- docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml — AEQ-012 (structured defect record)
- Commit `9f35f27` (the real fix)
