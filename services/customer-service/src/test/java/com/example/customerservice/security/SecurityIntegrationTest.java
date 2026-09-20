package com.example.customerservice.security;

import com.example.customerservice.model.Customer;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

import java.time.Duration;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * FAILURE-FIRST security testing against the real embedded server and
 * real JWT decoder, ported from the monolith's SecurityIntegrationTest
 * (customer/auth-relevant subset only -- no contract/appointment/admin
 * endpoints exist in this service): no token, malformed token, wrong
 * signature, expired token, wrong issuer/audience, wrong scope, and the
 * positive valid-token case. Also proves the demo issuer structurally
 * cannot grant anything beyond its fixed business scope set.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class SecurityIntegrationTest {

    @LocalServerPort
    private int port;

    @Autowired
    private DemoJwtIssuer demoJwtIssuer;

    private final RestTemplate restTemplate = new RestTemplate();

    private String url(String path) {
        return "http://localhost:" + port + path;
    }

    private ResponseEntity<String> getWithToken(String path, String token) {
        HttpHeaders headers = new HttpHeaders();
        if (token != null) {
            headers.setBearerAuth(token);
        }
        return restTemplate.exchange(url(path), HttpMethod.GET, new HttpEntity<>(headers), String.class);
    }

    @Test
    void demoTokenEndpoint_isPublic_andReturnsARealSignedToken() {
        ResponseEntity<Map> response = restTemplate.postForEntity(url("/auth/demo-token"), null, Map.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody().get("access_token")).isNotNull();
        assertThat(response.getBody().get("token_type")).isEqualTo("Bearer");
        assertThat((String) response.getBody().get("scope")).contains("customer:read");
    }

    @Test
    void demoIssuer_neverGrantsAnyScopeBeyondTheFixedBusinessSet() {
        assertThat(DemoJwtIssuer.DEMO_SCOPES).noneMatch(scope ->
                scope.contains("admin") || scope.contains("owner") || scope.contains("deploy")
                        || scope.contains("infra") || scope.contains("secret") || scope.contains("shell")
                        || scope.contains("workbench"));
    }

    @Test
    void protectedEndpoint_withNoToken_returns401() {
        assertThatThrownBy(() -> getWithToken("/customers/1", null))
                .isInstanceOf(HttpClientErrorException.Unauthorized.class);
    }

    @Test
    void protectedEndpoint_withMalformedToken_returns401() {
        assertThatThrownBy(() -> getWithToken("/customers/1", "not-a-real-jwt-at-all"))
                .isInstanceOf(HttpClientErrorException.Unauthorized.class);
    }

    @Test
    void protectedEndpoint_withWrongSignature_returns401() {
        // Same claims/shape as a real demo token, but signed with a
        // completely different secret -- must be rejected on signature
        // alone, before any claim is even inspected.
        DemoJwtIssuer forgedIssuer = new DemoJwtIssuer(
                "a-completely-different-signing-secret-that-does-not-match-production-at-all-32bytes",
                "agentic-delivery-customer-service-demo-issuer",
                "customer-service",
                900);
        String forgedToken = forgedIssuer.issueDemoToken();

        assertThatThrownBy(() -> getWithToken("/customers/1", forgedToken))
                .isInstanceOf(HttpClientErrorException.Unauthorized.class);
    }

    @Test
    void protectedEndpoint_withExpiredToken_returns401() {
        String expiredToken = demoJwtIssuer.issueToken(DemoJwtIssuer.DEMO_SCOPES, Duration.ofSeconds(-10));

        assertThatThrownBy(() -> getWithToken("/customers/1", expiredToken))
                .isInstanceOf(HttpClientErrorException.Unauthorized.class);
    }

    @Test
    void protectedEndpoint_withWrongIssuer_returns401() {
        DemoJwtIssuer wrongIssuer = new DemoJwtIssuer(
                sameSecretAsProduction(),
                "some-other-issuer-nobody-configured",
                "customer-service",
                900);
        String token = wrongIssuer.issueDemoToken();

        assertThatThrownBy(() -> getWithToken("/customers/1", token))
                .isInstanceOf(HttpClientErrorException.Unauthorized.class);
    }

    @Test
    void protectedEndpoint_withWrongAudience_returns401() {
        DemoJwtIssuer wrongAudience = new DemoJwtIssuer(
                sameSecretAsProduction(),
                "agentic-delivery-customer-service-demo-issuer",
                "some-other-app-entirely",
                900);
        String token = wrongAudience.issueDemoToken();

        assertThatThrownBy(() -> getWithToken("/customers/1", token))
                .isInstanceOf(HttpClientErrorException.Unauthorized.class);
    }

    @Test
    void validToken_withCorrectScope_isAllowed() {
        String token = restTemplate.postForObject(url("/auth/demo-token"), null, Map.class).get("access_token").toString();

        // A genuinely correct token against a real endpoint: 404 (not
        // 401/403) proves authentication+authorization succeeded and the
        // request reached the actual business logic.
        assertThatThrownBy(() -> getWithToken("/customers/999999999", token))
                .isInstanceOf(HttpClientErrorException.NotFound.class);
    }

    @Test
    void validToken_missingRequiredScope_returns403() {
        // A real, correctly-signed/issued token, but deliberately narrow:
        // only preference:read, never customer:read -- must be rejected
        // by authorization, not authentication.
        String narrowToken = demoJwtIssuer.issueToken(Set.of("preference:read"), Duration.ofMinutes(5));

        assertThatThrownBy(() -> getWithToken("/customers/1", narrowToken))
                .isInstanceOf(HttpClientErrorException.Forbidden.class);
    }

    @Test
    void createCustomer_withoutWriteScope_returns403() {
        String readOnlyToken = demoJwtIssuer.issueToken(Set.of("customer:read"), Duration.ofMinutes(5));
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(readOnlyToken);
        HttpEntity<Customer> request = new HttpEntity<>(new Customer("Blocked", "blocked@example.com"), headers);

        assertThatThrownBy(() -> restTemplate.postForEntity(url("/customers"), request, Customer.class))
                .isInstanceOf(HttpClientErrorException.Forbidden.class);
    }

    @Test
    void publicEndpoints_remainReachableWithNoToken() {
        assertThat(restTemplate.getForEntity(url("/auth/personas"), String.class).getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(restTemplate.getForEntity(url("/actuator/health"), String.class).getStatusCode()).isEqualTo(HttpStatus.OK);
    }

    private String sameSecretAsProduction() {
        // The default local/CI signing secret from application.properties
        // -- reused here only to isolate issuer/audience as the SOLE
        // variable under test, proving those checks fire independently of
        // signature validity.
        return "local-dev-only-insecure-demo-signing-secret-never-use-in-real-production-32-bytes-minimum";
    }
}
