package com.example.customer.controller;

import com.example.customer.model.Customer;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Real integration tests against the actual running Spring context (real
 * embedded servlet container + real H2 database) — the exact real HTTP
 * behavior this project's Customer API has TODAY (GET by id, POST
 * create, 404 for a missing id). Does not test Update Email or any
 * other not-yet-implemented feature — see docs/PROJECT_STATE.json:
 * Update Email remains unimplemented.
 *
 * Uses a plain org.springframework.web.client.RestTemplate rather than
 * TestRestTemplate/MockMvc: empirically confirmed (via the resolved
 * dependency tree and jar contents) that neither is on this project's
 * classpath with Spring Boot 4.1.1's current starter-web +
 * starter-test alone (Spring Boot 4's module split moved/renamed several
 * test-support classes — e.g. Jackson's ObjectMapper is now
 * tools.jackson.databind, not com.fasterxml.jackson.databind). A plain
 * RestTemplate needs no extra module and is definitionally available
 * wherever spring-boot-starter-web is.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class CustomerControllerIntegrationTest {

    @LocalServerPort
    private int port;

    private final RestTemplate restTemplate = new RestTemplate();

    private String url(String path) {
        return "http://localhost:" + port + path;
    }

    @Test
    void createCustomer_returns201WithGeneratedIdAndSubmittedFields() {
        Customer request = new Customer("Grace Hopper", "grace@example.com");

        ResponseEntity<Customer> response = restTemplate.postForEntity(url("/customers"), request, Customer.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        Customer created = response.getBody();
        assertThat(created).isNotNull();
        assertThat(created.getId()).isNotNull();
        assertThat(created.getName()).isEqualTo("Grace Hopper");
        assertThat(created.getEmail()).isEqualTo("grace@example.com");
    }

    @Test
    void getCustomer_afterRealCreate_returnsTheSameRealCustomer() {
        Customer request = new Customer("Ada Lovelace", "ada@example.com");
        Customer created = restTemplate.postForObject(url("/customers"), request, Customer.class);

        ResponseEntity<Customer> response = restTemplate.getForEntity(url("/customers/" + created.getId()), Customer.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody().getName()).isEqualTo("Ada Lovelace");
        assertThat(response.getBody().getEmail()).isEqualTo("ada@example.com");
    }

    @Test
    void getCustomer_nonExistentId_returns404WithRealNotFoundMessage() {
        assertThatThrownBy(() -> restTemplate.getForEntity(url("/customers/999999"), String.class))
                .isInstanceOf(HttpClientErrorException.NotFound.class)
                .satisfies(ex -> assertThat(((HttpClientErrorException) ex).getResponseBodyAsString()).contains("999999"));
    }
}
