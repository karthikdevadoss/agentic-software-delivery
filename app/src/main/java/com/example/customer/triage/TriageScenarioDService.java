package com.example.customer.triage;

import com.example.customer.messaging.ContractPlanBillingSyncConsumer;
import com.example.customer.messaging.ContractPlanNotificationConsumer;
import com.example.customer.outbox.ProcessedEvent;
import com.example.customer.outbox.ProcessedEventRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

/**
 * Incident Triage Lab -- Scenario D (fan-out idempotency: the real
 * ProcessedEvent global-by-eventId bug found and fixed while building
 * BL-003, see ProcessedEvent's Javadoc for the full story).
 *
 * PEDAGOGICAL REPLAY, NOT A REINTRODUCED PRODUCTION BUG: exactly the same
 * isolation pattern as Scenario A -- every reproduce() call generates a
 * brand-new synthetic eventId (never reused, never a real Kafka message
 * or real Kafka broker involved), so the buggy-vs-fixed comparison is
 * always a clean "first delivery of a new event" regardless of how many
 * times this is called. checkBuggy() below is a preserved snapshot of the
 * REAL pre-composite-key check (ProcessedEventRepository.existsByEventId,
 * itself already Javadoc'd as existing ONLY for this scenario); the fixed
 * path delegates to the real, current, production
 * existsByConsumerNameAndEventId -- never a second copy of the fix.
 */
@Service
public class TriageScenarioDService {

    private final ProcessedEventRepository processedEventRepository;

    private volatile String eventId;
    private volatile boolean fixApplied = false;

    public TriageScenarioDService(ProcessedEventRepository processedEventRepository) {
        this.processedEventRepository = processedEventRepository;
    }

    public synchronized TriageScenarioDState reset() {
        this.eventId = UUID.randomUUID().toString();
        this.fixApplied = false;
        return state();
    }

    /** Simulates a single ContractPlanEnrolled event being delivered to
     * BOTH independent fan-out consumers (Notification, then BillingSync)
     * for a brand-new synthetic event -- real ProcessedEvent rows are
     * written to the real table, just under a synthetic eventId no real
     * Kafka message will ever use. */
    @Transactional
    public synchronized TriageScenarioDReproductionResult reproduce() {
        this.eventId = UUID.randomUUID().toString(); // always a fresh event -- see class Javadoc
        String thisEventId = eventId;

        boolean notificationRan = processOne(ContractPlanNotificationConsumer.CONSUMER_NAME, thisEventId);
        boolean billingSyncRan = processOne(ContractPlanBillingSyncConsumer.CONSUMER_NAME, thisEventId);

        // The defect: BillingSync wrongly sees "already processed" because
        // the buggy check ignores WHICH consumer asked, and Notification's
        // row (for this same eventId) already exists -- real work silently
        // never happens for the second consumer.
        boolean defectReproduced = !fixApplied && !billingSyncRan;

        return new TriageScenarioDReproductionResult(thisEventId, fixApplied, notificationRan, billingSyncRan, defectReproduced);
    }

    /** @return true if this consumer's real work ran (not skipped as a false-or-genuine duplicate) */
    private boolean processOne(String consumerName, String eventId) {
        boolean alreadyProcessed = fixApplied
                ? processedEventRepository.existsByConsumerNameAndEventId(consumerName, eventId) // FIXED: correctly scoped per consumer
                : processedEventRepository.existsByEventId(eventId); // BUGGY: global, ignores which consumer asked
        if (alreadyProcessed) {
            return false;
        }
        processedEventRepository.save(new ProcessedEvent(consumerName, eventId));
        return true;
    }

    public synchronized TriageScenarioDState approveFix() {
        this.fixApplied = true;
        return state();
    }

    public TriageScenarioDState state() {
        return new TriageScenarioDState(eventId, fixApplied);
    }
}
