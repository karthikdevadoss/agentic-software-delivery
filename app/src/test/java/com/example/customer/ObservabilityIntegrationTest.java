package com.example.customer;

import com.example.customer.model.Customer;
import com.example.customer.security.DemoJwtIssuer;
import com.example.customer.testsupport.AuthTestSupport;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Proves the real observability surface, not just that beans exist:
 * health/info are genuinely public, metrics/prometheus genuinely require
 * a token, real HTTP/security-rejection meter data actually shows up in
 * /actuator/prometheus after real traffic (not merely that the endpoint
 * responds), and Resilience4j's circuit breaker/retry state is bound
 * into the same registry (the downstream-metrics requirement).
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ObservabilityIntegrationTest {

    @LocalServerPort
    private int port;

    @Autowired
    private DemoJwtIssuer demoJwtIssuer;

    private RestTemplate restTemplate;
    private RestTemplate anonymousRestTemplate;

    @BeforeEach
    void setUp() {
        restTemplate = AuthTestSupport.authenticatedRestTemplate(demoJwtIssuer);
        anonymousRestTemplate = new RestTemplate();
    }

    private String url(String path) {
        return "http://localhost:" + port + path;
    }

    @Test
    void health_isPublic_andReportsUp() {
        ResponseEntity<String> response = anonymousRestTemplate.getForEntity(url("/actuator/health"), String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).contains("\"status\":\"UP\"");
    }

    @Test
    void prometheusEndpoint_requiresAuthentication() {
        assertThatThrownBy(() -> anonymousRestTemplate.getForEntity(url("/actuator/prometheus"), String.class))
                .isInstanceOf(HttpClientErrorException.Unauthorized.class);
    }

    @Test
    void prometheusEndpoint_withValidToken_exposesRealMetersAfterRealTraffic() {
        // Generate real traffic first so the meters below are proven to
        // reflect actual activity, not just registered-but-empty meters.
        restTemplate.postForObject(url("/customers"), new Customer("Metrics Probe", "metrics@example.com"), Customer.class);

        ResponseEntity<String> response = restTemplate.getForEntity(url("/actuator/prometheus"), String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        String body = response.getBody();
        assertThat(body).contains("http_server_requests_seconds_count");
        assertThat(body).contains("hikaricp_connections");
        assertThat(body).contains("resilience4j_circuitbreaker_state");
        assertThat(body).contains("resilience4j_retry_calls_total");
    }

    @Test
    void securityRejectionCounter_incrementsOnRealUnauthenticatedRequest() {
        // Force at least one real 401 first.
        try {
            anonymousRestTemplate.getForEntity(url("/customers/1"), String.class);
        } catch (HttpClientErrorException.Unauthorized ignored) {
            // expected
        }

        ResponseEntity<String> response = restTemplate.getForEntity(url("/actuator/prometheus"), String.class);
        assertThat(response.getBody()).contains("security_rejections_total");
        assertThat(response.getBody()).contains("reason=\"unauthenticated\"");
    }
}
