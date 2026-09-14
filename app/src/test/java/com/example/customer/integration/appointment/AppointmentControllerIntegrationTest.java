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

import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * REAL BUG FOUND AND FIXED (2026-09-14): {@code customerId} was accepted
 * in the URL but never validated against anything -- an unused business
 * identifier in the API. AppointmentController now validates it via
 * CustomerService the same way CustomerPreferenceService/ContractPlanService
 * already do; this test proves a nonexistent customer id genuinely 404s
 * instead of silently returning a 200 downstream-availability answer.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class AppointmentControllerIntegrationTest {

    @LocalServerPort
    private int port;

    @Autowired
    private DemoJwtIssuer demoJwtIssuer;

    private RestTemplate restTemplate;

    @BeforeEach
    void setUpAuthenticatedClient() {
        restTemplate = AuthTestSupport.authenticatedRestTemplate(demoJwtIssuer);
    }

    private String url(String path) {
        return "http://localhost:" + port + path;
    }

    @Test
    void checkAvailability_forNonExistentCustomer_returns404_neverSilently200s() {
        assertThatThrownBy(() -> restTemplate.getForEntity(
                url("/customers/999999999/appointment-availability?date=2026-10-01"), String.class))
                .isInstanceOf(HttpClientErrorException.NotFound.class);
    }

    @Test
    void checkAvailability_forRealCustomer_doesNotFailOnCustomerValidation() {
        Customer created = restTemplate.postForObject(
                url("/customers"), new Customer("Appt Tester", "appt@example.com"), Customer.class);

        // No WireMock stub is configured for this test's default downstream
        // base-url, so the honest outcome here is SERVICE_UNAVAILABLE, not
        // AVAILABLE/UNAVAILABLE -- the point of this test is that customer
        // validation passes and the request reaches that point at all
        // (i.e. does NOT 404), not what the unstubbed downstream returns.
        var response = restTemplate.getForEntity(
                url("/customers/" + created.getId() + "/appointment-availability?date=2026-10-01"), String.class);
        org.assertj.core.api.Assertions.assertThat(response.getStatusCode().value()).isEqualTo(200);
    }
}
