package com.example.customer.triage;

import com.example.customer.integration.appointment.AppointmentAvailabilityClient;
import io.github.resilience4j.retry.Retry;
import io.github.resilience4j.retry.RetryConfig;
import org.springframework.context.annotation.Lazy;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.LocalDate;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Supplier;

/**
 * Incident Triage Lab -- Scenario B (appointment downstream resilience:
 * wrong retry predicate).
 *
 * REUSES THE SAME ENGINE AS SCENARIO A, not a parallel implementation:
 * reset -> reproduce -> (diagnose/candidate-patch/verify in
 * agent/triage_execution.py, calling the real Anthropic API and real
 * mvnw compile/test exactly like Scenario A) -> ADMIN-gated approve ->
 * rerun. The only thing that differs per scenario is WHAT is being
 * reproduced/fixed.
 *
 * ISOLATION CONTRACT, mirroring TriageScenarioAService exactly: the
 * "buggy" behavior below is a deliberately-seeded, clearly-labeled
 * defect that exists ONLY inside this isolated scenario service --
 * never wired into AppointmentAvailabilityService (the real, correct,
 * already-tested production path real customers' appointment checks
 * actually use). buggyRetry is a private, unregistered Retry instance,
 * never added to the shared RetryRegistry -- structurally unreachable
 * from real business logic. The "fixed" path here delegates to the REAL
 * production `appointmentRetry` bean (constructor-injected, same bean
 * AppointmentAvailabilityService itself uses), exactly like Scenario A's
 * enrollFixed() delegates to the real ContractPlanService rather than a
 * second copy of the fix.
 *
 * Reaches the downstream over a genuine HTTP loopback call (via
 * AppointmentAvailabilityClient -> DemoAppointmentProviderController's
 * scenario=client_error, a real HTTP 400) -- never a direct method call
 * or a hardcoded exception -- so the real retry/backoff/exception-type
 * mechanics are genuinely exercised, not simulated.
 */
@Service
public class TriageScenarioBService {

    private final AppointmentAvailabilityClient client;
    private final Retry productionRetry;

    /**
     * REAL, DELIBERATELY-SEEDED DEFECT (isolated pedagogical replay, never
     * reachable by real customer traffic): retries on ANY exception,
     * including a genuine downstream 4xx client error. A 4xx is not a
     * transient condition -- retrying it can never succeed, so this
     * wastes real HTTP round-trips and delays an answer that will never
     * change, exactly the anti-pattern AppointmentAvailabilityConfig's own
     * Javadoc explains the REAL predicate is narrow to avoid.
     */
    private final Retry buggyRetry = Retry.of("triageScenarioBBuggyRetry",
            RetryConfig.custom()
                    .maxAttempts(3)
                    .waitDuration(Duration.ofMillis(50))
                    .retryOnException(ex -> true)
                    .build());

    private volatile boolean fixApplied = false;

    public TriageScenarioBService(@Lazy AppointmentAvailabilityClient appointmentAvailabilityClient,
                                   Retry appointmentRetry) {
        this.client = appointmentAvailabilityClient;
        this.productionRetry = appointmentRetry;
    }

    public synchronized TriageBState reset() {
        this.fixApplied = false;
        return state();
    }

    /** Calls the real synthetic downstream (a genuine HTTP round-trip per
     * attempt) with scenario=client_error (a real HTTP 400), wrapped in
     * either the buggy or the real production retry policy depending on
     * fixApplied, counting real attempts as they happen -- never
     * estimated or asserted from the outside. */
    public TriageBReproductionResult reproduce() {
        AtomicInteger attempts = new AtomicInteger(0);
        Retry retryToUse = fixApplied ? productionRetry : buggyRetry;
        Supplier<AppointmentAvailabilityClient.DownstreamAvailabilityResponse> instrumented = () -> {
            attempts.incrementAndGet();
            return client.checkAvailability(LocalDate.now(), "client_error");
        };

        String exceptionType = null;
        String exceptionMessage = null;
        try {
            Retry.decorateSupplier(retryToUse, instrumented).get();
        } catch (Exception e) {
            exceptionType = e.getClass().getSimpleName();
            exceptionMessage = e.getMessage();
        }

        int attemptCount = attempts.get();
        boolean defectReproduced = !fixApplied && attemptCount > 1;
        return new TriageBReproductionResult(fixApplied, attemptCount, 1, exceptionType, exceptionMessage, defectReproduced);
    }

    /** Requires ADMIN authorization at the controller layer (see
     * TriageScenarioBController) -- flips only this isolated scenario's
     * own state, never touches real production config or any real
     * downstream call. */
    public synchronized TriageBState approveFix() {
        this.fixApplied = true;
        return state();
    }

    public TriageBState state() {
        return new TriageBState(fixApplied);
    }
}
