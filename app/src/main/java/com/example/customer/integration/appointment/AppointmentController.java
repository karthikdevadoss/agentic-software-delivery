package com.example.customer.integration.appointment;

import com.example.customer.service.CustomerService;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.util.List;

@RestController
@RequestMapping("/customers/{customerId}/appointment-availability")
@Tag(name = "Appointment Availability", description = "Real downstream integration with resilience (circuit breaker + retry)")
@SecurityRequirement(name = "bearerAuth")
public class AppointmentController {

    public record AppointmentAvailabilityResponse(LocalDate date, AppointmentAvailabilityStatus status, List<String> availableSlots) {
    }

    private final AppointmentAvailabilityService appointmentAvailabilityService;
    private final CustomerService customerService;

    public AppointmentController(AppointmentAvailabilityService appointmentAvailabilityService, CustomerService customerService) {
        this.appointmentAvailabilityService = appointmentAvailabilityService;
        this.customerService = customerService;
    }

    /** Deliberately does NOT 404/500 on a DOWNSTREAM failure -- the HTTP
     * response is always 200 with an honest status field
     * (AVAILABLE/UNAVAILABLE/SERVICE_UNAVAILABLE) once past customer/date
     * validation, since "the downstream dependency is down" is a real,
     * expected, non-exceptional outcome for a resilience-aware endpoint,
     * not a bug in THIS service. {@code customerId} is validated against
     * CustomerService (404 for a customer that does not exist). A past
     * date is rejected with a real 400 BEFORE ever calling downstream --
     * checking availability for a date that has already passed is not a
     * meaningful business operation, and the resilience/timeout machinery
     * shouldn't be exercised for a request that's invalid regardless of
     * what downstream would say. {@code scenario} is an optional,
     * demo-only control ("timeout"/"error") a recruiter can use to
     * deliberately exercise the real retry/circuit-breaker path -- see
     * AppointmentAvailabilityClient's Javadoc; omitted/blank means normal. */
    @GetMapping
    public AppointmentAvailabilityResponse checkAvailability(
            @PathVariable Long customerId,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date,
            @RequestParam(required = false) String scenario) {
        customerService.getById(customerId); // 404s if the customer itself does not exist
        if (date.isBefore(LocalDate.now())) {
            throw new IllegalArgumentException("Appointment date must be today or later.");
        }
        AppointmentAvailabilityResult result = appointmentAvailabilityService.checkAvailability(date, scenario);
        return new AppointmentAvailabilityResponse(date, result.status(), result.slots());
    }
}
