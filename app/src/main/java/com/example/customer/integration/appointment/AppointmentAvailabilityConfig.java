package com.example.customer.integration.appointment;

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
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Lazy;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

import java.time.Duration;

/**
 * DESIGN DECISION: Resilience4j's CORE circuitbreaker/retry modules,
 * composed programmatically here, rather than the
 * resilience4j-spring-boot3/4 annotation starter (@CircuitBreaker/@Retry
 * + application.properties config) — see pom.xml's comment for why
 * (a real, documented Spring Boot 4 compatibility gap in that starter's
 * BOM as of this session). The resulting CircuitBreaker/Retry beans
 * behave identically either way; only the wiring style differs.
 */
@Configuration
public class AppointmentAvailabilityConfig {

    @Bean
    public RestClient.Builder appointmentRestClientBuilder() {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(1000);
        factory.setReadTimeout(1000);
        return RestClient.builder().requestFactory(factory);
    }

    /**
     * REAL BUG FOUND AND FIXED (2026-09-14): eagerly resolving
     * appointment.service.base-url here broke every
     * @SpringBootTest(webEnvironment=RANDOM_PORT) test that exercises the
     * real self-loopback default (http://localhost:${local.server.port}/...)
     * -- local.server.port is only published (by Spring Boot's
     * ServerPortInfoApplicationContextInitializer, reacting to
     * WebServerInitializedEvent) once the embedded server actually starts
     * listening, in ServletWebServerApplicationContext.finishRefresh() --
     * which runs AFTER finishBeanFactoryInitialization(), where a normal
     * eager singleton like this one would already have resolved its
     * @Value against the not-yet-updated (still "0" for random-port tests)
     * property. @Lazy here alone was NOT sufficient the first time this was
     * tried -- AppointmentAvailabilityService (an eager singleton) requires
     * this bean via constructor injection, which forces eager resolution of
     * the whole dependency graph regardless of this bean's own laziness
     * unless the INJECTION POINT is also marked @Lazy (see
     * AppointmentAvailabilityService's constructor) so Spring injects a
     * lazy-resolving proxy there instead. With both in place, construction
     * (and therefore @Value resolution) is deferred to first real use --
     * always well after startup has fully completed -- with no behavior
     * change in production, where server.port is a fixed real value from
     * the start.
     */
    @Bean
    @Lazy
    public AppointmentAvailabilityClient appointmentAvailabilityClient(
            RestClient.Builder appointmentRestClientBuilder,
            @Value("${appointment.service.base-url}") String baseUrl) {
        return new AppointmentAvailabilityClient(appointmentRestClientBuilder, baseUrl);
    }

    /**
     * A registry (not a bare CircuitBreaker.of(...)) specifically so
     * TaggedCircuitBreakerMetrics -- resilience4j-micrometer's only
     * binding entry point in this version -- can bind its real state
     * (calls/failure-rate/state-transitions) into /actuator/prometheus.
     * Also binds it here, at construction, rather than a separate bean,
     * so metrics exist from the very first call, not only after some
     * later initialization order.
     */
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
    public CircuitBreaker appointmentCircuitBreaker(CircuitBreakerRegistry circuitBreakerRegistry) {
        CircuitBreakerConfig config = CircuitBreakerConfig.custom()
                .slidingWindowSize(10)
                .failureRateThreshold(50.0f)
                .waitDurationInOpenState(Duration.ofSeconds(10))
                .permittedNumberOfCallsInHalfOpenState(3)
                // Only genuine "the downstream call did not succeed" cases
                // count toward opening the breaker -- a 4xx from
                // AppointmentAvailabilityClient's perspective still throws
                // (RestClient.retrieve() throws on any non-2xx), so this is
                // deliberately broad at the exception-type level; retry
                // policy (below) is what actually distinguishes retryable
                // (5xx/timeout) from non-retryable (4xx) cases.
                .recordExceptions(Exception.class)
                .build();
        return circuitBreakerRegistry.circuitBreaker("appointmentService", config);
    }

    @Bean
    public Retry appointmentRetry(RetryRegistry retryRegistry) {
        RetryConfig config = RetryConfig.custom()
                .maxAttempts(3)
                .waitDuration(Duration.ofMillis(50))
                // Deliberately narrow: only retry on connectivity/timeout
                // failures. A 4xx client error or a malformed response body
                // is not a transient condition retrying can fix, and
                // retrying a non-idempotent-unsafe scenario "just in case"
                // is exactly the anti-pattern the task's own instructions
                // warn against ("do not retry operations where retry could
                // create duplicate side effects") -- this endpoint is a
                // read (GET), so duplication is not the concern here, but
                // retrying a 4xx would still just waste calls and delay an
                // answer that will never change.
                .retryOnException(ex -> ex instanceof ResourceAccessException
                        || ex instanceof HttpServerErrorException)
                .build();
        return retryRegistry.retry("appointmentService", config);
    }
}
