package com.example.customer.controller;

import com.example.customer.dto.CustomerEmailUpdateRequest;
import com.example.customer.model.Customer;
import com.example.customer.security.DemoJwtIssuer;
import com.example.customer.testsupport.AuthTestSupport;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Real integration tests against the actual running Spring context (real
 * embedded servlet container + real H2 database) — the exact real HTTP
 * behavior this project's Customer API has TODAY (GET by id, POST
 * create, PUT update-email, 404/409 handling). Corrected 2026-09-20
 * (BL-013): this comment previously said Update Email was untested here,
 * which was already stale — the tests below prove otherwise.
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

    /**
     * FOUNDATIONAL IMPROVEMENT (2026-09-13): GlobalExceptionHandler
     * (@RestControllerAdvice) replaces the previous inline
     * @ExceptionHandler on the controller, and now returns structured
     * JSON (an "error" field) instead of a raw plain-text string body —
     * a real gap since every OTHER endpoint on this API already returns
     * JSON.
     */
    @Test
    void getCustomer_nonExistentId_returnsStructuredJsonErrorBody() {
        assertThatThrownBy(() -> restTemplate.getForEntity(url("/customers/999999"), Map.class))
                .isInstanceOf(HttpClientErrorException.NotFound.class)
                .satisfies(ex -> {
                    HttpClientErrorException httpEx = (HttpClientErrorException) ex;
                    assertThat(httpEx.getResponseHeaders().getContentType()).isNotNull();
                    assertThat(httpEx.getResponseHeaders().getContentType().toString()).contains("json");
                    assertThat(httpEx.getResponseBodyAsString()).contains("\"error\"");
                });
    }

    /**
     * FOUNDATIONAL IMPROVEMENT (2026-09-13): Bean Validation was declared
     * as a dependency (spring-boot-starter-validation) but genuinely
     * unused anywhere in this codebase — POST /customers accepted a
     * blank name or malformed email with no rejection at all. Customer's
     * fields now carry @NotBlank/@Email constraints, enforced via
     * @Valid on the controller method, with structured 400 responses
     * from GlobalExceptionHandler.
     */
    @Test
    void createCustomer_withBlankName_returns400WithFieldError() {
        Customer request = new Customer("", "valid@example.com");

        assertThatThrownBy(() -> restTemplate.postForEntity(url("/customers"), request, Map.class))
                .isInstanceOf(HttpClientErrorException.BadRequest.class)
                .satisfies(ex -> {
                    String body = ((HttpClientErrorException) ex).getResponseBodyAsString();
                    assertThat(body).contains("\"name\"");
                });
    }

    @Test
    void createCustomer_withMalformedEmail_returns400WithFieldError() {
        Customer request = new Customer("Valid Name", "not-an-email");

        assertThatThrownBy(() -> restTemplate.postForEntity(url("/customers"), request, Map.class))
                .isInstanceOf(HttpClientErrorException.BadRequest.class)
                .satisfies(ex -> {
                    String body = ((HttpClientErrorException) ex).getResponseBodyAsString();
                    assertThat(body).contains("\"email\"");
                });
    }

    /**
     * REAL IMPLEMENTATION (2026-09-14): the project's original, long-
     * deferred "Update Email" ticket. Full round trip: update, then a
     * fresh GET confirms the new value was actually persisted, not just
     * returned in the PUT response.
     */
    @Test
    void updateEmail_persistsAndIsReturnedOnSubsequentGet() {
        Customer created = restTemplate.postForObject(
                url("/customers"), new Customer("Update Email Tester", "before@example.com"), Customer.class);

        HttpEntity<CustomerEmailUpdateRequest> request = new HttpEntity<>(new CustomerEmailUpdateRequest("after@example.com"));
        ResponseEntity<Customer> putResponse = restTemplate.exchange(
                url("/customers/" + created.getId()), HttpMethod.PUT, request, Customer.class);
        assertThat(putResponse.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(putResponse.getBody().getEmail()).isEqualTo("after@example.com");
        assertThat(putResponse.getBody().getName()).isEqualTo("Update Email Tester"); // unchanged

        ResponseEntity<Customer> getResponse = restTemplate.getForEntity(url("/customers/" + created.getId()), Customer.class);
        assertThat(getResponse.getBody().getEmail()).isEqualTo("after@example.com");
    }

    @Test
    void updateEmail_withMalformedEmail_returns400WithFieldError() {
        Customer created = restTemplate.postForObject(
                url("/customers"), new Customer("Update Email Tester", "before@example.com"), Customer.class);
        HttpEntity<CustomerEmailUpdateRequest> request = new HttpEntity<>(new CustomerEmailUpdateRequest("not-an-email"));

        assertThatThrownBy(() -> restTemplate.exchange(url("/customers/" + created.getId()), HttpMethod.PUT, request, Map.class))
                .isInstanceOf(HttpClientErrorException.BadRequest.class)
                .satisfies(ex -> {
                    String body = ((HttpClientErrorException) ex).getResponseBodyAsString();
                    assertThat(body).contains("\"email\"");
                });
    }

    @Test
    void updateEmail_forNonExistentCustomer_returns404() {
        HttpEntity<CustomerEmailUpdateRequest> request = new HttpEntity<>(new CustomerEmailUpdateRequest("someone@example.com"));

        assertThatThrownBy(() -> restTemplate.exchange(url("/customers/999999999"), HttpMethod.PUT, request, Map.class))
                .isInstanceOf(HttpClientErrorException.NotFound.class);
    }

    /**
     * REAL FIX (2026-09-20, BL-013): the original Update Email
     * implementation had no uniqueness check at all — a second customer
     * could silently take over a first customer's email. Proven here
     * against the real database, not just a mocked unit test.
     */
    @Test
    void updateEmail_toAnotherRealCustomersEmail_returns409AndLeavesBothUnchanged() {
        Customer first = restTemplate.postForObject(
                url("/customers"), new Customer("First Customer", "first@example.com"), Customer.class);
        Customer second = restTemplate.postForObject(
                url("/customers"), new Customer("Second Customer", "second@example.com"), Customer.class);

        HttpEntity<CustomerEmailUpdateRequest> request = new HttpEntity<>(new CustomerEmailUpdateRequest("first@example.com"));

        assertThatThrownBy(() -> restTemplate.exchange(url("/customers/" + second.getId()), HttpMethod.PUT, request, Map.class))
                .isInstanceOf(HttpClientErrorException.Conflict.class)
                .satisfies(ex -> {
                    String body = ((HttpClientErrorException) ex).getResponseBodyAsString();
                    assertThat(body).contains("\"error\"").contains("first@example.com");
                });

        ResponseEntity<Customer> stillSecond = restTemplate.getForEntity(url("/customers/" + second.getId()), Customer.class);
        assertThat(stillSecond.getBody().getEmail()).isEqualTo("second@example.com"); // unchanged after the rejected update
    }

    @Test
    void updateEmail_reSubmittingOwnCurrentEmail_stillReturns200() {
        Customer created = restTemplate.postForObject(
                url("/customers"), new Customer("Self Resubmit Tester", "self@example.com"), Customer.class);
        HttpEntity<CustomerEmailUpdateRequest> request = new HttpEntity<>(new CustomerEmailUpdateRequest("self@example.com"));

        ResponseEntity<Customer> response = restTemplate.exchange(
                url("/customers/" + created.getId()), HttpMethod.PUT, request, Customer.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody().getEmail()).isEqualTo("self@example.com");
    }
}
