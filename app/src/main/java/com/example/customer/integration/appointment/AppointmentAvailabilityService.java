package com.example.customer.integration.appointment;

import io.github.resilience4j.circuitbreaker.CallNotPermittedException;
import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.retry.Retry;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.util.function.Supplier;

/**
 * Composes the raw HTTP client with a circuit breaker + retry — see
 * AppointmentAvailabilityConfig for why these are Resilience4j's core
 * modules wired programmatically rather than the annotation-based
 * Spring Boot starter.
 *
 * NEVER fabricates AVAILABLE or UNAVAILABLE when the real downstream
 * call did not succeed — SERVICE_UNAVAILABLE is the only honest answer
 * in that case (see AppointmentAvailabilityStatus's Javadoc).
 */
@Service
public class AppointmentAvailabilityService {

    private final AppointmentAvailabilityClient client;
    private final CircuitBreaker circuitBreaker;
    private final Retry retry;

    public AppointmentAvailabilityService(AppointmentAvailabilityClient client,
                                           CircuitBreaker appointmentCircuitBreaker,
                                           Retry appointmentRetry) {
        this.client = client;
        this.circuitBreaker = appointmentCircuitBreaker;
        this.retry = appointmentRetry;
    }

    public AppointmentAvailabilityStatus checkAvailability(LocalDate date) {
        Supplier<AppointmentAvailabilityClient.DownstreamAvailabilityResponse> raw =
                () -> client.checkAvailability(date);
        // Composition order matters: the circuit breaker wraps the retry
        // (not the other way around) so that repeated retry attempts
        // during an open circuit's wait period never happen -- the
        // breaker's own fast-fail (CallNotPermittedException) is checked
        // first, before any retry logic runs at all.
        Supplier<AppointmentAvailabilityClient.DownstreamAvailabilityResponse> decorated =
                CircuitBreaker.decorateSupplier(circuitBreaker, Retry.decorateSupplier(retry, raw));

        try {
            return decorated.get().available()
                    ? AppointmentAvailabilityStatus.AVAILABLE
                    : AppointmentAvailabilityStatus.UNAVAILABLE;
        } catch (CallNotPermittedException openCircuitException) {
            // Circuit is open -- fails fast, never even attempts the
            // downstream call. Same honest outcome as any other
            // downstream failure from the caller's point of view.
            return AppointmentAvailabilityStatus.SERVICE_UNAVAILABLE;
        } catch (Exception downstreamFailure) {
            // Covers: connection refused/timeout (ResourceAccessException),
            // 5xx after retries exhausted, 4xx (never retried, see
            // AppointmentAvailabilityConfig), and a malformed/undeserializable
            // response body -- all are "we could not get a real answer",
            // never silently treated as UNAVAILABLE (which would be a
            // fabricated, actively misleading business answer).
            return AppointmentAvailabilityStatus.SERVICE_UNAVAILABLE;
        }
    }
}
