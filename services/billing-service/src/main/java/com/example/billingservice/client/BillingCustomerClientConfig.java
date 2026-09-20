package com.example.billingservice.client;

import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerConfig;
import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import io.github.resilience4j.micrometer.tagged.TaggedCircuitBreakerMetrics;
import io.github.resilience4j.micrometer.tagged.TaggedRetryMetrics;
import io.github.resilience4j.retry.Retry;
import io.github.resilience4j.retry.RetryConfig;
import io.github.resilience4j.retry.RetryRegistry;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.client.loadbalancer.LoadBalanced;
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
 * DESIGN DECISION: Resilience4j's CORE circuitbreaker/retry modules,
 * composed programmatically here, rather than the
 * resilience4j-spring-boot3/4 annotation starter -- same real, documented
 * Spring Boot 4 BOM compatibility gap app/'s AppointmentAvailabilityConfig
 * already found and documented; unchanged by moving to a separate service.
 *
 * THE REAL, NEW PIECE vs. the monolith's AppointmentAvailabilityConfig:
 * the RestClient.Builder here is @LoadBalanced. billing-service does not
 * know or care which concrete host:port customer-service is actually
 * running on -- "http://customer-service" is a logical Eureka service-id,
 * and spring-cloud-starter-loadbalancer's interceptor resolves it to a
 * real registered instance on every call. This is genuine service
 * independence: no hardcoded downstream URL anywhere in this service.
 */
@Configuration
public class BillingCustomerClientConfig {

    @Bean
    @LoadBalanced
    public RestClient.Builder loadBalancedCustomerRestClientBuilder() {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(1000);
        factory.setReadTimeout(1000);
        return RestClient.builder().requestFactory(factory);
    }

    /**
     * @Lazy for the same real reason as app/'s AppointmentAvailabilityConfig
     * documents in detail: eagerly resolving customer-service.base-url (or
     * eagerly constructing the RestClient against it) during singleton
     * pre-instantiation can run before a @DynamicPropertySource-driven test
     * property (e.g. a WireMock base URL) is actually in place, and/or
     * before this service's own embedded server/discovery client has
     * finished initializing. @Lazy here, plus @Lazy at the one place this
     * bean is actually injected (ContractPlanService's constructor param),
     * defers construction to first real use with no behavior change in
     * production.
     */
    @Bean
    @Lazy
    public BillingCustomerClient billingCustomerClient(
            RestClient.Builder loadBalancedCustomerRestClientBuilder,
            @Value("${customer-service.base-url}") String baseUrl,
            CircuitBreaker customerServiceCircuitBreaker,
            Retry customerServiceRetry) {
        return new BillingCustomerClient(loadBalancedCustomerRestClientBuilder, baseUrl, customerServiceCircuitBreaker, customerServiceRetry);
    }

    /** A registry (not a bare CircuitBreaker.of(...)) so TaggedCircuitBreakerMetrics
     * can bind its real state into /actuator/prometheus -- same reasoning as
     * app/'s AppointmentAvailabilityConfig. */
    @Bean
    public CircuitBreakerRegistry circuitBreakerRegistry(MeterRegistry meterRegistry) {
        CircuitBreakerRegistry registry = CircuitBreakerRegistry.ofDefaults();
        TaggedCircuitBreakerMetrics.ofCircuitBreakerRegistry(registry).bindTo(meterRegistry);
        return registry;
    }

    @Bean
    public RetryRegistry retryRegistry(MeterRegistry meterRegistry) {
        RetryRegistry registry = RetryRegistry.ofDefaults();
        TaggedRetryMetrics.ofRetryRegistry(registry).bindTo(meterRegistry);
        return registry;
    }

    @Bean
    public CircuitBreaker customerServiceCircuitBreaker(CircuitBreakerRegistry circuitBreakerRegistry) {
        CircuitBreakerConfig config = CircuitBreakerConfig.custom()
                .slidingWindowSize(10)
                .failureRateThreshold(50.0f)
                .waitDurationInOpenState(Duration.ofSeconds(10))
                .permittedNumberOfCallsInHalfOpenState(3)
                .recordExceptions(Exception.class)
                // DELIBERATE DIFFERENCE from app/'s AppointmentAvailabilityConfig
                // (which records every exception, 404s included): a
                // customer-not-found 404 is a real, healthy answer from
                // customer-service, not evidence customer-service itself is
                // failing. Counting it toward the failure rate would let a
                // caller hammering nonexistent customer ids trip the
                // breaker and start returning SERVICE_UNAVAILABLE for
                // OTHER, genuinely existing customers -- a real availability
                // bug this ignoreExceptions call exists to prevent.
                .ignoreExceptions(HttpClientErrorException.NotFound.class)
                .build();
        return circuitBreakerRegistry.circuitBreaker("customerService", config);
    }

    @Bean
    public Retry customerServiceRetry(RetryRegistry retryRegistry) {
        RetryConfig config = RetryConfig.custom()
                .maxAttempts(3)
                .waitDuration(Duration.ofMillis(50))
                // Deliberately narrow, same as app/'s AppointmentAvailabilityConfig:
                // only retry genuine connectivity/timeout/5xx failures. A 404
                // (HttpClientErrorException.NotFound) is not retried here
                // either -- it already falls outside this predicate since it
                // is neither a ResourceAccessException nor an
                // HttpServerErrorException, so no special-case is needed; it
                // is also this endpoint's one and only GET, so retrying is
                // never a duplicate-side-effect risk in the first place.
                .retryOnException(ex -> ex instanceof ResourceAccessException
                        || ex instanceof HttpServerErrorException)
                .build();
        return retryRegistry.retry("customerService", config);
    }
}
