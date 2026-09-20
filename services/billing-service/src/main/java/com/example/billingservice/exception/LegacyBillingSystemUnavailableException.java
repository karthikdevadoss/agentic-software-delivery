package com.example.billingservice.exception;

/**
 * ACT-013: thrown when LegacyBillingSystemClient could not get a real
 * answer from the legacy billing system (see
 * LegacyPlanPricingOutcome.Unavailable) -- distinct from a genuine
 * "plan not recognized" (NoSuchElementException, -&gt; 404): this means
 * billing-service's own dependency is unreachable, not that the plan
 * doesn't exist in the legacy catalog. See GlobalExceptionHandler for the
 * HTTP status mapping, same 503-not-502 reasoning as
 * CustomerServiceUnavailableException/MeteringServiceUnavailableException.
 */
public class LegacyBillingSystemUnavailableException extends RuntimeException {

    public LegacyBillingSystemUnavailableException(String message) {
        super(message);
    }
}
