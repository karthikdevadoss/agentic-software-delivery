package com.example.customer.controller;

import com.example.customer.dto.ContractPlanEnrollRequest;
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

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ContractPlanControllerIntegrationTest {

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

    private Long createCustomer() {
        Customer created = restTemplate.postForObject(
                url("/customers"), new Customer("Plan Tester", "plan@example.com"), Customer.class);
        return created.getId();
    }

    @Test
    void getActivePlan_whenNoneEnrolled_returns404() {
        Long id = createCustomer();

        assertThatThrownBy(() -> restTemplate.getForEntity(url("/customers/" + id + "/plan"), Map.class))
                .isInstanceOf(HttpClientErrorException.NotFound.class);
    }

    @Test
    void enroll_thenGetActivePlan_returnsTheEnrolledPlan() {
        Long id = createCustomer();
        ContractPlanEnrollRequest request = new ContractPlanEnrollRequest(
                "Standard 12mo", new BigDecimal("0.14"), LocalDate.of(2026, 1, 1));

        ResponseEntity<Map> enrollResponse = restTemplate.postForEntity(url("/customers/" + id + "/plan"), request, Map.class);
        assertThat(enrollResponse.getStatusCode()).isEqualTo(HttpStatus.CREATED);

        ResponseEntity<Map> getResponse = restTemplate.getForEntity(url("/customers/" + id + "/plan"), Map.class);
        assertThat(getResponse.getBody().get("planName")).isEqualTo("Standard 12mo");
        assertThat(getResponse.getBody().get("status")).isEqualTo("ACTIVE");
    }

    @Test
    void enrollTwice_supersedesThePriorPlan_onlyOneActiveRemains() {
        Long id = createCustomer();
        restTemplate.postForEntity(url("/customers/" + id + "/plan"),
                new ContractPlanEnrollRequest("Old Plan", new BigDecimal("0.20"), LocalDate.of(2025, 1, 1)), Map.class);

        restTemplate.postForEntity(url("/customers/" + id + "/plan"),
                new ContractPlanEnrollRequest("New Plan", new BigDecimal("0.11"), LocalDate.of(2026, 6, 1)), Map.class);

        ResponseEntity<Map> activePlan = restTemplate.getForEntity(url("/customers/" + id + "/plan"), Map.class);
        assertThat(activePlan.getBody().get("planName")).isEqualTo("New Plan");
    }

    @Test
    void enroll_submittedNTimesIdentically_alwaysResultsInExactlyOneActivePlan_forSeveralRealValuesOfN() {
        // Base Architecture V3 Section 5: systematic falsification testing
        // of the real idempotency invariant ("N identical enrollment
        // requests always result in exactly 1 active plan, for any N"),
        // generalizing the existing unit-level test (which only proves
        // N=2) across several real N values in one real HTTP/DB-backed
        // run -- no prior test in this codebase exercised N > 2. If this
        // property were ever falsified for some N, the plan's id would
        // change on a later submission (a new row created) instead of
        // staying exactly the same real database identity throughout.
        for (int n : new int[]{2, 3, 5, 10}) {
            Long id = createCustomer();
            ContractPlanEnrollRequest request = new ContractPlanEnrollRequest(
                    "Standard 12mo", new BigDecimal("0.14"), LocalDate.of(2026, 1, 1));

            Long firstPlanId = null;
            for (int i = 0; i < n; i++) {
                ResponseEntity<Map> response = restTemplate.postForEntity(url("/customers/" + id + "/plan"), request, Map.class);
                assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CREATED);
                Long planId = ((Number) response.getBody().get("id")).longValue();
                if (firstPlanId == null) {
                    firstPlanId = planId;
                } else {
                    assertThat(planId)
                            .as("submission %d of %d identical requests must return the SAME plan identity, not create a new row", i + 1, n)
                            .isEqualTo(firstPlanId);
                }
            }

            ResponseEntity<Map> activePlan = restTemplate.getForEntity(url("/customers/" + id + "/plan"), Map.class);
            Long activePlanId = ((Number) activePlan.getBody().get("id")).longValue();
            assertThat(activePlanId)
                    .as("after %d identical submissions, exactly one active plan (the original) must exist", n)
                    .isEqualTo(firstPlanId);
            assertThat(activePlan.getBody().get("status")).isEqualTo("ACTIVE");
        }
    }

    @Test
    void enroll_withZeroRate_returns400() {
        Long id = createCustomer();
        ContractPlanEnrollRequest request = new ContractPlanEnrollRequest("Free?", BigDecimal.ZERO, LocalDate.now());

        assertThatThrownBy(() -> restTemplate.postForEntity(url("/customers/" + id + "/plan"), request, Map.class))
                .isInstanceOf(HttpClientErrorException.BadRequest.class);
    }

    @Test
    void enroll_forNonExistentCustomer_returns404() {
        ContractPlanEnrollRequest request = new ContractPlanEnrollRequest("Any", BigDecimal.ONE, LocalDate.now());

        assertThatThrownBy(() -> restTemplate.postForEntity(url("/customers/999999999/plan"), request, Map.class))
                .isInstanceOf(HttpClientErrorException.NotFound.class);
    }
}
