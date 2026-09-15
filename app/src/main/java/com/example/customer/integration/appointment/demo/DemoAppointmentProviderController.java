package com.example.customer.integration.appointment.demo;

import com.example.customer.integration.appointment.AppointmentAvailabilityClient;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.DayOfWeek;
import java.time.LocalDate;
import java.util.List;

/**
 * PORTFOLIO DEMO DOWNSTREAM PROVIDER -- SYNTHETIC DATA. This is
 * explicitly NOT a real energy-company appointment-scheduling backend;
 * it exists solely so a recruiter/interviewer can exercise the real
 * AppointmentAvailabilityClient/Service HTTP + Resilience4j path (real
 * timeout, real retry, real circuit breaker) without a paid/real
 * external dependency. AppointmentAvailabilityClient reaches this over
 * a genuine HTTP loopback call (see application.properties'
 * appointment.service.base-url default) -- never a direct method call --
 * so the integration architecture stays real end to end; only the data
 * on the other side of the wire is synthetic.
 *
 * Deterministic by design (same date always gives the same answer,
 * weekends are always fully booked) so a recruiter can trust and
 * reason about what they see, not random noise.
 */
@RestController
@RequestMapping("/internal/demo-appointment-provider")
public class DemoAppointmentProviderController {

    private static final List<String> WEEKDAY_SLOTS = List.of("09:00", "11:30", "14:00", "16:30");

    /** Longer than AppointmentAvailabilityConfig's real 1000ms client read
     * timeout, so scenario=timeout triggers a genuine client-side timeout
     * exception, not a simulated one. */
    private static final long TIMEOUT_SCENARIO_DELAY_MS = 2500;

    @GetMapping("/availability")
    public ResponseEntity<AppointmentAvailabilityClient.DownstreamAvailabilityResponse> checkAvailability(
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date,
            @RequestParam(required = false) String scenario) throws InterruptedException {
        if ("timeout".equalsIgnoreCase(scenario)) {
            Thread.sleep(TIMEOUT_SCENARIO_DELAY_MS);
        }
        if ("error".equalsIgnoreCase(scenario)) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
        // Incident Triage Lab, Scenario B: a genuine downstream 4xx client
        // error (never retried by the real, correct Resilience4j predicate
        // in AppointmentAvailabilityConfig -- retrying a client error can
        // never fix it) -- see TriageScenarioBService for how this is used
        // to demonstrate a deliberately WRONG retry predicate.
        if ("client_error".equalsIgnoreCase(scenario)) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST).build();
        }

        boolean isWeekend = date.getDayOfWeek() == DayOfWeek.SATURDAY || date.getDayOfWeek() == DayOfWeek.SUNDAY;
        return ResponseEntity.ok(isWeekend
                ? new AppointmentAvailabilityClient.DownstreamAvailabilityResponse(false, List.of())
                : new AppointmentAvailabilityClient.DownstreamAvailabilityResponse(true, WEEKDAY_SLOTS));
    }
}
