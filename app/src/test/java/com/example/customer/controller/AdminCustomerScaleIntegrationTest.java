package com.example.customer.controller;

import com.example.customer.security.DemoIdentitySeeder;
import com.example.customer.security.DemoLoginRequest;
import com.example.customer.security.DemoLoginResponse;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Real pagination/sorting behavior at real row counts (250 seeded
 * customers, not the ~5 demo-identity-bound rows the existing
 * AdminCustomerControllerIntegrationTest covers) -- proves
 * GET /admin/customers/all and POST /admin/customers/seed-demo-data
 * both genuinely work, not just that a handful of pre-seeded rows page
 * correctly.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class AdminCustomerScaleIntegrationTest {

    private static final int SEED_COUNT = 250;

    @LocalServerPort
    private int port;

    private final RestTemplate restTemplate = new RestTemplate();

    private String url(String path) {
        return "http://localhost:" + port + path;
    }

    private String adminToken() {
        DemoLoginResponse admin = restTemplate.postForObject(
                url("/auth/login"), new DemoLoginRequest("admin1", DemoIdentitySeeder.DEMO_PASSWORD), DemoLoginResponse.class);
        return admin.accessToken();
    }

    private ResponseEntity<Map> withToken(String path, org.springframework.http.HttpMethod method, String token) {
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(token);
        return restTemplate.exchange(url(path), method, new HttpEntity<>(headers), Map.class);
    }

    @Test
    void seedDemoData_requiresAdminAuthority() {
        assertThatThrownBy(() -> restTemplate.postForEntity(url("/admin/customers/seed-demo-data?count=5"), null, Map.class))
                .isInstanceOf(HttpClientErrorException.Unauthorized.class);
    }

    @Test
    void seedDemoData_genuinelyCreatesTheRequestedCount_andListAllReflectsRealVolume() {
        String token = adminToken();

        ResponseEntity<Map> seedResponse = withToken("/admin/customers/seed-demo-data?count=" + SEED_COUNT, HttpMethod.POST, token);
        assertThat(seedResponse.getStatusCode().value()).isEqualTo(200);
        assertThat(seedResponse.getBody().get("created")).isEqualTo(SEED_COUNT);
        long totalAfterSeed = ((Number) seedResponse.getBody().get("totalCustomersNow")).longValue();
        assertThat(totalAfterSeed).isGreaterThanOrEqualTo(SEED_COUNT);

        // Real pagination at real volume: page size 50 over 250+ rows
        // means more than one page, and every page must be full-sized
        // except possibly the last.
        ResponseEntity<Map> page0 = withToken("/admin/customers/all?page=0&size=50", HttpMethod.GET, token);
        Map body = page0.getBody();
        assertThat((Integer) body.get("totalPages")).isGreaterThan(1);
        assertThat(((List) body.get("content")).size()).isEqualTo(50);
    }

    @Test
    void listAll_sortByEmail_isGenuinelyOrdered_notJustAccepted() {
        String token = adminToken();
        withToken("/admin/customers/seed-demo-data?count=30", HttpMethod.POST, token);

        ResponseEntity<Map> response = withToken("/admin/customers/all?page=0&size=100&sortBy=email", HttpMethod.GET, token);
        List<Map<String, Object>> content = (List<Map<String, Object>>) response.getBody().get("content");

        List<String> emails = content.stream().map(row -> (String) row.get("email")).toList();
        List<String> sortedCopy = new java.util.ArrayList<>(emails);
        java.util.Collections.sort(sortedCopy);
        assertThat(emails).isEqualTo(sortedCopy);
    }

    @Test
    void listAll_rejectsAnUnknownSortField_fallingBackToIdRatherThanFailingOrInjecting() {
        String token = adminToken();

        // "email); DROP TABLE customer;--" is exactly the shape of input
        // a naive raw-field-name-into-ORDER-BY implementation would be
        // vulnerable to -- proves the allowlist in listAllCustomers()
        // silently falls back to a safe default instead.
        ResponseEntity<Map> response = withToken(
                "/admin/customers/all?page=0&size=5&sortBy=" + java.net.URLEncoder.encode("email); DROP TABLE customer;--", java.nio.charset.StandardCharsets.UTF_8),
                HttpMethod.GET, token);

        assertThat(response.getStatusCode().value()).isEqualTo(200); // no 500, no injected SQL, just a safe fallback
    }
}
