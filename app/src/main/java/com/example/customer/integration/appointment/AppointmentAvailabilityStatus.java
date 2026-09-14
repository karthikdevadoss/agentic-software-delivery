package com.example.customer.integration.appointment;

/**
 * SERVICE_UNAVAILABLE is a deliberate, distinct outcome from
 * AVAILABLE/UNAVAILABLE — never fabricated as either. Guessing "probably
 * available" (or "probably not") when the real downstream service could
 * not be reached would be actively wrong for a real scheduling decision;
 * an honest "we don't know, try again" is the only business-valid
 * fallback here (see the overnight task's own instruction: "fallback
 * only where business-valid").
 */
public enum AppointmentAvailabilityStatus {
    AVAILABLE,
    UNAVAILABLE,
    SERVICE_UNAVAILABLE
}
