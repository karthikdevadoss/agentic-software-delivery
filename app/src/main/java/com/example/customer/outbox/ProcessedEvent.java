package com.example.customer.outbox;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;

import java.time.Instant;

/**
 * Durable idempotency ledger for the CONSUMER side. The outbox pattern
 * guarantees at-least-once delivery -- a consumer restart, rebalance, or
 * broker retry can and will redeliver the same event_id more than once.
 *
 * REAL BUG FOUND AND FIXED while adding a second, independently-consumed
 * event (ContractPlanEnrolled, see CustomerPreferenceEventFlowIntegrationTest's
 * sibling test for the fix's proof): this row was originally keyed by
 * eventId alone. That is correct ONLY as long as exactly one consumer
 * group ever processes a given event. The moment a second, independent
 * consumer (Notification vs. BillingSync, different consumer groups by
 * design so Kafka delivers each of them its own full copy of the topic)
 * subscribes to the same event, a single global "processed" flag is wrong:
 * whichever consumer records its row FIRST makes the SECOND, entirely
 * independent consumer see "already processed" and silently skip real
 * work it was supposed to do -- a true fan-out silently degrades into
 * "only the fastest consumer actually runs." The composite key
 * (consumerName, eventId) scopes idempotency per consumer, which is what
 * "at-least-once delivery, exactly-once processing PER CONSUMER" actually
 * requires. See Triage Scenario D for a reproducible replay of this exact
 * defect.
 */
@Entity
@IdClass(ProcessedEventId.class)
public class ProcessedEvent {

    @Id
    @Column(length = 100)
    private String consumerName;

    @Id
    @Column(length = 36)
    private String eventId;

    @Column(nullable = false)
    private Instant processedAt;

    protected ProcessedEvent() {
    }

    public ProcessedEvent(String consumerName, String eventId) {
        this.consumerName = consumerName;
        this.eventId = eventId;
        this.processedAt = Instant.now();
    }

    public String getConsumerName() {
        return consumerName;
    }

    public String getEventId() {
        return eventId;
    }

    public Instant getProcessedAt() {
        return processedAt;
    }
}
