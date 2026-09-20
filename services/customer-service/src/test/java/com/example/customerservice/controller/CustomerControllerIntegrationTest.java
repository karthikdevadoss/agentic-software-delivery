package com.example.customerservice.controller;

import com.example.customerservice.dto.CustomerEmailUpdateRequest;
import com.example.customerservice.model.Customer;
import com.example.customerservice.security.DemoJwtIssuer;
import com.example.customerservice.testsupport.AuthTestSupport;
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
 * embedded servlet container + real H2 database), ported from the
 * monolith's CustomerControllerIntegrationTest.
 *
 * Uses a plain org.springframework.web.client.RestTemplate rather than
 * TestRestTemplate/MockMvc: neither is on this Spring Boot 4.1.1
 * project's classpath (Jackson's module split moved ObjectMapper to
 * tools.jackson.databind, same as the monolith -- see that class's
 * original Javadoc for the full explanation). A plain RestTemplate needs
 * no extra module and is definitionally available wherever
 * spring-boot-starter-web is.
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
}
