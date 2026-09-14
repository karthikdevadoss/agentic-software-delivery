package com.example.customer.integration.appointment;

import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;

@RestController
@RequestMapping("/customers/{customerId}/appointment-availability")
@Tag(name = "Appointment Availability", description = "Real downstream integration with resilience (circuit breaker + retry)")
public class AppointmentController {

    public record AppointmentAvailabilityResponse(LocalDate date, AppointmentAvailabilityStatus status) {
    }

    private final AppointmentAvailabilityService appointmentAvailabilityService;

    public AppointmentController(AppointmentAvailabilityService appointmentAvailabilityService) {
        this.appointmentAvailabilityService = appointmentAvailabilityService;
    }

    /** Deliberately does NOT 404/500 on a downstream failure -- the HTTP
     * response is always 200 with an honest status field
     * (AVAILABLE/UNAVAILABLE/SERVICE_UNAVAILABLE), since "the downstream
     * dependency is down" is a real, expected, non-exceptional outcome
     * for a resilience-aware endpoint, not a bug in THIS service. Note
     * this intentionally ignores {@code customerId} beyond routing --
     * the downstream Appointment service in this scenario schedules by
     * date only, not per-customer; kept as a path variable purely to
     * match this app's existing /customers/{id}/... URL convention. */
    @GetMapping
    public AppointmentAvailabilityResponse checkAvailability(
            @PathVariable Long customerId,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date) {
        return new AppointmentAvailabilityResponse(date, appointmentAvailabilityService.checkAvailability(date));
    }
}
