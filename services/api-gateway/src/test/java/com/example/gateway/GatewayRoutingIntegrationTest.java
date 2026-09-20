package com.example.gateway;

import com.github.tomakehurst.wiremock.junit5.WireMockExtension;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.RegisterExtension;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.web.client.RestClient;

import static com.github.tomakehurst.wiremock.client.WireMock.aResponse;
import static com.github.tomakehurst.wiremock.client.WireMock.equalTo;
import static com.github.tomakehurst.wiremock.client.WireMock.get;
import static com.github.tomakehurst.wiremock.client.WireMock.getRequestedFor;
import static com.github.tomakehurst.wiremock.client.WireMock.urlPathEqualTo;
import static org.assertj.core.api.Assertions.assertThat;

/**
 * ACT-014 / BL-024: real proof that GatewayRoutesConfig's routing table
 * and the lb()+uri() filter chain actually forward a real HTTP request to
 * the right real downstream -- not just that the RouterFunction bean
 * exists (ApiGatewayApplicationTests already covers that).
 *
 * Uses TWO separate real WireMock servers, one per simulated downstream
 * service id (customer-service, billing-service), wired in via
 * spring.cloud.discovery.client.simple.instances.<id>[0].uri --
 * SimpleDiscoveryClientAutoConfiguration activates because the real
 * Eureka client is disabled for the test profile (see
 * application-test.properties), so GatewayRoutesConfig's real lb(...)
 * filters resolve service ids against these two real stub servers exactly
 * the way they would resolve them against real Eureka-registered
 * instances in production -- GatewayRoutesConfig itself is completely
 * unmodified for this test.
 *
 * Using two DISTINCT WireMock instances (not one shared one) is
 * deliberate, not incidental: GatewayRoutesConfig's own Javadoc documents
 * a real ordering risk -- the broad "/customers/**" catch-all route to
 * customer-service must lose to the more specific "/customers/*&#47;plan"
 * route to billing-service. A single shared backend could not tell those
 * two failure modes apart (both would "work"); asserting which of the
 * two real, independent servers actually received the request is the
 * only way to prove the right ROUTE, not just any route, was taken.
 *
 * Header-propagation assertions follow docs/TESTING_ARCHITECTURE_V1.md's
 * §S convention: assert on the real outbound request (not just the
 * response), with a distinct per-call Authorization value -- the gateway
 * is documented (GatewayRoutesConfig's own Javadoc) to pass Authorization
 * straight through untouched, and a response-only assertion could not
 * catch a regression that silently dropped or mangled it.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class GatewayRoutingIntegrationTest {

    @RegisterExtension
    static WireMockExtension customerServiceStub = WireMockExtension.newInstance().options(
            com.github.tomakehurst.wiremock.core.WireMockConfiguration.wireMockConfig().dynamicPort()
    ).build();

    @RegisterExtension
    static WireMockExtension billingServiceStub = WireMockExtension.newInstance().options(
            com.github.tomakehurst.wiremock.core.WireMockConfiguration.wireMockConfig().dynamicPort()
    ).build();

    @DynamicPropertySource
    static void discoveryStubs(DynamicPropertyRegistry registry) {
        registry.add("spring.cloud.discovery.client.simple.instances.customer-service[0].uri", customerServiceStub::baseUrl);
        registry.add("spring.cloud.discovery.client.simple.instances.billing-service[0].uri", billingServiceStub::baseUrl);
    }

    @LocalServerPort
    private int gatewayPort;

    private final RestClient restClient = RestClient.create();

    @BeforeEach
    void resetStubs() {
        customerServiceStub.resetAll();
        billingServiceStub.resetAll();
    }

    @Test
    void bareCustomerRoute_forwardsToCustomerService_andPropagatesTheRealCallerToken() {
        customerServiceStub.stubFor(get(urlPathEqualTo("/customers/42"))
                .willReturn(aResponse().withStatus(200).withBody("{\"id\":42}")));

        ResponseEntity<String> response = restClient.get()
                .uri("http://localhost:" + gatewayPort + "/customers/42")
                .header(HttpHeaders.AUTHORIZATION, "Bearer customer-route-token-1")
                .retrieve()
                .toEntity(String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).contains("42");

        // Correct TARGET proven, not just "a" target: billing-service's
        // stub must never have seen this request.
        customerServiceStub.verify(1, getRequestedFor(urlPathEqualTo("/customers/42"))
                .withHeader("Authorization", equalTo("Bearer customer-route-token-1")));
        billingServiceStub.verify(0, getRequestedFor(urlPathEqualTo("/customers/42")));
    }

    @Test
    void planRoute_forwardsToBillingService_notTheBroaderCustomerCatchAll() {
        // Real regression target: GatewayRoutesConfig.java's own Javadoc
        // documents that billing/metering routes MUST be combined before
        // the broad customer-service "/customers/**" catch-all, or this
        // exact path would be wrongly claimed by customer-service instead.
        billingServiceStub.stubFor(get(urlPathEqualTo("/customers/42/plan"))
                .willReturn(aResponse().withStatus(200).withBody("{\"planName\":\"GOLD\"}")));

        ResponseEntity<String> response = restClient.get()
                .uri("http://localhost:" + gatewayPort + "/customers/42/plan")
                .header(HttpHeaders.AUTHORIZATION, "Bearer plan-route-token-2")
                .retrieve()
                .toEntity(String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).contains("GOLD");

        billingServiceStub.verify(1, getRequestedFor(urlPathEqualTo("/customers/42/plan"))
                .withHeader("Authorization", equalTo("Bearer plan-route-token-2")));
        // The real proof this test exists for: the broader customer-service
        // catch-all must NOT have also (or instead) received this request.
        customerServiceStub.verify(0, getRequestedFor(urlPathEqualTo("/customers/42/plan")));
    }
}
