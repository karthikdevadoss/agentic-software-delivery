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

@RestController
@RequestMapping("/customers/{customerId}/appointment-availability")
@Tag(name = "Appointment Availability", description = "Real downstream integration with resilience (circuit breaker + retry)")
@SecurityRequirement(name = "bearerAuth")
public class AppointmentController {

    public record AppointmentAvailabilityResponse(LocalDate date, AppointmentAvailabilityStatus status) {
    }

    private final AppointmentAvailabilityService appointmentAvailabilityService;
    private final CustomerService customerService;

    public AppointmentController(AppointmentAvailabilityService appointmentAvailabilityService, CustomerService customerService) {
        this.appointmentAvailabilityService = appointmentAvailabilityService;
        this.customerService = customerService;
    }

    /** Deliberately does NOT 404/500 on a DOWNSTREAM failure -- the HTTP
     * response is always 200 with an honest status field
     * (AVAILABLE/UNAVAILABLE/SERVICE_UNAVAILABLE) once past customer
     * validation, since "the downstream dependency is down" is a real,
     * expected, non-exceptional outcome for a resilience-aware endpoint,
     * not a bug in THIS service. {@code customerId} previously routed
     * requests without being validated at all -- an unused business
     * identifier in the API contract. It is now validated against
     * CustomerService (404 for a customer that does not exist), the same
     * pattern CustomerPreferenceService/ContractPlanService already use,
     * so a caller cannot probe arbitrary/nonexistent customer ids and
     * still get a 200. The downstream Appointment service in this
     * scenario still schedules by date only, not per-customer. */
    @GetMapping
    public AppointmentAvailabilityResponse checkAvailability(
            @PathVariable Long customerId,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date) {
        customerService.getById(customerId); // 404s if the customer itself does not exist
        return new AppointmentAvailabilityResponse(date, appointmentAvailabilityService.checkAvailability(date));
    }
}
