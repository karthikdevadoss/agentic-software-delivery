package com.example.customer.triage;

import com.example.customer.security.DemoIdentitySeeder;
import com.example.customer.security.DemoJwtIssuer;
import com.example.customer.security.DemoLoginRequest;
import com.example.customer.security.DemoLoginResponse;
import com.example.customer.testsupport.AuthTestSupport;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Real, end-to-end proof of Incident Triage Lab Scenario D's isolation
 * and lifecycle contract -- same shape as TriageScenarioAIntegrationTest:
 * the buggy path genuinely reproduces the real historical defect (the
 * BillingSync fan-out consumer silently never running because
 * ProcessedEvent's idempotency check used to be global by eventId, not
 * scoped per consumer -- see ProcessedEvent's Javadoc), approve() is
 * genuinely ADMIN-gated, and once approved both consumers genuinely run.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class TriageScenarioDIntegrationTest {

    @LocalServerPort
    private int port;

    @Autowired
    private DemoJwtIssuer demoJwtIssuer;

    private RestTemplate restTemplate;

    @BeforeEach
    void setUp() {
        restTemplate = AuthTestSupport.authenticatedRestTemplate(demoJwtIssuer);
    }

    private String url(String path) {
        return "http://localhost:" + port + path;
    }

    private String adminToken() {
        DemoLoginResponse admin = restTemplate.postForObject(
                url("/auth/login"), new DemoLoginRequest("admin1", DemoIdentitySeeder.DEMO_PASSWORD), DemoLoginResponse.class);
        return admin.accessToken();
    }

    @Test
    void reset_isReachableWithoutAuthentication_andCreatesAFreshSyntheticEventId() {
        RestTemplate anonymous = new RestTemplate();
        ResponseEntity<TriageScenarioDState> response = anonymous.postForEntity(
                url("/internal/triage/scenario-d/reset"), null, TriageScenarioDState.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody().eventId()).isNotNull();
        assertThat(response.getBody().fixApplied()).isFalse();
    }

    @Test
    void reproduce_beforeApproval_genuinelyReproducesTheRealFanOutBug() {
        restTemplate.postForEntity(url("/internal/triage/scenario-d/reset"), null, TriageScenarioDState.class);

        TriageScenarioDReproductionResult result = restTemplate.postForObject(
                url("/internal/triage/scenario-d/reproduce"), null, TriageScenarioDReproductionResult.class);

        assertThat(result.notificationConsumerRan()).isTrue(); // the first consumer always genuinely runs
        assertThat(result.billingSyncConsumerRan()).isFalse(); // the second is wrongly skipped -- the real bug
        assertThat(result.defectReproduced()).isTrue();
    }

    @Test
    void approve_withoutAdminAuthority_isRejected() {
        RestTemplate anonymous = new RestTemplate();
        assertThatThrownBy(() -> anonymous.postForEntity(url("/internal/triage/scenario-d/approve"), null, TriageScenarioDState.class))
                .isInstanceOf(HttpClientErrorException.Unauthorized.class);

        assertThatThrownBy(() -> restTemplate.postForEntity(url("/internal/triage/scenario-d/approve"), null, TriageScenarioDState.class))
                .isInstanceOf(HttpClientErrorException.Forbidden.class);
    }

    @Test
    void approve_withAdminAuthority_appliesTheFix_andBothConsumersGenuinelyRun() {
        restTemplate.postForEntity(url("/internal/triage/scenario-d/reset"), null, TriageScenarioDState.class);

        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(adminToken());
        ResponseEntity<TriageScenarioDState> approveResponse = restTemplate.exchange(
                url("/internal/triage/scenario-d/approve"), HttpMethod.POST, new HttpEntity<>(headers), TriageScenarioDState.class);
        assertThat(approveResponse.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(approveResponse.getBody().fixApplied()).isTrue();

        // A fresh event (reproduce() always generates one) with the fix
        // applied: BOTH independent consumers genuinely process it.
        TriageScenarioDReproductionResult result = restTemplate.postForObject(
                url("/internal/triage/scenario-d/reproduce"), null, TriageScenarioDReproductionResult.class);

        assertThat(result.notificationConsumerRan()).isTrue();
        assertThat(result.billingSyncConsumerRan()).isTrue();
        assertThat(result.defectReproduced()).isFalse();
    }

    @Test
    void reproduce_generatesAFreshEventIdEveryCall_soRepeatedCallsStayCleanReplays() {
        restTemplate.postForEntity(url("/internal/triage/scenario-d/reset"), null, TriageScenarioDState.class);

        TriageScenarioDReproductionResult first = restTemplate.postForObject(
                url("/internal/triage/scenario-d/reproduce"), null, TriageScenarioDReproductionResult.class);
        TriageScenarioDReproductionResult second = restTemplate.postForObject(
                url("/internal/triage/scenario-d/reproduce"), null, TriageScenarioDReproductionResult.class);

        assertThat(first.eventId()).isNotEqualTo(second.eventId());
        assertThat(second.defectReproduced()).isTrue(); // still buggy, still reproduces cleanly, no reset needed
    }
}
