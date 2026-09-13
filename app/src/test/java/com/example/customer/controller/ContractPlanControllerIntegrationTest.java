package com.example.customer.controller;

import com.example.customer.dto.ContractPlanEnrollRequest;
import com.example.customer.model.Customer;
import org.junit.jupiter.api.Test;
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

    private final RestTemplate restTemplate = new RestTemplate();

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
