package com.example.meteringservice.controller;

import com.example.meteringservice.dto.MeterReadingResponse;
import com.example.meteringservice.dto.UsageSummaryResponse;
import com.example.meteringservice.testsupport.TestJwtIssuer;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

import java.math.BigDecimal;
import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.assertThrows;

/**
 * Real end-to-end coverage over an actual running server (MockMvc is not
 * on this classpath -- see pom.xml -- so, like the monolith's own
 * RestTemplate-based integration tests, these hit the real embedded
 * Tomcat, real Spring Security filter chain, real H2-backed JPA
 * persistence, and real controller/service/repository wiring together).
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class MeterReadingControllerIntegrationTest {

    @LocalServerPort
    private int port;

    @Value("${app.security.jwt.issuer}")
    private String jwtIssuer;

    @Value("${app.security.jwt.audience}")
    private String jwtAudience;

    private RestTemplate restTemplate;

    @BeforeEach
    void setUp() {
        restTemplate = new RestTemplate();
    }

    private String baseUrl() {
        return "http://localhost:" + port;
    }

    private HttpHeaders authHeaders(String role, Long customerId) {
        String token = TestJwtIssuer.issueToken(jwtIssuer, jwtAudience, role, customerId);
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(token);
        return headers;
    }

    @Test
    void submitReading_thenReadBackInHistory() {
        HttpHeaders headers = authHeaders("USER", 101L);
        String body = """
                {"meterId":"METER-101-A","readingDate":"2026-09-10","kWhConsumed":42.5}
                """;
        headers.setContentType(org.springframework.http.MediaType.APPLICATION_JSON);
        HttpEntity<String> submitRequest = new HttpEntity<>(body, headers);

        ResponseEntity<MeterReadingResponse> submitResponse = restTemplate.postForEntity(
                baseUrl() + "/customers/101/meter-readings", submitRequest, MeterReadingResponse.class);

        assertThat(submitResponse.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        assertThat(submitResponse.getBody()).isNotNull();
        assertThat(submitResponse.getBody().meterId()).isEqualTo("METER-101-A");
        assertThat(submitResponse.getBody().kWhConsumed()).isEqualByComparingTo("42.5");

        HttpEntity<Void> getRequest = new HttpEntity<>(authHeaders("USER", 101L));
        ResponseEntity<MeterReadingResponse[]> historyResponse = restTemplate.exchange(
                baseUrl() + "/customers/101/meter-readings", HttpMethod.GET, getRequest, MeterReadingResponse[].class);

        assertThat(historyResponse.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(historyResponse.getBody()).isNotNull();
        assertThat(historyResponse.getBody()).anyMatch(r -> "METER-101-A".equals(r.meterId()));
    }

    @Test
    void usageSummary_reflectsRealSubmittedReadingsForThePeriod() {
        Long customerId = 202L;
        HttpHeaders postHeaders = authHeaders("USER", customerId);
        postHeaders.setContentType(org.springframework.http.MediaType.APPLICATION_JSON);

        submit(customerId, postHeaders, "METER-202", "2026-08-05", "10.000");
        submit(customerId, postHeaders, "METER-202", "2026-08-20", "15.500");
        // Outside the queried period (September) -- must NOT be included in the August summary.
        submit(customerId, postHeaders, "METER-202", "2026-09-05", "999.000");

        HttpEntity<Void> getRequest = new HttpEntity<>(authHeaders("USER", customerId));
        ResponseEntity<UsageSummaryResponse> summaryResponse = restTemplate.exchange(
                baseUrl() + "/customers/" + customerId + "/usage-summary?from=2026-08-01&to=2026-08-31",
                HttpMethod.GET, getRequest, UsageSummaryResponse.class);

        assertThat(summaryResponse.getStatusCode()).isEqualTo(HttpStatus.OK);
        UsageSummaryResponse summary = summaryResponse.getBody();
        assertThat(summary).isNotNull();
        assertThat(summary.totalKwhConsumed()).isEqualByComparingTo("25.500");
        assertThat(summary.readingCount()).isEqualTo(2);
        assertThat(summary.periodStart()).isEqualTo(LocalDate.of(2026, 8, 1));
        assertThat(summary.periodEnd()).isEqualTo(LocalDate.of(2026, 8, 31));
    }

    @Test
    void usageSummary_forACustomerWithNoReadingsInThePeriod_isExplicitlyZeroNotAnError() {
        Long customerId = 303L;
        HttpEntity<Void> getRequest = new HttpEntity<>(authHeaders("USER", customerId));

        ResponseEntity<UsageSummaryResponse> summaryResponse = restTemplate.exchange(
                baseUrl() + "/customers/" + customerId + "/usage-summary?from=2026-01-01&to=2026-01-31",
                HttpMethod.GET, getRequest, UsageSummaryResponse.class);

        assertThat(summaryResponse.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(summaryResponse.getBody()).isNotNull();
        assertThat(summaryResponse.getBody().totalKwhConsumed()).isEqualByComparingTo(BigDecimal.ZERO);
        assertThat(summaryResponse.getBody().readingCount()).isEqualTo(0L);
    }

    @Test
    void workspaceIsolation_userTokenForCustomerA_cannotReadCustomerBsReadings() {
        Long customerA = 401L;
        Long customerB = 402L;
        HttpHeaders postHeadersB = authHeaders("USER", customerB);
        postHeadersB.setContentType(org.springframework.http.MediaType.APPLICATION_JSON);
        submit(customerB, postHeadersB, "METER-B", "2026-09-01", "5.000");

        // Token bound to customer A's cid attempts to read customer B's history.
        HttpEntity<Void> crossTenantRequest = new HttpEntity<>(authHeaders("USER", customerA));

        HttpClientErrorException.Forbidden thrown = assertThrows(HttpClientErrorException.Forbidden.class,
                () -> restTemplate.exchange(baseUrl() + "/customers/" + customerB + "/meter-readings",
                        HttpMethod.GET, crossTenantRequest, MeterReadingResponse[].class));

        assertThat(thrown.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
    }

    @Test
    void workspaceIsolation_userTokenForCustomerA_cannotSubmitReadingForCustomerB() {
        Long customerA = 501L;
        Long customerB = 502L;
        HttpHeaders headers = authHeaders("USER", customerA);
        headers.setContentType(org.springframework.http.MediaType.APPLICATION_JSON);
        String body = """
                {"meterId":"METER-INTRUDER","readingDate":"2026-09-10","kWhConsumed":1.0}
                """;
        HttpEntity<String> request = new HttpEntity<>(body, headers);

        HttpClientErrorException.Forbidden thrown = assertThrows(HttpClientErrorException.Forbidden.class,
                () -> restTemplate.postForEntity(baseUrl() + "/customers/" + customerB + "/meter-readings",
                        request, MeterReadingResponse.class));

        assertThat(thrown.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
    }

    @Test
    void submitReading_futureDateRejectedWithBadRequest() {
        HttpHeaders headers = authHeaders("USER", 601L);
        headers.setContentType(org.springframework.http.MediaType.APPLICATION_JSON);
        String body = """
                {"meterId":"METER-601","readingDate":"2099-01-01","kWhConsumed":1.0}
                """;
        HttpEntity<String> request = new HttpEntity<>(body, headers);

        HttpClientErrorException.BadRequest thrown = assertThrows(HttpClientErrorException.BadRequest.class,
                () -> restTemplate.postForEntity(baseUrl() + "/customers/601/meter-readings", request, MeterReadingResponse.class));

        assertThat(thrown.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
    }

    @Test
    void submitReading_nonPositiveKwh_rejectedWithBadRequest() {
        HttpHeaders headers = authHeaders("USER", 602L);
        headers.setContentType(org.springframework.http.MediaType.APPLICATION_JSON);
        String body = """
                {"meterId":"METER-602","readingDate":"2026-09-10","kWhConsumed":0}
                """;
        HttpEntity<String> request = new HttpEntity<>(body, headers);

        HttpClientErrorException.BadRequest thrown = assertThrows(HttpClientErrorException.BadRequest.class,
                () -> restTemplate.postForEntity(baseUrl() + "/customers/602/meter-readings", request, MeterReadingResponse.class));

        assertThat(thrown.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
    }

    @Test
    void unauthenticatedRequest_rejectedWithUnauthorized() {
        HttpClientErrorException.Unauthorized thrown = assertThrows(HttpClientErrorException.Unauthorized.class,
                () -> restTemplate.getForEntity(baseUrl() + "/customers/701/meter-readings", MeterReadingResponse[].class));

        assertThat(thrown.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    private void submit(Long customerId, HttpHeaders headers, String meterId, String date, String kwh) {
        String body = "{\"meterId\":\"" + meterId + "\",\"readingDate\":\"" + date + "\",\"kWhConsumed\":" + kwh + "}";
        HttpEntity<String> request = new HttpEntity<>(body, headers);
        ResponseEntity<MeterReadingResponse> response = restTemplate.postForEntity(
                baseUrl() + "/customers/" + customerId + "/meter-readings", request, MeterReadingResponse.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CREATED);
    }
}
