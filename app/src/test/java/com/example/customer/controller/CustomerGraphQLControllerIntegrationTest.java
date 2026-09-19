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
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestTemplate;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Real, HTTP-driven proof that the GraphQL endpoint reaches the exact
 * same data/security path as the REST controllers -- deliberately kept
 * to plain RestTemplate + raw GraphQL query strings, matching this
 * codebase's existing REST integration-test style
 * (ContractPlanControllerIntegrationTest), rather than introducing a
 * separate GraphQL-specific test dependency for one endpoint.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class CustomerGraphQLControllerIntegrationTest {

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

    private Long createCustomer(String name, String email) {
        Customer created = restTemplate.postForObject(url("/customers"), new Customer(name, email), Customer.class);
        return created.getId();
    }

    /**
     * Also asserts the response carries no "errors" entry -- a GraphQL
     * response can be HTTP 200 with a populated "data" map AND a real
     * unresolved server error in "errors" at the same time (an
     * INTERNAL_ERROR data-fetcher exception still leaves the failed
     * field null in "data", which can look like a clean business null
     * if only "data" is checked -- see CustomerGraphQLController's
     * NoSuchElementException handling for the real bug this caught).
     */
    @SuppressWarnings("unchecked")
    private Map<String, Object> executeGraphQl(String query) {
        Map<String, Object> body = Map.of("query", query);
        ResponseEntity<Map> response = restTemplate.postForEntity(url("/graphql"), body, Map.class);
        assertThat(response.getStatusCode().is2xxSuccessful()).isTrue();
        assertThat(response.getBody().get("errors"))
                .as("GraphQL response must not contain an unresolved server error")
                .isNull();
        return (Map<String, Object>) response.getBody().get("data");
    }

    @Test
    void customerQuery_returnsTheSameCustomerTheRestEndpointWouldReturn() {
        Long id = createCustomer("GraphQL Tester", "graphql@example.com");

        Map<String, Object> data = executeGraphQl(
                "{ customer(id: " + id + ") { id name email } }");

        @SuppressWarnings("unchecked")
        Map<String, Object> customer = (Map<String, Object>) data.get("customer");
        assertThat(customer.get("name")).isEqualTo("GraphQL Tester");
        assertThat(customer.get("email")).isEqualTo("graphql@example.com");
    }

    @Test
    void activeContractPlanQuery_afterEnrollingViaRest_returnsThePlanThroughGraphQl() {
        Long id = createCustomer("Plan GraphQL Tester", "planqraphql@example.com");
        restTemplate.postForEntity(url("/customers/" + id + "/plan"),
                new ContractPlanEnrollRequest("GraphQL Plan", new BigDecimal("0.15"), LocalDate.of(2026, 1, 1)),
                Map.class);

        Map<String, Object> data = executeGraphQl(
                "{ activeContractPlan(customerId: " + id + ") { planName status ratePerKwh } }");

        @SuppressWarnings("unchecked")
        Map<String, Object> plan = (Map<String, Object>) data.get("activeContractPlan");
        assertThat(plan.get("planName")).isEqualTo("GraphQL Plan");
        assertThat(plan.get("status")).isEqualTo("ACTIVE");
        // ContractPlan.ratePerKwh is BigDecimal(precision=10, scale=4) --
        // "0.15" in is correctly "0.1500" out, matching the DB column's
        // real scale, not a formatting bug.
        assertThat(plan.get("ratePerKwh")).isEqualTo("0.1500");
    }

    @Test
    void activeContractPlanQuery_whenNoneEnrolled_returnsNullNotAnError() {
        Long id = createCustomer("No Plan Tester", "noplan@example.com");

        Map<String, Object> data = executeGraphQl(
                "{ activeContractPlan(customerId: " + id + ") { planName } }");

        assertThat(data.get("activeContractPlan")).isNull();
    }

    @Test
    void graphiqlPage_isPubliclyReachable_withoutAToken() {
        RestTemplate anonymous = new RestTemplate();
        ResponseEntity<String> response = anonymous.getForEntity(url("/graphiql"), String.class);
        assertThat(response.getStatusCode().is2xxSuccessful()).isTrue();
    }
}
