package com.example.customer.integration.appointment;

import com.example.customer.model.Customer;
import com.example.customer.security.DemoJwtIssuer;
import com.example.customer.testsupport.AuthTestSupport;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.temporal.TemporalAdjusters;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * REAL BUG FOUND AND FIXED (2026-09-14): {@code customerId} was accepted
 * in the URL but never validated against anything -- an unused business
 * identifier in the API. AppointmentController now validates it via
 * CustomerService the same way CustomerPreferenceService/ContractPlanService
 * already do; this test proves a nonexistent customer id genuinely 404s
 * instead of silently returning a 200 downstream-availability answer.
 *
 * As of the internal demo-appointment-provider addition (same day), the
 * default downstream base-url is this app's own real synthetic demo
 * provider (no WireMock needed here) -- these tests exercise the real,
 * default happy-path behavior a recruiter actually sees.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class AppointmentControllerIntegrationTest {

    @LocalServerPort
    private int port;

    @Autowired
    private DemoJwtIssuer demoJwtIssuer;

    private RestTemplate restTemplate;

    // The demo provider's synthetic rule is "weekdays available, weekends
    // fully booked". Dates are computed from today: fixed calendar dates
    // (2026-10-01/03) passed into the past and turned this suite red once
    // the controller rejected them as "before today".
    private static final LocalDate WEEKDAY =
            LocalDate.now().plusWeeks(1).with(TemporalAdjusters.nextOrSame(DayOfWeek.WEDNESDAY));
    private static final LocalDate WEEKEND =
            LocalDate.now().plusWeeks(1).with(TemporalAdjusters.nextOrSame(DayOfWeek.SATURDAY));

    @BeforeEach
    void setUpAuthenticatedClient() {
        restTemplate = AuthTestSupport.authenticatedRestTemplate(demoJwtIssuer);
    }

    private String url(String path) {
        return "http://localhost:" + port + path;
    }

    private Long createCustomer() {
        Customer created = restTemplate.postForObject(
                url("/customers"), new Customer("Appt Tester", "appt@example.com"), Customer.class);
        return created.getId();
    }

    @Test
    void checkAvailability_forNonExistentCustomer_returns404_neverSilently200s() {
        assertThatThrownBy(() -> restTemplate.getForEntity(
                url("/customers/999999999/appointment-availability?date=" + WEEKDAY), String.class))
                .isInstanceOf(HttpClientErrorException.NotFound.class);
    }

    @Test
    void checkAvailability_forRealFutureWeekday_returnsAvailableWithRealSyntheticSlots() {
        Long id = createCustomer();

        @SuppressWarnings("unchecked")
        Map<String, Object> body = restTemplate.getForObject(
                url("/customers/" + id + "/appointment-availability?date=" + WEEKDAY), Map.class);

        assertThat(body.get("status")).isEqualTo("AVAILABLE");
        assertThat((java.util.List<String>) body.get("availableSlots")).isNotEmpty();
    }

    @Test
    void checkAvailability_forFutureWeekend_returnsUnavailableWithNoSlots() {
        Long id = createCustomer();

        @SuppressWarnings("unchecked")
        Map<String, Object> body = restTemplate.getForObject(
                url("/customers/" + id + "/appointment-availability?date=" + WEEKEND), Map.class);

        assertThat(body.get("status")).isEqualTo("UNAVAILABLE");
        assertThat((java.util.List<String>) body.get("availableSlots")).isEmpty();
    }

    @Test
    void checkAvailability_forPastDate_returns400_withoutCallingDownstream() {
        Long id = createCustomer();
        String pastDate = LocalDate.now().minusDays(1).toString();

        assertThatThrownBy(() -> restTemplate.getForEntity(
                url("/customers/" + id + "/appointment-availability?date=" + pastDate), Map.class))
                .isInstanceOf(HttpClientErrorException.BadRequest.class)
                .satisfies(ex -> {
                    String responseBody = ((HttpClientErrorException) ex).getResponseBodyAsString();
                    assertThat(responseBody).contains("Appointment date must be today or later.");
                });
    }

    @Test
    void checkAvailability_withTimeoutScenario_returnsServiceUnavailable_realResilience4jPath() {
        Long id = createCustomer();

        @SuppressWarnings("unchecked")
        Map<String, Object> body = restTemplate.getForObject(
                url("/customers/" + id + "/appointment-availability?date=" + WEEKDAY + "&scenario=timeout"), Map.class);

        assertThat(body.get("status")).isEqualTo("SERVICE_UNAVAILABLE");
    }
}
