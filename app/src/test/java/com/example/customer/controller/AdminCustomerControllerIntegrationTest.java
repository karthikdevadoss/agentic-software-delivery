package com.example.customer.controller;

import com.example.customer.model.Customer;
import com.example.customer.repository.CustomerRepository;
import com.example.customer.security.DemoIdentitySeeder;
import com.example.customer.security.DemoLoginRequest;
import com.example.customer.security.DemoLoginResponse;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * The real ADMIN "All Customers" dashboard: server-side pagination and
 * search (never a client-side filter over a full fetch), scoped to the
 * current demo workspace (the 3 real, demo_identity-bound Customer rows),
 * with the exact regression coverage named for this feature: pagination,
 * search by id/name/email, empty search, no-result search, USER 403 on
 * the ADMIN endpoint, cross-workspace isolation, ADMIN opening a
 * customer, a USER's own change being visible to ADMIN, and persistence
 * surviving a fresh login (the real proxy for "logout, then log back
 * in" -- there is no server-side session to expire beyond the JWT
 * itself, so a second independent /auth/login call is the correct real
 * equivalent).
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class AdminCustomerControllerIntegrationTest {

    @LocalServerPort
    private int port;

    @Autowired
    private CustomerRepository customerRepository;

    private final RestTemplate restTemplate = new RestTemplate();

    private String url(String path) {
        return "http://localhost:" + port + path;
    }

    private DemoLoginResponse login(String username) {
        return restTemplate.postForObject(
                url("/auth/login"), new DemoLoginRequest(username, DemoIdentitySeeder.DEMO_PASSWORD), DemoLoginResponse.class);
    }

    private ResponseEntity<Map> getWithToken(String path, String token) {
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(token);
        return restTemplate.exchange(url(path), HttpMethod.GET, new HttpEntity<>(headers), Map.class);
    }

    @Test
    void admin_listsAllWorkspaceCustomers_withPagination() {
        DemoLoginResponse admin = login("admin1");
        ResponseEntity<Map> response = getWithToken("/admin/customers?page=0&size=20", admin.accessToken());

        assertThat(response.getStatusCode().value()).isEqualTo(200);
        Map body = response.getBody();
        assertThat(((java.util.List) body.get("content")).size()).isGreaterThanOrEqualTo(3);
        assertThat(body.get("totalElements")).isNotNull();
        assertThat((Integer) body.get("totalPages")).isGreaterThanOrEqualTo(1);
    }

    @Test
    void admin_searchesByCustomerId() {
        DemoLoginResponse admin = login("admin1");
        DemoLoginResponse user1 = login("user1");

        ResponseEntity<Map> response = getWithToken("/admin/customers?customerId=" + user1.customerId(), admin.accessToken());
        java.util.List content = (java.util.List) response.getBody().get("content");
        assertThat(content).hasSize(1);
        assertThat(((Map) content.get(0)).get("customerId")).isEqualTo(user1.customerId().intValue());
    }

    @Test
    void admin_searchesByName() {
        DemoLoginResponse admin = login("admin1");
        // Seeded real name for user1, see DemoIdentitySeeder.
        ResponseEntity<Map> response = getWithToken("/admin/customers?name=Alex", admin.accessToken());
        java.util.List content = (java.util.List) response.getBody().get("content");
        assertThat(content).isNotEmpty();
        assertThat(content).allSatisfy(row -> assertThat(((String) ((Map) row).get("name"))).containsIgnoringCase("alex"));
    }

    @Test
    void admin_searchesByEmail() {
        DemoLoginResponse admin = login("admin1");
        // A literal "@", not a pre-percent-encoded "%40" -- RestTemplate's
        // exchange(String, ...) treats its URL argument as a template and
        // encodes it itself; pre-encoding here would double-encode.
        ResponseEntity<Map> response = getWithToken("/admin/customers?email=user1@energydemo.local", admin.accessToken());
        java.util.List content = (java.util.List) response.getBody().get("content");
        assertThat(content).hasSize(1);
        assertThat(((Map) content.get(0)).get("email")).isEqualTo("user1@energydemo.local");
    }

    @Test
    void admin_emptySearch_returnsAllWorkspaceCustomers() {
        DemoLoginResponse admin = login("admin1");
        ResponseEntity<Map> response = getWithToken("/admin/customers", admin.accessToken());
        java.util.List content = (java.util.List) response.getBody().get("content");
        assertThat(content.size()).isGreaterThanOrEqualTo(3);
    }

    @Test
    void admin_noResultSearch_returnsEmptyPageNotError() {
        DemoLoginResponse admin = login("admin1");
        ResponseEntity<Map> response = getWithToken("/admin/customers?name=NoSuchPersonNameAtAll12345", admin.accessToken());
        assertThat(response.getStatusCode().value()).isEqualTo(200);
        java.util.List content = (java.util.List) response.getBody().get("content");
        assertThat(content).isEmpty();
    }

    @Test
    void user_cannotCallAdminEndpoint_returns403() {
        DemoLoginResponse user1 = login("user1");
        assertThatThrownBy(() -> getWithToken("/admin/customers", user1.accessToken()))
                .isInstanceOf(HttpClientErrorException.Forbidden.class);
    }

    @Test
    void crossWorkspaceIsolation_strayNonDemoCustomerNeverListed() {
        // A Customer row NOT bound to any demo_identity (e.g. historical
        // clutter from the old anonymous-token auto-create flow) must
        // never appear in "the current demo workspace" -- real DB proof,
        // not a mocked assumption.
        Customer stray = customerRepository.save(new Customer("Stray Nobody", "stray-nobody@example.com"));

        DemoLoginResponse admin = login("admin1");
        ResponseEntity<Map> response = getWithToken("/admin/customers?customerId=" + stray.getId(), admin.accessToken());
        java.util.List content = (java.util.List) response.getBody().get("content");
        assertThat(content).isEmpty();
    }

    @Test
    void admin_opensCustomer_seesRealPersistedData() {
        DemoLoginResponse admin = login("admin1");
        DemoLoginResponse user3 = login("user3");

        ResponseEntity<Map> response = getWithToken("/customers/" + user3.customerId(), admin.accessToken());
        assertThat(response.getStatusCode().value()).isEqualTo(200);
        assertThat(response.getBody().get("id")).isEqualTo(user3.customerId().intValue());
    }

    @Test
    void usersOwnChange_isVisibleToAdmin() {
        DemoLoginResponse user2 = login("user2");
        String newEmail = "user2-changed-" + System.nanoTime() + "@energydemo.local";

        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(user2.accessToken());
        headers.setContentType(MediaType.APPLICATION_JSON);
        restTemplate.exchange(url("/customers/" + user2.customerId()), HttpMethod.PUT,
                new HttpEntity<>(Map.of("email", newEmail), headers), Map.class);

        DemoLoginResponse admin = login("admin1");
        ResponseEntity<Map> adminView = getWithToken("/admin/customers?customerId=" + user2.customerId(), admin.accessToken());
        java.util.List content = (java.util.List) adminView.getBody().get("content");
        assertThat(((Map) content.get(0)).get("email")).isEqualTo(newEmail);
    }

    @Test
    void persistedChange_survivesAFreshLogin() {
        // The real equivalent of "logout, then log back in": there is no
        // server-side session beyond the JWT itself, so a second,
        // independent /auth/login call is the correct real proxy for a
        // returning visitor -- proves the change lives in Postgres, not
        // in any per-session state. Uses user3 (not user1/user2) so this
        // permanent mutation cannot race against admin_searchesByEmail's
        // and usersOwnChange_isVisibleToAdmin's own exact-value
        // assertions on the other two personas under JUnit 5's
        // unordered execution.
        DemoLoginResponse firstLogin = login("user3");
        String newEmail = "user3-relogin-" + System.nanoTime() + "@energydemo.local";

        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(firstLogin.accessToken());
        headers.setContentType(MediaType.APPLICATION_JSON);
        restTemplate.exchange(url("/customers/" + firstLogin.customerId()), HttpMethod.PUT,
                new HttpEntity<>(Map.of("email", newEmail), headers), Map.class);

        DemoLoginResponse secondLogin = login("user3"); // simulates logout + relogin
        assertThat(secondLogin.customerId()).isEqualTo(firstLogin.customerId());
        ResponseEntity<Map> afterRelogin = getWithToken("/customers/" + secondLogin.customerId(), secondLogin.accessToken());
        assertThat(afterRelogin.getBody().get("email")).isEqualTo(newEmail);
    }
}
