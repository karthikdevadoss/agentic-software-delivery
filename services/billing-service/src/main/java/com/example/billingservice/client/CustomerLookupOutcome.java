package com.example.billingservice.client;

/**
 * Honest, distinct outcomes of asking customer-service whether a customer
 * exists -- mirrors AppointmentAvailabilityStatus's philosophy in app/
 * (see its Javadoc): SERVICE_UNAVAILABLE is never fabricated as either
 * FOUND or NOT_FOUND. Guessing "probably exists" when customer-service
 * could not be reached would let billing-service silently enroll a
 * customer it never actually confirmed exists; an honest "we don't know,
 * try again" (mapped to a 503 by GlobalExceptionHandler) is the only
 * business-valid fallback.
 *
 * NOT_FOUND is kept distinct from SERVICE_UNAVAILABLE (unlike a plain
 * boolean "found") because they mean genuinely different things to a
 * caller: NOT_FOUND is a real, confirmed negative answer from a healthy
 * customer-service (-> 404, "this customer id does not exist"),
 * SERVICE_UNAVAILABLE is the absence of any answer at all (-> 503, "try
 * again, we could not check").
 */
public enum CustomerLookupOutcome {
    FOUND,
    NOT_FOUND,
    SERVICE_UNAVAILABLE
}
