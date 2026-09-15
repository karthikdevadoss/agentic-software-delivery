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
 * Real, end-to-end proof of Incident Triage Lab Scenario B's isolation
 * and lifecycle contract -- same shape as TriageScenarioAIntegrationTest,
 * a different underlying defect: the buggy path genuinely retries a real
 * downstream HTTP 400 (never retryable) three times before giving up;
 * approve() is genuinely gated to an ADMIN persona token; once approved,
 * the exact same reproduction genuinely makes exactly one real HTTP
 * attempt -- delegating to the REAL production appointmentRetry bean,
 * not a second copy of the fix.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class TriageScenarioBIntegrationTest {

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
    void reset_isReachableWithoutAuthentication() {
        RestTemplate anonymous = new RestTemplate();
        ResponseEntity<TriageBState> response = anonymous.postForEntity(url("/internal/triage/scenario-b/reset"), null, TriageBState.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody().fixApplied()).isFalse();
    }

    @Test
    void reproduce_beforeApproval_genuinelyRetriesANonRetryable4xxThreeTimes() {
        restTemplate.postForEntity(url("/internal/triage/scenario-b/reset"), null, TriageBState.class);

        TriageBReproductionResult result = restTemplate.postForObject(
                url("/internal/triage/scenario-b/reproduce"), null, TriageBReproductionResult.class);

        assertThat(result.defectReproduced()).isTrue();
        assertThat(result.attemptCount()).isEqualTo(3);
        assertThat(result.expectedAttemptCount()).isEqualTo(1);
        assertThat(result.exceptionType()).isNotBlank();
    }

    @Test
    void approve_withoutAdminAuthority_isRejected() {
        RestTemplate anonymous = new RestTemplate();
        assertThatThrownBy(() -> anonymous.postForEntity(url("/internal/triage/scenario-b/approve"), null, TriageBState.class))
                .isInstanceOf(HttpClientErrorException.Unauthorized.class);

        assertThatThrownBy(() -> restTemplate.postForEntity(url("/internal/triage/scenario-b/approve"), null, TriageBState.class))
                .isInstanceOf(HttpClientErrorException.Forbidden.class);
    }

    @Test
    void approve_withAdminAuthority_appliesTheFix_andReproduceNowMakesExactlyOneAttempt() {
        restTemplate.postForEntity(url("/internal/triage/scenario-b/reset"), null, TriageBState.class);

        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(adminToken());
        ResponseEntity<TriageBState> approveResponse = restTemplate.exchange(
                url("/internal/triage/scenario-b/approve"), HttpMethod.POST, new HttpEntity<>(headers), TriageBState.class);
        assertThat(approveResponse.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(approveResponse.getBody().fixApplied()).isTrue();

        TriageBReproductionResult result = restTemplate.postForObject(
                url("/internal/triage/scenario-b/reproduce"), null, TriageBReproductionResult.class);

        assertThat(result.defectReproduced()).isFalse();
        assertThat(result.attemptCount()).isEqualTo(1);
    }
}
