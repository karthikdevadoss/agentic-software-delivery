package com.example.customer.security;

import com.example.customer.repository.DemoIdentityRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Real login against the real embedded server and the real
 * DemoIdentitySeeder-populated demo_identity table -- no mocking of
 * credential verification. Proves the exact contract the "FRICTIONLESS
 * REAL DEMO LOGIN" requirement asked for: known public username/password
 * pairs genuinely authenticate, a wrong password genuinely fails, and the
 * persona list is real (reflects the actual seeded rows).
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class DemoLoginControllerIntegrationTest {

    @LocalServerPort
    private int port;

    @Autowired
    private DemoIdentityRepository demoIdentityRepository;

    private final RestTemplate restTemplate = new RestTemplate();

    private String url(String path) {
        return "http://localhost:" + port + path;
    }

    @Test
    void personas_listsRealSeededUsernamesSplitByRole() {
        ResponseEntity<DemoPersonasResponse> response =
                restTemplate.getForEntity(url("/auth/personas"), DemoPersonasResponse.class);

        assertThat(response.getBody().user()).containsExactly("user1", "user2", "user3");
        assertThat(response.getBody().admin()).containsExactly("admin1", "admin2");
    }

    @Test
    void login_withKnownDemoUserCredentials_succeeds() {
        DemoLoginRequest request = new DemoLoginRequest("user1", DemoIdentitySeeder.DEMO_PASSWORD);
        ResponseEntity<DemoLoginResponse> response =
                restTemplate.postForEntity(url("/auth/login"), request, DemoLoginResponse.class);

        assertThat(response.getBody().accessToken()).isNotBlank();
        assertThat(response.getBody().username()).isEqualTo("user1");
        assertThat(response.getBody().role()).isEqualTo("USER");
        assertThat(response.getBody().customerId()).isNotNull();
    }

    @Test
    void login_withKnownDemoAdminCredentials_succeedsWithNoCustomerId() {
        DemoLoginRequest request = new DemoLoginRequest("admin1", DemoIdentitySeeder.DEMO_PASSWORD);
        ResponseEntity<DemoLoginResponse> response =
                restTemplate.postForEntity(url("/auth/login"), request, DemoLoginResponse.class);

        assertThat(response.getBody().role()).isEqualTo("ADMIN");
        assertThat(response.getBody().customerId()).isNull();
    }

    // NOTE: these two cases deliberately do NOT assert on
    // getResponseBodyAsString() -- java.net.HttpURLConnection (which
    // RestTemplate's default SimpleClientHttpRequestFactory uses) has a
    // known, JDK-level special case for HTTP 401/407 responses that can
    // discard the error body before Spring ever reads it, independent of
    // anything this server does. Every other 401 case in
    // SecurityIntegrationTest already avoids body assertions for the
    // exact same reason. The real response body was independently
    // verified correct via a direct curl against a locally running
    // instance: {"error":"invalid username or password"}, HTTP 401 --
    // see docs/PROJECT_STATE.json's verification_state for this task.

    @Test
    void login_withWrongPassword_returns401() {
        DemoLoginRequest request = new DemoLoginRequest("user1", "definitely-not-the-real-password");
        assertThatThrownBy(() -> restTemplate.postForEntity(url("/auth/login"), request, java.util.Map.class))
                .isInstanceOf(HttpClientErrorException.Unauthorized.class);
    }

    @Test
    void login_withUnknownUsername_returns401() {
        DemoLoginRequest request = new DemoLoginRequest("no-such-user", DemoIdentitySeeder.DEMO_PASSWORD);
        assertThatThrownBy(() -> restTemplate.postForEntity(url("/auth/login"), request, java.util.Map.class))
                .isInstanceOf(HttpClientErrorException.Unauthorized.class);
    }

    @Test
    void login_withDisabledIdentity_returns401() {
        // Directly exercises the enabled-state filter in
        // DemoLoginController -- the seeded personas are all enabled by
        // default, so this proves a disabled identity is genuinely
        // rejected even with the exactly correct password, not merely
        // that unknown usernames are.
        DemoLoginRequest request = new DemoLoginRequest("user1", DemoIdentitySeeder.DEMO_PASSWORD);
        // Disable the real seeded identity for this one assertion, then
        // restore it so later tests sharing this context still work.
        var identity = demoIdentityRepository.findByUsername("user1").orElseThrow();
        identity.setEnabled(false);
        demoIdentityRepository.save(identity);
        try {
            assertThatThrownBy(() -> restTemplate.postForEntity(url("/auth/login"), request, java.util.Map.class))
                    .isInstanceOf(HttpClientErrorException.Unauthorized.class);
        } finally {
            identity.setEnabled(true);
            demoIdentityRepository.save(identity);
        }
    }

    @Test
    void personaToken_grantsAccessToOwnCustomerViaGet() {
        DemoLoginResponse login = restTemplate.postForObject(
                url("/auth/login"), new DemoLoginRequest("user2", DemoIdentitySeeder.DEMO_PASSWORD), DemoLoginResponse.class);

        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(login.accessToken());
        headers.setContentType(MediaType.APPLICATION_JSON);
        ResponseEntity<String> response = restTemplate.exchange(
                url("/customers/" + login.customerId()), org.springframework.http.HttpMethod.GET,
                new HttpEntity<>(headers), String.class);

        assertThat(response.getStatusCode().value()).isEqualTo(200);
    }

    @Test
    void adminToken_carriesAdminReadScopeClaim_userTokenDoesNot() {
        DemoLoginResponse adminLogin = restTemplate.postForObject(
                url("/auth/login"), new DemoLoginRequest("admin1", DemoIdentitySeeder.DEMO_PASSWORD), DemoLoginResponse.class);
        DemoLoginResponse userLogin = restTemplate.postForObject(
                url("/auth/login"), new DemoLoginRequest("user1", DemoIdentitySeeder.DEMO_PASSWORD), DemoLoginResponse.class);

        assertThat(decodeJwtPayload(adminLogin.accessToken())).contains("admin:read");
        assertThat(decodeJwtPayload(userLogin.accessToken())).doesNotContain("admin:read");
    }

    private static String decodeJwtPayload(String jwt) {
        String[] parts = jwt.split("\\.");
        return new String(java.util.Base64.getUrlDecoder().decode(parts[1]));
    }
}
