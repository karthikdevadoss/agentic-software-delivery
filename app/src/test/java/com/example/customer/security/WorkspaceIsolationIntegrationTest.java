package com.example.customer.security;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * The core proof behind "PERSISTENT DEMO WORKSPACE" / "USER EXPERIENCE"
 * (docs: the mega-prompt's Priority 3): a real logged-in USER persona
 * token can read/write its OWN customer's data but is genuinely rejected
 * -- server-side, not merely by a hidden UI button -- when it targets
 * another persona's customer, across every customer-scoped endpoint. An
 * ADMIN persona token bypasses this on purpose. All tokens here come from
 * the real /auth/login endpoint and the real DemoIdentitySeeder-seeded
 * rows -- nothing hand-constructed or mocked.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class WorkspaceIsolationIntegrationTest {

    @LocalServerPort
    private int port;

    private final RestTemplate restTemplate = new RestTemplate();

    private String url(String path) {
        return "http://localhost:" + port + path;
    }

    private DemoLoginResponse login(String username) {
        return restTemplate.postForObject(
                url("/auth/login"), new DemoLoginRequest(username, DemoIdentitySeeder.DEMO_PASSWORD), DemoLoginResponse.class);
    }

    private <T> ResponseEntity<T> withToken(String token, HttpMethod method, String path, Class<T> responseType) {
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(token);
        return restTemplate.exchange(url(path), method, new HttpEntity<>(headers), responseType);
    }

    @Test
    void user_canReadOwnCustomer() {
        DemoLoginResponse user1 = login("user1");
        ResponseEntity<String> response = withToken(user1.accessToken(), HttpMethod.GET, "/customers/" + user1.customerId(), String.class);
        assertThat(response.getStatusCode().value()).isEqualTo(200);
    }

    @Test
    void user_cannotReadAnotherUsersCustomer_returns403() {
        DemoLoginResponse user1 = login("user1");
        DemoLoginResponse user2 = login("user2");

        assertThatThrownBy(() -> withToken(user1.accessToken(), HttpMethod.GET, "/customers/" + user2.customerId(), String.class))
                .isInstanceOf(HttpClientErrorException.Forbidden.class);
    }

    @Test
    void user_cannotUpdateAnotherUsersEmail_returns403() {
        DemoLoginResponse user1 = login("user1");
        DemoLoginResponse user2 = login("user2");

        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(user1.accessToken());
        headers.setContentType(org.springframework.http.MediaType.APPLICATION_JSON);
        HttpEntity<String> body = new HttpEntity<>("{\"email\":\"hijacked@evil.example\"}", headers);

        assertThatThrownBy(() -> restTemplate.exchange(
                url("/customers/" + user2.customerId()), HttpMethod.PUT, body, String.class))
                .isInstanceOf(HttpClientErrorException.Forbidden.class);
    }

    @Test
    void user_cannotReadAnotherUsersPreferences_returns403() {
        DemoLoginResponse user1 = login("user1");
        DemoLoginResponse user2 = login("user2");

        assertThatThrownBy(() -> withToken(user1.accessToken(), HttpMethod.GET,
                "/customers/" + user2.customerId() + "/preferences", String.class))
                .isInstanceOf(HttpClientErrorException.Forbidden.class);
    }

    @Test
    void user_cannotReadAnotherUsersContractPlan_returns403() {
        DemoLoginResponse user1 = login("user1");
        DemoLoginResponse user2 = login("user2");

        assertThatThrownBy(() -> withToken(user1.accessToken(), HttpMethod.GET,
                "/customers/" + user2.customerId() + "/plan", String.class))
                .isInstanceOf(HttpClientErrorException.Forbidden.class);
    }

    @Test
    void user_cannotReadAnotherUsersAppointmentAvailability_returns403() {
        DemoLoginResponse user1 = login("user1");
        DemoLoginResponse user3 = login("user3");
        String date = LocalDate.now().plusDays(3).toString();

        assertThatThrownBy(() -> withToken(user1.accessToken(), HttpMethod.GET,
                "/customers/" + user3.customerId() + "/appointment-availability?date=" + date, String.class))
                .isInstanceOf(HttpClientErrorException.Forbidden.class);
    }

    @Test
    void admin_canReadAnyUsersCustomer() {
        DemoLoginResponse admin = login("admin1");
        DemoLoginResponse user3 = login("user3");

        ResponseEntity<String> response = withToken(admin.accessToken(), HttpMethod.GET, "/customers/" + user3.customerId(), String.class);
        assertThat(response.getStatusCode().value()).isEqualTo(200);
    }

    @Test
    void distinctUserPersonas_areBoundToDistinctRealCustomerRows() {
        DemoLoginResponse user1 = login("user1");
        DemoLoginResponse user2 = login("user2");
        DemoLoginResponse user3 = login("user3");

        assertThat(user1.customerId()).isNotEqualTo(user2.customerId());
        assertThat(user2.customerId()).isNotEqualTo(user3.customerId());
        assertThat(user1.customerId()).isNotEqualTo(user3.customerId());
    }
}
