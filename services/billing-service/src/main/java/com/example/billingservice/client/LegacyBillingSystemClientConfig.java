package com.example.billingservice.client;

import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerConfig;
import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import io.github.resilience4j.retry.Retry;
import io.github.resilience4j.retry.RetryConfig;
import io.github.resilience4j.retry.RetryRegistry;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.restclient.autoconfigure.RestClientBuilderConfigurer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Lazy;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

import java.time.Duration;

/**
 * ACT-013: mirrors BillingCustomerClientConfig/MeteringUsageClientConfig's
 * proven RestClient + Resilience4j composition (see either's Javadoc for
 * the full rationale, unchanged here), reusing the SAME
 * CircuitBreakerRegistry/RetryRegistry beans those classes already define
 * and already bind to Micrometer once for the whole registry (see
 * MeteringUsageClientConfig's Javadoc for why a second .bindTo() here
 * would be redundant) -- only registering a new, isolated
 * "legacyBillingSystem" entry in each, with its own failure budget so an
 * outage in the legacy system can never trip billing-service's circuit
 * breaker for customer-service or metering-service, or vice versa.
 *
 * DELIBERATELY NOT @LoadBalanced (unlike the other two client configs):
 * see LegacyBillingSystemClient's Javadoc for why a plain builder against
 * a fixed configured URL is the more realistic modeling choice for a
 * genuine legacy-system integration. This ALSO means, unlike
 * BillingCustomerClientIntegrationTest, no test-side RestClient.Builder
 * bean override is needed -- pointing legacy-billing-system.base-url at a
 * WireMock server via @DynamicPropertySource is enough, since this
 * builder never tries to resolve its base URL as an Eureka service-id.
 *
 * Still defines its OWN dedicated plain builder (not a reuse of
 * BillingCustomerClientConfig's shared @Primary one) for the same real
 * reason MeteringUsageClientConfig defines its own @LoadBalanced one
 * instead of reusing anything: this client needs its own
 * SimpleClientHttpRequestFactory connect/read timeouts (1s, matching the
 * other two clients) so a hung legacy-system call fails fast into the
 * circuit breaker/retry stack rather than hanging on the shared bean's
 * default (unbounded) timeout.
 */
@Configuration
public class LegacyBillingSystemClientConfig {

    @Bean
    public RestClient.Builder legacyBillingRestClientBuilder(RestClientBuilderConfigurer configurer) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(1000);
        factory.setReadTimeout(1000);
        return configurer.configure(RestClient.builder().requestFactory(factory));
    }

    /** @Lazy for the same real reason as BillingCustomerClientConfig documents:
     * defers construction (and the @Value baseUrl resolution) to first real
     * use, so a @DynamicPropertySource-driven test property is always in
     * place before this bean is actually built. */
    @Bean
    @Lazy
    public LegacyBillingSystemClient legacyBillingSystemClient(
            @Qualifier("legacyBillingRestClientBuilder") RestClient.Builder legacyBillingRestClientBuilder,
            @Value("${legacy-billing-system.base-url}") String baseUrl,
            CircuitBreaker legacyBillingSystemCircuitBreaker,
            Retry legacyBillingSystemRetry) {
        return new LegacyBillingSystemClient(legacyBillingRestClientBuilder, baseUrl, legacyBillingSystemCircuitBreaker, legacyBillingSystemRetry);
    }

    @Bean
    public CircuitBreaker legacyBillingSystemCircuitBreaker(CircuitBreakerRegistry circuitBreakerRegistry) {
        CircuitBreakerConfig config = CircuitBreakerConfig.custom()
                .slidingWindowSize(10)
                .failureRateThreshold(50.0f)
                .waitDurationInOpenState(Duration.ofSeconds(10))
                .permittedNumberOfCallsInHalfOpenState(3)
                .recordExceptions(Exception.class)
                // A "plan not recognized" 404 is a real, healthy answer
                // from the legacy system, not evidence it is failing --
                // same reasoning as BillingCustomerClientConfig's
                // customer-not-found exclusion.
                .ignoreExceptions(HttpClientErrorException.NotFound.class)
                .build();
        return circuitBreakerRegistry.circuitBreaker("legacyBillingSystem", config);
    }

    @Bean
    public Retry legacyBillingSystemRetry(RetryRegistry retryRegistry) {
        RetryConfig config = RetryConfig.custom()
                .maxAttempts(3)
                .waitDuration(Duration.ofMillis(50))
                .retryOnException(ex -> ex instanceof ResourceAccessException
                        || ex instanceof HttpServerErrorException)
                .build();
        return retryRegistry.retry("legacyBillingSystem", config);
    }
}
