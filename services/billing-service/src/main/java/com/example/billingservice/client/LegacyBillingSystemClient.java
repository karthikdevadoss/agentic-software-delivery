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
 * ACT-013, THE REAL POINT OF THIS REWORK (see docs/ACTION_QUEUE.json /
 * docs/BACKLOG.json): billing-service does not calculate or own the
 * authoritative billing rate for a plan -- it is a FACADE that confirms it
 * with the legacy billing system of record, exactly matching what the
 * Owner's own real NRG billing-service does (his own confirmed words: a
 * bridge/facade to an older, separate billing system that does NOT
 * calculate bills itself -- see ContractPlanService's Javadoc for the full
 * story of what changed here and why). ContractPlanEnrollRequest.ratePerKwh
 * is only ever a REQUESTED rate now -- this call is what actually decides
 * the rate that gets persisted.
 *
 * Mirrors BillingCustomerClient's exact RestClient + Resilience4j
 * circuit-breaker/retry shape and its honest, never-fabricated outcome
 * discipline (see LegacyPlanPricingOutcome's Javadoc) -- the SAME proven
 * pattern already used tonight for the customer-service and
 * metering-service calls, reused here rather than inventing a new
 * integration style for a third real dependency.
 *
 * Since there is no actual external legacy billing mainframe to call in
 * this exercise, the far side of this call is a REALISTIC SIMULATION
 * (WireMock in every test -- see LegacyBillingSystemClientIntegrationTest
 * -- exactly the same stand-in role WireMock already plays for
 * customer-service and metering-service in this codebase's own tests).
 * That simulation is honest about what it is: it is never claimed to be a
 * real NRG system, only a realistic stand-in for the pattern the Owner
 * confirmed is real.
 *
 * ONE DELIBERATE DIFFERENCE from BillingCustomerClient/MeteringUsageClient:
 * this RestClient is built from a PLAIN (non-@LoadBalanced) builder against
 * a fixed configured URL, not resolved through Eureka -- see
 * LegacyBillingSystemClientConfig's Javadoc for why: a real legacy billing
 * system like the one being modeled here is essentially never a modern,
 * Eureka-registered peer microservice; it is reached through a fixed
 * integration endpoint (its own gateway, or an internal ESB/integration
 * layer) that nobody has modernized -- itself part of the real interview
 * story this facade exists to tell (why these legacy bridges are
 * expensive and slow to ever migrate away from).
 */
public class LegacyBillingSystemClient {

    private static final Logger log = LoggerFactory.getLogger(LegacyBillingSystemClient.class);

    private final RestClient restClient;
    private final CircuitBreaker circuitBreaker;
    private final Retry retry;

    public LegacyBillingSystemClient(RestClient.Builder builder, String baseUrl, CircuitBreaker circuitBreaker, Retry retry) {
        this.restClient = builder.baseUrl(baseUrl).build();
        this.circuitBreaker = circuitBreaker;
        this.retry = retry;
    }

    /**
     * Real GET /legacy-billing/plans/{planName}/pricing?customerId={id}
     * call to the legacy billing system, propagating the original caller's
     * bearer token (same identity-propagation pattern as
     * BillingCustomerClient -- the legacy system's own integration gateway
     * validates it independently, same reasoning). {@code customerId} is
     * sent because a real legacy rate engine can apply customer-specific
     * eligibility/tier pricing, not just a flat per-plan rate -- never
     * assumed to be irrelevant just because this simulation ignores it.
     * NEVER throws for a healthy "plan not recognized" or
     * downstream-unavailable outcome -- both are honestly represented in
     * the return value; only a genuinely unexpected programming error
     * would propagate.
     */
    public LegacyPlanPricingOutcome confirmPlanPricing(String planName, Long customerId, String callerBearerToken) {
        Supplier<LegacyPlanRateResponse> raw = () -> restClient.get()
                .uri("/legacy-billing/plans/{planName}/pricing?customerId={customerId}", planName, customerId)
                .header("Authorization", callerBearerToken)
                .retrieve()
                .body(LegacyPlanRateResponse.class);
        // Same composition order as BillingCustomerClient/MeteringUsageClient:
        // circuit breaker wraps retry, never the reverse.
        Supplier<LegacyPlanRateResponse> decorated =
                CircuitBreaker.decorateSupplier(circuitBreaker, Retry.decorateSupplier(retry, raw));

        try {
            LegacyPlanRateResponse response = decorated.get();
            return new LegacyPlanPricingOutcome.Confirmed(response.ratePerKwh());
        } catch (CallNotPermittedException openCircuitException) {
            // Circuit is open -- fails fast, never even attempts the call.
            return new LegacyPlanPricingOutcome.Unavailable();
        } catch (HttpClientErrorException.NotFound notFound) {
            // A real, healthy answer from the legacy system: this plan
            // code does not exist in its catalog.
            return new LegacyPlanPricingOutcome.PlanNotRecognized();
        } catch (Exception downstreamFailure) {
            // Covers: connection refused/timeout (ResourceAccessException),
            // 5xx after retries exhausted, and any other unexpected
            // failure -- all are "we could not get a real answer," never
            // silently fabricated as a confirmed rate (which would let
            // billing-service enroll a customer at a rate it never
            // actually confirmed) or as PlanNotRecognized (which would
            // incorrectly reject a real plan just because the legacy
            // system happened to be down).
            log.warn("legacy billing system pricing lookup for plan '{}' (customer {}) failed, reporting unavailable: {}",
                    planName, customerId, downstreamFailure.toString());
            return new LegacyPlanPricingOutcome.Unavailable();
        }
    }
}
