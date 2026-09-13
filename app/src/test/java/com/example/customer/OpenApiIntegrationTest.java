package com.example.customer;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestTemplate;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * BUSINESS REQUIREMENT: any consumer (a recruiter, a future frontend, a
 * future downstream service) must be able to discover this API's real
 * contract without reading the source -- springdoc-openapi generates
 * /v3/api-docs FROM the actual controllers/DTOs/validation annotations,
 * so it can never drift silently from real behavior the way a
 * hand-maintained API doc could.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class OpenApiIntegrationTest {

    @LocalServerPort
    private int port;

    private final RestTemplate restTemplate = new RestTemplate();

    private String url(String path) {
        return "http://localhost:" + port + path;
    }

    @Test
    void apiDocsEndpoint_returnsRealOpenApiDescribingOurActualEndpoints() {
        ResponseEntity<String> response = restTemplate.getForEntity(url("/v3/api-docs"), String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        String body = response.getBody();
        assertThat(body).contains("\"/customers/{id}\"");
        assertThat(body).contains("\"/customers/{customerId}/preferences\"");
        assertThat(body).contains("\"/customers/{customerId}/plan\"");
    }

    @Test
    void swaggerUi_isReachable() {
        ResponseEntity<String> response = restTemplate.getForEntity(url("/swagger-ui/index.html"), String.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
    }
}
