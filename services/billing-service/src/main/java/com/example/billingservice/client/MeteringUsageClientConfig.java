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
import org.springframework.cloud.client.loadbalancer.LoadBalanced;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Lazy;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.RestClient;

import java.time.Duration;

/**
 * BL-015: mirrors BillingCustomerClientConfig exactly, including its
 * RestClientBuilderConfigurer usage (BL-014 finding -- the bare
 * RestClient.builder() static factory bypasses Spring Boot's own
 * RestClientAutoConfiguration customizer pipeline entirely, including
 * tracing propagation; going through the configurer here from the start
 * rather than repeating that same gap in a second client).
 *
 * Deliberately NOT reusing BillingCustomerClientConfig's own
 * @Primary plain restClientBuilder() bean here -- that bean already
 * exists once in this application context (Spring beans are
 * application-scoped, not per-client-class), this class only adds the
 * SECOND @LoadBalanced builder metering-service's client needs, plus its
 * own dedicated circuit breaker/retry (a metering-service outage must
 * never trip billing-service's circuit breaker for customer-service, and
 * vice versa -- each real dependency gets its own isolated failure
 * budget).
 */
@Configuration
public class MeteringUsageClientConfig {

    @Bean
    @LoadBalanced
    public RestClient.Builder loadBalancedMeteringRestClientBuilder(RestClientBuilderConfigurer configurer) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(1000);
        factory.setReadTimeout(1000);
        return configurer.configure(RestClient.builder().requestFactory(factory));
    }

    /** @Lazy for the same real reason as BillingCustomerClientConfig documents. */
    @Bean
    @Lazy
    public MeteringUsageClient meteringUsageClient(
            @Qualifier("loadBalancedMeteringRestClientBuilder") RestClient.Builder loadBalancedMeteringRestClientBuilder,
            @Value("${metering-service.base-url}") String baseUrl,
            CircuitBreaker meteringServiceCircuitBreaker,
            Retry meteringServiceRetry) {
        return new MeteringUsageClient(loadBalancedMeteringRestClientBuilder, baseUrl, meteringServiceCircuitBreaker, meteringServiceRetry);
    }

    /**
     * Reuses the SAME CircuitBreakerRegistry/RetryRegistry beans
     * BillingCustomerClientConfig already defines and already binds to
     * Micrometer once for the whole registry (Resilience4j's tagged-
     * metrics binder listens for entries added to a registry AFTER
     * binding, so a second .bindTo() call here would just duplicate that
     * binding, not add anything real) -- only registering a new, isolated
     * "meteringService" entry in each, with its own failure budget so a
     * metering-service outage can never trip the customer-service circuit
     * breaker, or vice versa.
     */
    @Bean
    public CircuitBreaker meteringServiceCircuitBreaker(CircuitBreakerRegistry circuitBreakerRegistry) {
        CircuitBreakerConfig config = CircuitBreakerConfig.custom()
                .slidingWindowSize(10)
                .failureRateThreshold(50.0f)
                .waitDurationInOpenState(Duration.ofSeconds(10))
                .permittedNumberOfCallsInHalfOpenState(3)
                .recordExceptions(Exception.class)
                .build();
        return circuitBreakerRegistry.circuitBreaker("meteringService", config);
    }

    @Bean
    public Retry meteringServiceRetry(RetryRegistry retryRegistry) {
        RetryConfig config = RetryConfig.custom()
                .maxAttempts(3)
                .waitDuration(Duration.ofMillis(50))
                .retryOnException(ex -> ex instanceof ResourceAccessException
                        || ex instanceof HttpServerErrorException)
                .build();
        return retryRegistry.retry("meteringService", config);
    }
}
