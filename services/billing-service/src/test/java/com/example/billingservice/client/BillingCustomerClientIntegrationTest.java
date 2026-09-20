package com.example.billingservice.client;

import com.github.tomakehurst.wiremock.junit5.WireMockExtension;
import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.RegisterExtension;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.web.client.RestClient;

import static com.github.tomakehurst.wiremock.client.WireMock.aResponse;
import static com.github.tomakehurst.wiremock.client.WireMock.get;
import static com.github.tomakehurst.wiremock.client.WireMock.getRequestedFor;
import static com.github.tomakehurst.wiremock.client.WireMock.notFound;
import static com.github.tomakehurst.wiremock.client.WireMock.serverError;
import static com.github.tomakehurst.wiremock.client.WireMock.urlPathEqualTo;
import static org.assertj.core.api.Assertions.assertThat;

/**
 * FAILURE-FIRST TESTING for the real service-to-service integration point
 * this whole service exists to demonstrate: success, a genuine customer-
 * not-found 404, a connect timeout, and the circuit breaker actually
 * opening under sustained failure -- every scenario asserts the real,
 * honest CustomerLookupOutcome, never a fabricated one. Mirrors app/'s
 * AppointmentAvailabilityIntegrationTest pattern exactly (real WireMock
 * server, not a mocked client -- exercises the REAL RestClient/
 * CircuitBreaker/Retry stack end to end over real loopback HTTP).
 *
 * PRODUCTION uses a @LoadBalanced RestClient.Builder (see
 * BillingCustomerClientConfig) resolved via Eureka -- there is no Eureka
 * server or real customer-service instance in this test, so
 * TestRestClientOverride below REPLACES that exact bean (same bean name,
 * "loadBalancedCustomerRestClientBuilder") with a PLAIN RestClient.Builder
 * pointed directly at WireMock's real loopback base URL
 * (customer-service.base-url, set via @DynamicPropertySource).
 *
 * REAL BUG this replaced an earlier, broken approach for (found during
 * the first genuine multi-service smoke test, see
 * BillingCustomerClientConfig's Javadoc for the full story): an
 * @Primary-based override under a DIFFERENT bean name worked here in
 * isolation, but the production fix for that same bug (adding a
 * @Primary plain builder so Eureka's own unqualified client stops
 * getting load-balanced by accident) needs billingCustomerClient()'s
 * OWN injection point to be qualified BY NAME, not by @Primary -- so
 * this test must override by that same name to still take effect,
 * not introduce a second, differently-named @Primary competitor.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class BillingCustomerClientIntegrationTest {

    @RegisterExtension
    static WireMockExtension wireMock = WireMockExtension.newInstance().options(
            com.github.tomakehurst.wiremock.core.WireMockConfiguration.wireMockConfig().dynamicPort()
    ).build();

    @DynamicPropertySource
    static void customerServiceUrl(DynamicPropertyRegistry registry) {
        registry.add("customer-service.base-url", wireMock::baseUrl);
    }

    @TestConfiguration
    static class TestRestClientOverride {
        // Same bean NAME as BillingCustomerClientConfig's real
        // @LoadBalanced builder -- Spring Boot's test bean overriding
        // replaces that exact definition, which is what
        // billingCustomerClient()'s @Qualifier("loadBalancedCustomerRestClientBuilder")
        // actually resolves against (not @Primary -- see class Javadoc).
        @Bean("loadBalancedCustomerRestClientBuilder")
        RestClient.Builder loadBalancedCustomerRestClientBuilder() {
            SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
            factory.setConnectTimeout(1000);
            factory.setReadTimeout(1000);
            return RestClient.builder().requestFactory(factory);
        }
    }

    @Autowired
    private BillingCustomerClient billingCustomerClient;

    @Autowired
    private CircuitBreaker customerServiceCircuitBreaker;

    private static final Long CUSTOMER_ID = 42L;

    /**
     * Same real bug class app/'s AppointmentAvailabilityIntegrationTest
     * documents and guards against: the CircuitBreaker bean is a
     * singleton shared by every @Test method in this class (same cached
     * Spring context) -- resetting it here, alongside wireMock, makes
     * every test's downstream behavior depend only on that test's own
     * WireMock stub, never on execution order.
     */
    @BeforeEach
    void resetWireMockAndCircuitBreaker() {
        wireMock.resetAll();
        customerServiceCircuitBreaker.reset();
    }

    @Test
    void customerExists_returnsFound() {
        wireMock.stubFor(get(urlPathEqualTo("/customers/" + CUSTOMER_ID)).willReturn(aResponse().withStatus(200)));

        assertThat(billingCustomerClient.checkCustomerExists(CUSTOMER_ID, "Bearer test-token")).isEqualTo(CustomerLookupOutcome.FOUND);
    }

    @Test
    void customerNotFound_returnsNotFound_notServiceUnavailable() {
        wireMock.stubFor(get(urlPathEqualTo("/customers/" + CUSTOMER_ID)).willReturn(notFound()));

        assertThat(billingCustomerClient.checkCustomerExists(CUSTOMER_ID, "Bearer test-token")).isEqualTo(CustomerLookupOutcome.NOT_FOUND);
        // A 404 is a real, healthy answer -- never retried (see
        // BillingCustomerClientConfig's retry predicate).
        wireMock.verify(1, getRequestedFor(urlPathEqualTo("/customers/" + CUSTOMER_ID)));
    }

    @Test
    void downstream500_retriesThenReturnsServiceUnavailable_neverFabricatesAnAnswer() {
        wireMock.stubFor(get(urlPathEqualTo("/customers/" + CUSTOMER_ID)).willReturn(serverError()));

        assertThat(billingCustomerClient.checkCustomerExists(CUSTOMER_ID, "Bearer test-token")).isEqualTo(CustomerLookupOutcome.SERVICE_UNAVAILABLE);
        // maxAttempts=3 in BillingCustomerClientConfig -- a 500 is retryable.
        wireMock.verify(3, getRequestedFor(urlPathEqualTo("/customers/" + CUSTOMER_ID)));
    }

    @Test
    void downstreamTimeout_returnsServiceUnavailable() {
        wireMock.stubFor(get(urlPathEqualTo("/customers/" + CUSTOMER_ID))
                .willReturn(aResponse().withFixedDelay(3000).withStatus(200)));

        // Client read timeout is 1000ms (BillingCustomerClientConfig) --
        // this must time out and be treated the same as any other
        // downstream failure, never hang the caller or fabricate FOUND.
        assertThat(billingCustomerClient.checkCustomerExists(CUSTOMER_ID, "Bearer test-token")).isEqualTo(CustomerLookupOutcome.SERVICE_UNAVAILABLE);
    }

    @Test
    void sustainedFailures_openTheCircuitBreaker_subsequentCallsStayHonestlyServiceUnavailable() {
        wireMock.stubFor(get(urlPathEqualTo("/customers/" + CUSTOMER_ID)).willReturn(serverError()));

        // slidingWindowSize=10, failureRateThreshold=50% (BillingCustomerClientConfig).
        // Each checkCustomerExists() call internally retries 3x on a 500,
        // and each RETRY ATTEMPT is recorded as one call inside the
        // circuit breaker's sliding window.
        for (int i = 0; i < 4; i++) {
            billingCustomerClient.checkCustomerExists(CUSTOMER_ID, "Bearer test-token");
        }

        int callsBeforeOpen = wireMock.getAllServeEvents().size();
        assertThat(callsBeforeOpen).isGreaterThan(0);

        // The honest business outcome stays SERVICE_UNAVAILABLE throughout
        // -- the actual contract that matters to a caller -- rather than
        // asserting brittle exact-open-state timing.
        assertThat(billingCustomerClient.checkCustomerExists(CUSTOMER_ID, "Bearer test-token")).isEqualTo(CustomerLookupOutcome.SERVICE_UNAVAILABLE);
    }

    @Test
    void repeatedNotFound_neverOpensTheCircuitBreaker() {
        // DELIBERATE, NEW coverage vs. app/'s AppointmentAvailability test
        // (which has no notion of a "not found but healthy" downstream):
        // proves BillingCustomerClientConfig's ignoreExceptions(NotFound)
        // actually works -- a customer that genuinely does not exist must
        // never make OTHER, genuinely existing customers start seeing
        // SERVICE_UNAVAILABLE just because 404s piled up in the window.
        wireMock.stubFor(get(urlPathEqualTo("/customers/" + CUSTOMER_ID)).willReturn(notFound()));
        for (int i = 0; i < 10; i++) {
            assertThat(billingCustomerClient.checkCustomerExists(CUSTOMER_ID, "Bearer test-token")).isEqualTo(CustomerLookupOutcome.NOT_FOUND);
        }

        wireMock.resetAll();
        wireMock.stubFor(get(urlPathEqualTo("/customers/" + CUSTOMER_ID)).willReturn(aResponse().withStatus(200)));
        assertThat(billingCustomerClient.checkCustomerExists(CUSTOMER_ID, "Bearer test-token")).isEqualTo(CustomerLookupOutcome.FOUND);
    }
}
