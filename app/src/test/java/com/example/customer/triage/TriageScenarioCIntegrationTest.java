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
 * Real, end-to-end proof of Incident Triage Lab Scenario C's isolation
 * and lifecycle contract -- same shape as Scenarios A/B. Runs against
 * this project's default H2 profile, so it can only verify what H2
 * CAN prove: reset/reproduce/approve mechanics, isolation, and admin
 * gating. It deliberately does NOT assert defectReproduced==true for the
 * buggy path -- H2 has no equivalent type-inference gap to Postgres's
 * (the whole point of this real historical incident), so the buggy query
 * genuinely succeeds on H2. That specific defect proof lives in
 * TriageScenarioCPostgresIntegrationTest (Testcontainers, real Postgres,
 * CI-only -- see PostgresFlywayIntegrationTest for the established
 * pattern this project already uses for exactly this class of test).
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class TriageScenarioCIntegrationTest {

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
        ResponseEntity<TriageCState> response = anonymous.postForEntity(url("/internal/triage/scenario-c/reset"), null, TriageCState.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody().fixApplied()).isFalse();
    }

    @Test
    void reproduce_onH2_honestlyReportsTheQuerySucceeding_notAFabricatedDefect() {
        restTemplate.postForEntity(url("/internal/triage/scenario-c/reset"), null, TriageCState.class);

        TriageCReproductionResult result = restTemplate.postForObject(
                url("/internal/triage/scenario-c/reproduce"), null, TriageCReproductionResult.class);

        // H2 has no equivalent type-inference gap -- this query genuinely
        // succeeds here, finding the real synthetic customer reset() just
        // created, regardless of fixApplied. Never asserted as a defect.
        assertThat(result.querySucceeded()).isTrue();
        assertThat(result.resultCount()).isGreaterThanOrEqualTo(1);
        assertThat(result.defectReproduced()).isFalse();
    }

    @Test
    void approve_withoutAdminAuthority_isRejected() {
        RestTemplate anonymous = new RestTemplate();
        assertThatThrownBy(() -> anonymous.postForEntity(url("/internal/triage/scenario-c/approve"), null, TriageCState.class))
                .isInstanceOf(HttpClientErrorException.Unauthorized.class);

        assertThatThrownBy(() -> restTemplate.postForEntity(url("/internal/triage/scenario-c/approve"), null, TriageCState.class))
                .isInstanceOf(HttpClientErrorException.Forbidden.class);
    }

    @Test
    void approve_withAdminAuthority_appliesTheFix() {
        restTemplate.postForEntity(url("/internal/triage/scenario-c/reset"), null, TriageCState.class);

        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(adminToken());
        ResponseEntity<TriageCState> approveResponse = restTemplate.exchange(
                url("/internal/triage/scenario-c/approve"), HttpMethod.POST, new HttpEntity<>(headers), TriageCState.class);
        assertThat(approveResponse.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(approveResponse.getBody().fixApplied()).isTrue();

        TriageCReproductionResult result = restTemplate.postForObject(
                url("/internal/triage/scenario-c/reproduce"), null, TriageCReproductionResult.class);
        assertThat(result.fixApplied()).isTrue();
        assertThat(result.querySucceeded()).isTrue();
    }
}
