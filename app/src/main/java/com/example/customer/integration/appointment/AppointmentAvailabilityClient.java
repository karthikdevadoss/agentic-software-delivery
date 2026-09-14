package com.example.customer.integration.appointment;

import org.springframework.web.client.RestClient;

import java.time.LocalDate;
import java.util.List;

/**
 * BUSINESS REQUIREMENT: scheduling a technician appointment (e.g. a meter
 * install/service visit) requires checking a downstream Appointment
 * Availability service — a real external dependency this application
 * does not own or control.
 *
 * DESIGN DECISION: `RestClient` (Spring's modern synchronous HTTP client,
 * available since Spring Framework 6.1 / Boot 3.2, already on the
 * classpath via spring-boot-starter-web) rather than the older
 * `RestTemplate` — this project's own integration TESTS use RestTemplate
 * only because MockMvc/TestRestTemplate happen to be missing from this
 * Spring Boot 4.1.1 setup's test classpath (see
 * CustomerControllerIntegrationTest's Javadoc); that constraint does not
 * apply to production client code, where RestClient is the current
 * idiomatic choice.
 *
 * This class does no retry/circuit-breaking itself — that is
 * AppointmentAvailabilityService's job (composition over one thin,
 * single-purpose HTTP client makes each concern independently testable).
 *
 * By default this points at this same application's own internal
 * synthetic demo provider (see appointment/demo/DemoAppointmentProviderController)
 * over a REAL HTTP loopback call -- not a direct method call -- so the
 * full client/timeout/retry/circuit-breaker path stays genuine. Point
 * appointment.service.base-url at a real downstream service instead once
 * one exists.
 */
public class AppointmentAvailabilityClient {

    private final RestClient restClient;

    public AppointmentAvailabilityClient(RestClient.Builder builder, String baseUrl) {
        this.restClient = builder.baseUrl(baseUrl).build();
    }

    public record DownstreamAvailabilityResponse(boolean available, List<String> slots) {
        public List<String> slotsOrEmpty() {
            return slots == null ? List.of() : slots;
        }
    }

    public DownstreamAvailabilityResponse checkAvailability(LocalDate date) {
        return checkAvailability(date, null);
    }

    /** Throws on any non-2xx response, timeout, or connection failure —
     * callers (AppointmentAvailabilityService) decide what to do with
     * that, this class never swallows a failure into a fake "unavailable"
     * result. {@code scenario} is an optional demo-only control
     * ("timeout"/"error") forwarded to the demo provider so a recruiter
     * can deliberately exercise the real retry/circuit-breaker path --
     * null/blank means "normal". */
    public DownstreamAvailabilityResponse checkAvailability(LocalDate date, String scenario) {
        return restClient.get()
                .uri(uriBuilder -> {
                    uriBuilder.path("/availability").queryParam("date", date);
                    if (scenario != null && !scenario.isBlank()) {
                        uriBuilder.queryParam("scenario", scenario);
                    }
                    return uriBuilder.build();
                })
                .retrieve()
                .body(DownstreamAvailabilityResponse.class);
    }
}
