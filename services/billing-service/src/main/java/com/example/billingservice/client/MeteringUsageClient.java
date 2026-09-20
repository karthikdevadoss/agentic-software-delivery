package com.example.billingservice.client;

import io.github.resilience4j.circuitbreaker.CallNotPermittedException;
import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.retry.Retry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.client.RestClient;

import java.time.LocalDate;
import java.util.Optional;
import java.util.function.Supplier;

/**
 * BL-015: real service-to-service call from billing-service to
 * metering-service, wiring MeterReading usage data into billing
 * calculations -- see docs/MICROSERVICES_ARCHITECTURE.md's "What's
 * explicitly deferred" section, now closed. Mirrors BillingCustomerClient
 * exactly (same real RestClient + Resilience4j circuit-breaker/retry
 * pattern, resolved via Eureka + spring-cloud-starter-loadbalancer,
 * honest never-fabricated SERVICE_UNAVAILABLE) -- see that class's
 * Javadoc for the full design rationale, unchanged here.
 *
 * metering-service's own GET /customers/{id}/usage-summary always
 * returns 200 (readingCount=0 for a genuinely empty period, never a 404
 * -- see MeterReadingService.getUsageSummary), so this client has no
 * NOT_FOUND outcome to represent: Optional.empty() means only "we could
 * not get a real answer" (SERVICE_UNAVAILABLE), never a business-level
 * absence.
 */
public class MeteringUsageClient {

    private static final Logger log = LoggerFactory.getLogger(MeteringUsageClient.class);

    private final RestClient restClient;
    private final CircuitBreaker circuitBreaker;
    private final Retry retry;

    public MeteringUsageClient(RestClient.Builder builder, String baseUrl, CircuitBreaker circuitBreaker, Retry retry) {
        this.restClient = builder.baseUrl(baseUrl).build();
        this.circuitBreaker = circuitBreaker;
        this.retry = retry;
    }

    /**
     * Real GET /customers/{id}/usage-summary?from=&to= call to
     * metering-service, propagating the original caller's bearer token
     * (same identity-propagation pattern as BillingCustomerClient --
     * metering-service independently validates JWTs as its own OAuth2
     * resource server, per docs/MICROSERVICES_ARCHITECTURE.md's Auth
     * pattern). Returns Optional.empty() only when metering-service could
     * not be reached at all -- never a fabricated zero-usage answer.
     */
    public Optional<UsageSummaryResponse> getUsageSummary(Long customerId, LocalDate from, LocalDate to, String callerBearerToken) {
        Supplier<UsageSummaryResponse> raw = () -> restClient.get()
                .uri("/customers/{id}/usage-summary?from={from}&to={to}", customerId, from, to)
                .header("Authorization", callerBearerToken)
                .retrieve()
                .body(UsageSummaryResponse.class);
        // Same composition order as BillingCustomerClient: circuit breaker
        // wraps retry, never the reverse.
        Supplier<UsageSummaryResponse> decorated = CircuitBreaker.decorateSupplier(circuitBreaker, Retry.decorateSupplier(retry, raw));

        try {
            return Optional.of(decorated.get());
        } catch (CallNotPermittedException openCircuitException) {
            return Optional.empty();
        } catch (Exception downstreamFailure) {
            log.warn("metering-service usage-summary lookup for customer {} failed, reporting unavailable: {}",
                    customerId, downstreamFailure.toString());
            return Optional.empty();
        }
    }
}
