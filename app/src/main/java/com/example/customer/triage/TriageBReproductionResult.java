package com.example.customer.triage;

/** Real evidence returned to the Triage Lab UI: how many actual HTTP
 * round-trip attempts the real Resilience4j Retry made against a genuine
 * downstream 4xx client error (which retrying can never fix), plus the
 * derived verdict (defectReproduced = the pre-fix predicate retried a
 * 4xx anyway, wasting calls and delaying an answer that would never
 * change). expectedAttemptCount is always 1 -- the one correct answer
 * for a non-retryable client error, never a guess. */
public record TriageBReproductionResult(
        boolean fixApplied,
        int attemptCount,
        int expectedAttemptCount,
        String exceptionType,
        String exceptionMessage,
        boolean defectReproduced
) {
}
