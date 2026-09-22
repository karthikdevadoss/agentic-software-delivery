package com.example.gateway.bff;

import com.github.tomakehurst.wiremock.junit5.WireMockExtension;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.RegisterExtension;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.web.client.RestClient;

import java.util.Map;

import static com.github.tomakehurst.wiremock.client.WireMock.aResponse;
import static com.github.tomakehurst.wiremock.client.WireMock.equalTo;
import static com.github.tomakehurst.wiremock.client.WireMock.get;
import static com.github.tomakehurst.wiremock.client.WireMock.getRequestedFor;
import static com.github.tomakehurst.wiremock.client.WireMock.urlPathEqualTo;
import static com.github.tomakehurst.wiremock.core.WireMockConfiguration.wireMockConfig;
import static org.assertj.core.api.Assertions.assertThat;

/**
 * BL-039: three REAL WireMock downstreams behind the gateway's real
 * DiscoveryClient (same simple-discovery wiring as
 * GatewayRoutingIntegrationTest). The decisive test is the slow one: a
 * dependency answering slower than the per-call timeout must degrade its
 * own section only, while the other two sections carry real data and the
 * whole call returns well before the slow stub would have.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = "bff.per-call-timeout-ms=800")
@ActiveProfiles("test")
class DashboardBffIntegrationTest {

    @RegisterExtension
    static WireMockExtension customerStub = WireMockExtension.newInstance().options(wireMockConfig().dynamicPort()).build();
    @RegisterExtension
    static WireMockExtension billingStub = WireMockExtension.newInstance().options(wireMockConfig().dynamicPort()).build();
    @RegisterExtension
    static WireMockExtension meteringStub = WireMockExtension.newInstance().options(wireMockConfig().dynamicPort()).build();

    @DynamicPropertySource
    static void discoveryStubs(DynamicPropertyRegistry registry) {
        registry.add("spring.cloud.discovery.client.simple.instances.customer-service[0].uri", customerStub::baseUrl);
        registry.add("spring.cloud.discovery.client.simple.instances.billing-service[0].uri", billingStub::baseUrl);
        registry.add("spring.cloud.discovery.client.simple.instances.metering-service[0].uri", meteringStub::baseUrl);
    }

    @LocalServerPort
    private int gatewayPort;

    private final RestClient restClient = RestClient.create();

    @BeforeEach
    void resetStubs() {
        customerStub.resetAll();
        billingStub.resetAll();
        meteringStub.resetAll();
    }

    private ResponseEntity<Map<String, Object>> callDashboard() {
        return restClient.get()
                .uri("http://localhost:" + gatewayPort + "/bff/customers/42/dashboard")
                .header(HttpHeaders.AUTHORIZATION, "Bearer bff-test-token")
                .retrieve()
                .toEntity(new ParameterizedTypeReference<>() { });
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> section(Map<String, Object> body, String name) {
        return (Map<String, Object>) ((Map<String, Object>) body.get("sections")).get(name);
    }

    @Test
    void allDownstreamsHealthy_returnsCompleteDashboard_andPropagatesTheCallerTokenToEachOne() {
        customerStub.stubFor(get(urlPathEqualTo("/customers/42")).willReturn(aResponse().withStatus(200)
                .withHeader("Content-Type", "application/json").withBody("{\"id\":42,\"name\":\"Dash Board\"}")));
        billingStub.stubFor(get(urlPathEqualTo("/customers/42/plan")).willReturn(aResponse().withStatus(200)
                .withHeader("Content-Type", "application/json").withBody("{\"planName\":\"Residential-12\",\"ratePerKwh\":0.1825}")));
        meteringStub.stubFor(get(urlPathEqualTo("/customers/42/usage-summary")).willReturn(aResponse().withStatus(200)
                .withHeader("Content-Type", "application/json").withBody("{\"totalKwh\":312.5}")));

        ResponseEntity<Map<String, Object>> response = callDashboard();

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        Map<String, Object> body = response.getBody();
        assertThat(body.get("partial")).isEqualTo(false);
        assertThat(section(body, "customer").get("status")).isEqualTo("OK");
        assertThat(section(body, "plan").get("status")).isEqualTo("OK");
        assertThat(section(body, "usage").get("status")).isEqualTo("OK");
        assertThat(((Map<?, ?>) section(body, "plan").get("data")).get("planName")).isEqualTo("Residential-12");
        for (WireMockExtension stub : new WireMockExtension[]{customerStub, billingStub, meteringStub}) {
            stub.verify(1, getRequestedFor(urlPathEqualTo(stub == customerStub ? "/customers/42"
                            : stub == billingStub ? "/customers/42/plan" : "/customers/42/usage-summary"))
                    .withHeader("Authorization", equalTo("Bearer bff-test-token")));
        }
    }

    @Test
    void oneSlowDownstream_degradesOnlyItsSection_andDoesNotBlockTheScreen() {
        customerStub.stubFor(get(urlPathEqualTo("/customers/42")).willReturn(aResponse().withStatus(200)
                .withHeader("Content-Type", "application/json").withBody("{\"id\":42}")));
        // billing answers, but only after 4 s -- far beyond the 800 ms per-call timeout
        billingStub.stubFor(get(urlPathEqualTo("/customers/42/plan")).willReturn(aResponse().withStatus(200)
                .withFixedDelay(4000).withHeader("Content-Type", "application/json").withBody("{\"planName\":\"late\"}")));
        meteringStub.stubFor(get(urlPathEqualTo("/customers/42/usage-summary")).willReturn(aResponse().withStatus(200)
                .withHeader("Content-Type", "application/json").withBody("{\"totalKwh\":1}")));

        long started = System.currentTimeMillis();
        ResponseEntity<Map<String, Object>> response = callDashboard();
        long elapsed = System.currentTimeMillis() - started;

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        Map<String, Object> body = response.getBody();
        assertThat(body.get("partial")).isEqualTo(true);
        assertThat(section(body, "plan").get("status")).isEqualTo("UNAVAILABLE");
        assertThat((String) section(body, "plan").get("reason")).contains("timed out");
        assertThat(section(body, "customer").get("status")).isEqualTo("OK");
        assertThat(section(body, "usage").get("status")).isEqualTo("OK");
        assertThat(elapsed).isLessThan(3000L);
    }

    @Test
    void unknownCustomerDownstream404_isReportedAsUnavailableNotFabricated() {
        customerStub.stubFor(get(urlPathEqualTo("/customers/42")).willReturn(aResponse().withStatus(404)));
        billingStub.stubFor(get(urlPathEqualTo("/customers/42/plan")).willReturn(aResponse().withStatus(404)));
        meteringStub.stubFor(get(urlPathEqualTo("/customers/42/usage-summary")).willReturn(aResponse().withStatus(200)
                .withHeader("Content-Type", "application/json").withBody("{\"totalKwh\":0}")));

        Map<String, Object> body = callDashboard().getBody();

        assertThat(section(body, "customer").get("status")).isEqualTo("UNAVAILABLE");
        assertThat(section(body, "customer").get("reason")).isEqualTo("not found");
        assertThat(section(body, "customer").get("data")).isNull();
        assertThat(section(body, "usage").get("status")).isEqualTo("OK");
    }
}
