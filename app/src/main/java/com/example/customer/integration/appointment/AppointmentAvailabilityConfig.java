package com.example.customer.integration.appointment;

import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerConfig;
import io.github.resilience4j.retry.Retry;
import io.github.resilience4j.retry.RetryConfig;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
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

    @Bean
    public AppointmentAvailabilityClient appointmentAvailabilityClient(
            RestClient.Builder appointmentRestClientBuilder,
            @Value("${appointment.service.base-url}") String baseUrl) {
        return new AppointmentAvailabilityClient(appointmentRestClientBuilder, baseUrl);
    }

    @Bean
    public CircuitBreaker appointmentCircuitBreaker() {
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
        return CircuitBreaker.of("appointmentService", config);
    }

    @Bean
    public Retry appointmentRetry() {
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
        return Retry.of("appointmentService", config);
    }
}
