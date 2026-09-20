package com.example.billingservice.client;

import com.github.tomakehurst.wiremock.junit5.WireMockExtension;
import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.RegisterExtension;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.web.client.RestClient;

import java.time.LocalDate;
import java.util.Optional;

import static com.github.tomakehurst.wiremock.client.WireMock.aResponse;
import static com.github.tomakehurst.wiremock.client.WireMock.get;
import static com.github.tomakehurst.wiremock.client.WireMock.getRequestedFor;
import static com.github.tomakehurst.wiremock.client.WireMock.serverError;
import static com.github.tomakehurst.wiremock.client.WireMock.urlPathEqualTo;
import static org.assertj.core.api.Assertions.assertThat;

/**
 * BL-015: mirrors BillingCustomerClientIntegrationTest exactly (same real
 * WireMock server, not a mocked client) -- see that class's Javadoc for
 * the full reasoning behind this pattern, unchanged here.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class MeteringUsageClientIntegrationTest {

    @RegisterExtension
    static WireMockExtension wireMock = WireMockExtension.newInstance().options(
            com.github.tomakehurst.wiremock.core.WireMockConfiguration.wireMockConfig().dynamicPort()
    ).build();

    @DynamicPropertySource
    static void meteringServiceUrl(DynamicPropertyRegistry registry) {
        registry.add("metering-service.base-url", wireMock::baseUrl);
    }

    @TestConfiguration
    static class TestRestClientOverride {
        @Bean("loadBalancedMeteringRestClientBuilder")
        RestClient.Builder loadBalancedMeteringRestClientBuilder() {
            SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
            factory.setConnectTimeout(1000);
            factory.setReadTimeout(1000);
            return RestClient.builder().requestFactory(factory);
        }
    }

    @Autowired
    private MeteringUsageClient meteringUsageClient;

    @Autowired
    @Qualifier("meteringServiceCircuitBreaker")
    private CircuitBreaker meteringServiceCircuitBreaker;

    private static final Long CUSTOMER_ID = 42L;
    private static final LocalDate FROM = LocalDate.of(2026, 9, 1);
    private static final LocalDate TO = LocalDate.of(2026, 9, 30);

    @BeforeEach
    void resetWireMockAndCircuitBreaker() {
        wireMock.resetAll();
        meteringServiceCircuitBreaker.reset();
    }

    @Test
    void realUsageSummary_returnsRealParsedData() {
        wireMock.stubFor(get(urlPathEqualTo("/customers/" + CUSTOMER_ID + "/usage-summary"))
                .willReturn(aResponse().withStatus(200).withHeader("Content-Type", "application/json")
                        .withBody("{\"customerId\":42,\"periodStart\":\"2026-09-01\",\"periodEnd\":\"2026-09-30\",\"totalKwhConsumed\":150.5,\"readingCount\":3}")));

        Optional<UsageSummaryResponse> result = meteringUsageClient.getUsageSummary(CUSTOMER_ID, FROM, TO, "Bearer test-token");

        assertThat(result).isPresent();
        assertThat(result.get().totalKwhConsumed()).isEqualByComparingTo("150.5");
        assertThat(result.get().readingCount()).isEqualTo(3);
    }

    @Test
    void zeroReadings_isARealAnswer_notUnavailable() {
        // metering-service's own MeterReadingService.getUsageSummary always
        // returns 200 with readingCount=0 for a genuinely empty period,
        // never a 404 -- this must be honestly distinguished from
        // SERVICE_UNAVAILABLE (an Optional.empty() here would be a lie:
        // we DID get a real answer, it was just zero).
        wireMock.stubFor(get(urlPathEqualTo("/customers/" + CUSTOMER_ID + "/usage-summary"))
                .willReturn(aResponse().withStatus(200).withHeader("Content-Type", "application/json")
                        .withBody("{\"customerId\":42,\"periodStart\":\"2026-09-01\",\"periodEnd\":\"2026-09-30\",\"totalKwhConsumed\":0,\"readingCount\":0}")));

        Optional<UsageSummaryResponse> result = meteringUsageClient.getUsageSummary(CUSTOMER_ID, FROM, TO, "Bearer test-token");

        assertThat(result).isPresent();
        assertThat(result.get().readingCount()).isZero();
    }

    @Test
    void downstream500_retriesThenReturnsEmpty_neverFabricatesAnAnswer() {
        wireMock.stubFor(get(urlPathEqualTo("/customers/" + CUSTOMER_ID + "/usage-summary")).willReturn(serverError()));

        assertThat(meteringUsageClient.getUsageSummary(CUSTOMER_ID, FROM, TO, "Bearer test-token")).isEmpty();
        wireMock.verify(3, getRequestedFor(urlPathEqualTo("/customers/" + CUSTOMER_ID + "/usage-summary")));
    }

    @Test
    void downstreamTimeout_returnsEmpty() {
        wireMock.stubFor(get(urlPathEqualTo("/customers/" + CUSTOMER_ID + "/usage-summary"))
                .willReturn(aResponse().withFixedDelay(3000).withStatus(200)));

        assertThat(meteringUsageClient.getUsageSummary(CUSTOMER_ID, FROM, TO, "Bearer test-token")).isEmpty();
    }
}
