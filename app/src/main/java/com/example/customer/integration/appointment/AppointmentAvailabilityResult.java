package com.example.customer.integration.appointment;

import java.util.List;

/** Business-level outcome of an availability check -- status plus, when
 * genuinely AVAILABLE, the real synthetic slot times the downstream
 * response carried. Never populated with slots for UNAVAILABLE/
 * SERVICE_UNAVAILABLE (there is nothing honest to show). */
public record AppointmentAvailabilityResult(AppointmentAvailabilityStatus status, List<String> slots) {

    public static AppointmentAvailabilityResult withoutSlots(AppointmentAvailabilityStatus status) {
        return new AppointmentAvailabilityResult(status, List.of());
    }
}
