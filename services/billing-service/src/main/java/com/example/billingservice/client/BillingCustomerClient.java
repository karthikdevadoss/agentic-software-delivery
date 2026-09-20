package com.example.billingservice.client;

import io.github.resilience4j.circuitbreaker.CallNotPermittedException;
import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.retry.Retry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;

import java.util.function.Supplier;

/**
 * THE REAL POINT OF THIS SERVICE: replaces the monolith's in-process
 * {@code customerService.getById(customerId)} call (see app/'s
 * ContractPlanService) with a genuine service-to-service HTTP call --
 * billing-service does not own Customer data, customer-service does (see
 * docs/MICROSERVICES_ARCHITECTURE.md's "Real inter-service communication"
 * section).
 *
 * DESIGN DECISION, mirroring the EXACT pattern already proven in app/'s
 * AppointmentAvailabilityClient + AppointmentAvailabilityConfig + service:
 * Spring's modern {@code RestClient}, composed with Resilience4j's core
 * circuitbreaker/retry modules programmatically (see
 * BillingCustomerClientConfig for why: same real Spring Boot 4 / core
 * modules vs. the resilience4j-spring-boot starter tradeoff already made
 * there). SERVICE_UNAVAILABLE is a distinct, never-fabricated outcome --
 * see CustomerLookupOutcome's Javadoc.
 *
 * ONE DELIBERATE STRUCTURAL DIFFERENCE from the Appointment pattern: app/
 * splits this into a raw HTTP client (AppointmentAvailabilityClient) and a
 * separate resilience-composing service (AppointmentAvailabilityService)
 * because that integration point has to compose multiple call shapes
 * across its callers. ContractPlanService needs exactly ONE decorated
 * operation here -- "does this customer exist" -- so the raw RestClient
 * call and its circuit-breaker/retry composition are combined into this
 * one class instead of splitting them for no real benefit. This is also
 * the class the real EXACT_PATTERN unit test in
 * ContractPlanServiceTest mocks directly (mirrors mocking a repository:
 * one clean seam, not two).
 *
 * By design this NEVER returns a Customer DTO -- only a bodiless existence
 * check (toBodilessEntity()) -- so billing-service stays loosely coupled
 * to customer-service's response shape; it does not need to know or trust
 * that shape to answer "does this id exist".
 */
public class BillingCustomerClient {

    private static final Logger log = LoggerFactory.getLogger(BillingCustomerClient.class);

    private final RestClient restClient;
    private final CircuitBreaker circuitBreaker;
    private final Retry retry;

    public BillingCustomerClient(RestClient.Builder builder, String baseUrl, CircuitBreaker circuitBreaker, Retry retry) {
        this.restClient = builder.baseUrl(baseUrl).build();
        this.circuitBreaker = circuitBreaker;
        this.retry = retry;
    }

    /**
     * Confirms customer {@code customerId} exists via a real GET
     * /customers/{id} call to customer-service, resolved through Eureka +
     * spring-cloud-starter-loadbalancer in production (see
     * BillingCustomerClientConfig's @LoadBalanced RestClient.Builder).
     * NEVER throws for a healthy "not found" or downstream-unavailable
     * outcome -- both are honestly represented in the return value; only
     * a genuinely unexpected programming error would propagate.
     */
    public CustomerLookupOutcome checkCustomerExists(Long customerId) {
        Supplier<Void> raw = () -> {
            restClient.get().uri("/customers/{id}", customerId).retrieve().toBodilessEntity();
            return null;
        };
        // Composition order matters: the circuit breaker wraps the retry
        // (not the other way around) so repeated retry attempts during an
        // open circuit's wait period never happen -- see app/'s
        // AppointmentAvailabilityService for the same reasoning.
        Supplier<Void> decorated = CircuitBreaker.decorateSupplier(circuitBreaker, Retry.decorateSupplier(retry, raw));

        try {
            decorated.get();
            return CustomerLookupOutcome.FOUND;
        } catch (CallNotPermittedException openCircuitException) {
            // Circuit is open -- fails fast, never even attempts the call.
            return CustomerLookupOutcome.SERVICE_UNAVAILABLE;
        } catch (HttpClientErrorException.NotFound notFound) {
            // A real, healthy answer from customer-service: this id does
            // not exist. Never retried (see BillingCustomerClientConfig's
            // retry predicate) and never counted as a circuit-breaker
            // failure (see its ignoreExceptions) -- a 404 says nothing
            // about customer-service's health.
            return CustomerLookupOutcome.NOT_FOUND;
        } catch (Exception downstreamFailure) {
            // Covers: connection refused/timeout (ResourceAccessException),
            // 5xx after retries exhausted, and any other unexpected
            // failure -- all are "we could not get a real answer", never
            // silently treated as FOUND (which would let billing-service
            // enroll a customer it never actually confirmed exists) or
            // NOT_FOUND (which would incorrectly 404 a real customer just
            // because customer-service happened to be down).
            log.warn("customer-service lookup for customer {} failed, reporting SERVICE_UNAVAILABLE: {}",
                    customerId, downstreamFailure.toString());
            return CustomerLookupOutcome.SERVICE_UNAVAILABLE;
        }
    }
}
