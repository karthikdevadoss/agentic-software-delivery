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
 * Real, end-to-end proof of Incident Triage Lab Scenario A's isolation
 * and lifecycle contract: the buggy path genuinely reproduces the real
 * historical defect (duplicate ACTIVE-plan churn) against ONLY a
 * dedicated synthetic customer, approve() is genuinely gated to an ADMIN
 * persona token (never anonymous or USER), and once approved the exact
 * same reproduction sequence is genuinely fixed (idempotent no-op).
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class TriageScenarioAIntegrationTest {

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
    void reset_isReachableWithoutAuthentication_andCreatesADedicatedSyntheticCustomer() {
        RestTemplate anonymous = new RestTemplate();
        ResponseEntity<TriageState> response = anonymous.postForEntity(url("/internal/triage/scenario-a/reset"), null, TriageState.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody().triageCustomerId()).isNotNull();
        assertThat(response.getBody().fixApplied()).isFalse();
    }

    @Test
    void reproduce_beforeApproval_genuinelyReproducesTheRealHistoricalDefect() {
        restTemplate.postForEntity(url("/internal/triage/scenario-a/reset"), null, TriageState.class);

        TriageReproductionResult result = restTemplate.postForObject(
                url("/internal/triage/scenario-a/reproduce"), null, TriageReproductionResult.class);

        assertThat(result.defectReproduced()).isTrue();
        assertThat(result.plans()).hasSizeGreaterThan(1);
        assertThat(result.activePlanCount()).isEqualTo(1);
    }

    @Test
    void approve_withoutAdminAuthority_isRejected() {
        RestTemplate anonymous = new RestTemplate();
        assertThatThrownBy(() -> anonymous.postForEntity(url("/internal/triage/scenario-a/approve"), null, TriageState.class))
                .isInstanceOf(HttpClientErrorException.Unauthorized.class);

        assertThatThrownBy(() -> restTemplate.postForEntity(url("/internal/triage/scenario-a/approve"), null, TriageState.class))
                .isInstanceOf(HttpClientErrorException.Forbidden.class);
    }

    @Test
    void approve_withAdminAuthority_appliesTheFix_andReproduceIsNowIdempotent() {
        restTemplate.postForEntity(url("/internal/triage/scenario-a/reset"), null, TriageState.class);

        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(adminToken());
        ResponseEntity<TriageState> approveResponse = restTemplate.exchange(
                url("/internal/triage/scenario-a/approve"), HttpMethod.POST, new HttpEntity<>(headers), TriageState.class);
        assertThat(approveResponse.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(approveResponse.getBody().fixApplied()).isTrue();

        TriageReproductionResult result = restTemplate.postForObject(
                url("/internal/triage/scenario-a/reproduce"), null, TriageReproductionResult.class);

        assertThat(result.defectReproduced()).isFalse();
        assertThat(result.plans()).hasSize(1);
        assertThat(result.activePlanCount()).isEqualTo(1);
    }
}
