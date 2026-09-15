package com.example.customer.triage;

/** Real evidence returned to the Triage Lab UI: whether the actual JPQL
 * search query executed successfully against the real database, and if
 * not, the real exception it threw. On H2 (this dev machine's default,
 * no local Docker) the buggy query never fails -- H2 has no equivalent
 * type-inference gap, so defectReproduced can only genuinely be true
 * when this runs against real PostgreSQL (Testcontainers in CI, or the
 * real deployed production database). Never fabricated either way. */
public record TriageCReproductionResult(
        boolean fixApplied,
        boolean querySucceeded,
        int resultCount,
        String errorType,
        String errorMessage,
        boolean defectReproduced
) {
}
