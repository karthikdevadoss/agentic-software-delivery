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
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.web.client.RestTemplate;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * REAL Postgres proof of Incident Triage Lab Scenario C's actual defect --
 * the exact same Testcontainers pattern PostgresFlywayIntegrationTest
 * already established in this project (disabledWithoutDocker = true: an
 * honest SKIP, not a fail, on this dev machine which has no local Docker
 * daemon; runs for real on GitHub Actions' Docker-enabled CI runners --
 * see .github/workflows/ci.yml).
 *
 * Proves the real historical incident (commit 9f35f27): a bind parameter
 * wrapped in LOWER(CONCAT('%', :term, '%')) and also compared via
 * ":term IS NULL" cannot have its type inferred by PostgreSQL's JDBC
 * driver, defaulting to bytea and failing with "function lower(bytea)
 * does not exist" -- genuinely reproduced here against a real, ephemeral
 * PostgreSQL container, then genuinely fixed by pre-building the LIKE
 * pattern and binding it as a plain, unambiguous String parameter.
 */
@Testcontainers(disabledWithoutDocker = true)
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("postgres")
class TriageScenarioCPostgresIntegrationTest {

    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

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
    void reproduce_beforeApproval_genuinelyFailsAgainstRealPostgres_withTheRealHistoricalException() {
        restTemplate.postForEntity(url("/internal/triage/scenario-c/reset"), null, TriageCState.class);

        TriageCReproductionResult result = restTemplate.postForObject(
                url("/internal/triage/scenario-c/reproduce"), null, TriageCReproductionResult.class);

        assertThat(result.querySucceeded()).isFalse();
        assertThat(result.defectReproduced()).isTrue();
        assertThat(result.errorMessage()).containsIgnoringCase("bytea");
    }

    @Test
    void approve_withAdminAuthority_appliesTheFix_andReproduceNowGenuinelySucceedsAgainstRealPostgres() {
        restTemplate.postForEntity(url("/internal/triage/scenario-c/reset"), null, TriageCState.class);

        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(adminToken());
        ResponseEntity<TriageCState> approveResponse = restTemplate.exchange(
                url("/internal/triage/scenario-c/approve"), HttpMethod.POST, new HttpEntity<>(headers), TriageCState.class);
        assertThat(approveResponse.getStatusCode()).isEqualTo(HttpStatus.OK);

        TriageCReproductionResult result = restTemplate.postForObject(
                url("/internal/triage/scenario-c/reproduce"), null, TriageCReproductionResult.class);

        assertThat(result.querySucceeded()).isTrue();
        assertThat(result.defectReproduced()).isFalse();
        assertThat(result.resultCount()).isGreaterThanOrEqualTo(1);
    }
}
