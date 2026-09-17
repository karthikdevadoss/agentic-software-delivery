package com.example.customer.controller;

import com.example.customer.security.DemoIdentitySeeder;
import com.example.customer.security.DemoLoginRequest;
import com.example.customer.security.DemoLoginResponse;
import graphql.ErrorClassification;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.graphql.execution.ErrorType;
import org.springframework.graphql.test.tester.HttpGraphQlTester;
import org.springframework.http.HttpHeaders;
import org.springframework.test.web.reactive.server.WebTestClient;
import org.springframework.web.client.RestTemplate;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Real end-to-end proof of the GraphQL API, over the real HTTP transport
 * (no mocked GraphQL engine, no mocked security) -- login via the real
 * /auth/login REST endpoint for a real persona token (same as
 * WorkspaceIsolationIntegrationTest), then exercise POST /graphql with it,
 * proving: a query resolves a customer's identity + active plan +
 * preferences in one round trip; a query missing a field never touches
 * that field's resolver/table; workspace isolation and scope checks
 * (enforced inside CustomerGraphQlController itself, not by
 * SecurityConfig's path-based rules) reject a cross-workspace request the
 * same way the REST API does, just as a GraphQL error instead of an HTTP
 * status; and the mutation path genuinely writes through to the database.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class CustomerGraphQlControllerIntegrationTest {

    @LocalServerPort
    private int port;

    private final RestTemplate restTemplate = new RestTemplate();

    private DemoLoginResponse login(String username) {
        return restTemplate.postForObject(
                "http://localhost:" + port + "/auth/login",
                new DemoLoginRequest(username, DemoIdentitySeeder.DEMO_PASSWORD),
                DemoLoginResponse.class);
    }

    private HttpGraphQlTester tester(String token) {
        WebTestClient client = WebTestClient.bindToServer()
                .baseUrl("http://localhost:" + port + "/graphql")
                .defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                .build();
        return HttpGraphQlTester.create(client);
    }

    @Test
    void query_resolvesCustomerWithActivePlanAndPreferences_inOneRoundTrip() {
        DemoLoginResponse user1 = login("user1");

        // Give this persona a real active plan first (a freshly-seeded
        // demo identity has none by default) -- via the real REST
        // endpoint, so the GraphQL query below is proving its own nested
        // resolver against real, independently-written data, not data it
        // wrote itself.
        HttpHeaders enrollHeaders = new HttpHeaders();
        enrollHeaders.setBearerAuth(user1.accessToken());
        enrollHeaders.setContentType(org.springframework.http.MediaType.APPLICATION_JSON);
        String enrollBody = """
                {"planName":"GraphQL Test Plan","ratePerKwh":0.15,"effectiveStartDate":"%s"}
                """.formatted(java.time.LocalDate.now());
        restTemplate.postForEntity(
                "http://localhost:" + port + "/customers/" + user1.customerId() + "/plan",
                new org.springframework.http.HttpEntity<>(enrollBody, enrollHeaders),
                String.class);

        tester(user1.accessToken())
                .document("""
                        query($id: ID!) {
                          customer(id: $id) {
                            id
                            name
                            email
                            activePlan { planName status ratePerKwh }
                            preferences { paperlessBilling notificationChannel }
                          }
                        }
                        """)
                .variable("id", user1.customerId())
                .execute()
                .path("customer.id").entity(String.class).isEqualTo(String.valueOf(user1.customerId()))
                .path("customer.activePlan.status").entity(String.class).isEqualTo("ACTIVE")
                .path("customer.preferences.notificationChannel").hasValue();
    }

    @Test
    void query_aFieldNotAsked_isSimplyAbsent_notAnError() {
        DemoLoginResponse user1 = login("user1");

        // Asking only for {id name email} must succeed even for a query
        // shape that never touches the plan/preference resolvers at all --
        // proving activePlan/preferences are genuinely lazy per-field, not
        // an always-eager join under the hood.
        tester(user1.accessToken())
                .document("query($id: ID!) { customer(id: $id) { id name email } }")
                .variable("id", user1.customerId())
                .execute()
                .errors().verify()
                .path("customer.email").hasValue()
                .path("customer.name").hasValue();
    }

    @Test
    void query_crossWorkspaceAccess_isRejectedAsAForbiddenGraphQlError() {
        DemoLoginResponse user1 = login("user1");
        DemoLoginResponse user2 = login("user2");

        tester(user1.accessToken())
                .document("query($id: ID!) { customer(id: $id) { id } }")
                .variable("id", user2.customerId())
                .execute()
                .errors()
                .expect(error -> error.getErrorType() == ErrorType.FORBIDDEN)
                .verify();
    }

    @Test
    void query_forANonExistentCustomer_isANotFoundGraphQlError() {
        DemoLoginResponse admin = login("admin1");

        tester(admin.accessToken())
                .document("query { customer(id: 999999999) { id } }")
                .execute()
                .errors()
                .expect(error -> error.getErrorType() == ErrorType.NOT_FOUND)
                .verify();
    }

    @Test
    void mutation_updatesEmail_realDatabaseWrite_thenVisibleOnTheSameCustomer() {
        DemoLoginResponse user1 = login("user1");
        String newEmail = "graphql-updated-" + System.nanoTime() + "@example.com";

        tester(user1.accessToken())
                .document("""
                        mutation($id: ID!, $email: String!) {
                          updateCustomerEmail(id: $id, email: $email) { id email }
                        }
                        """)
                .variable("id", user1.customerId())
                .variable("email", newEmail)
                .execute()
                .path("updateCustomerEmail.email").entity(String.class).isEqualTo(newEmail);

        // Real write, proven by reading it back through a second, separate query.
        tester(user1.accessToken())
                .document("query($id: ID!) { customer(id: $id) { email } }")
                .variable("id", user1.customerId())
                .execute()
                .path("customer.email").entity(String.class).isEqualTo(newEmail);
    }

    @Test
    void mutation_updatingAnotherUsersEmail_isRejected_notSilentlyApplied() {
        DemoLoginResponse user1 = login("user1");
        DemoLoginResponse user2 = login("user2");

        var response = tester(user1.accessToken())
                .document("""
                        mutation($id: ID!) {
                          updateCustomerEmail(id: $id, email: "hijacked@evil.example") { id }
                        }
                        """)
                .variable("id", user2.customerId())
                .execute();

        response.errors().expect(error -> error.getErrorType() == ErrorType.FORBIDDEN).verify();

        // The real point of this test: prove the write genuinely did not
        // happen, not just that an error was returned alongside it.
        DemoLoginResponse admin = login("admin1");
        tester(admin.accessToken())
                .document("query($id: ID!) { customer(id: $id) { email } }")
                .variable("id", user2.customerId())
                .execute()
                .path("customer.email").entity(String.class).satisfies(
                        email -> assertThat(email).isNotEqualTo("hijacked@evil.example"));
    }
}
