package com.example.billingservice.client;

import java.math.BigDecimal;

/**
 * ACT-013: honest, distinct outcomes of asking the legacy billing system
 * of record for a plan's authoritative rate -- mirrors
 * CustomerLookupOutcome's philosophy exactly (see its Javadoc): Unavailable
 * is never fabricated as either a confirmed rate or a "plan does not
 * exist" answer. Guessing a rate, or silently falling back to whatever the
 * caller submitted, when the legacy system could not be reached would let
 * billing-service enroll a customer at a rate it never actually confirmed
 * -- the exact behavior this whole facade rework (ACT-013) exists to
 * remove. A sealed interface (not a plain enum) because Confirmed needs to
 * carry the actual rate value -- same style already used by
 * EnrollmentLockService.LockResult for the same reason (Acquired carries a
 * token).
 */
public sealed interface LegacyPlanPricingOutcome {

    /** The legacy system recognizes this plan and returned its real,
     * authoritative rate -- this is what gets persisted, never the
     * caller-submitted rate on ContractPlanEnrollRequest. */
    record Confirmed(BigDecimal ratePerKwh) implements LegacyPlanPricingOutcome {}

    /** A real, healthy 404 from the legacy system: this plan code does not
     * exist in its catalog. Never retried, never counted as a circuit-
     * breaker failure (see LegacyBillingSystemClientConfig's
     * ignoreExceptions) -- a real negative answer, not evidence the legacy
     * system itself is failing. */
    record PlanNotRecognized() implements LegacyPlanPricingOutcome {}

    /** The legacy system could not be reached at all (timeout, 5xx, open
     * circuit) -- "we don't know, try again," never fabricated as either
     * of the above. */
    record Unavailable() implements LegacyPlanPricingOutcome {}
}
