package com.example.notificationservice.outbox;

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
 * REAL BUG FOUND AND FIXED in the monolith this service is ported from
 * (app/src/main/java/com/example/customer/outbox/ProcessedEvent.java),
 * while adding a second, independently-consumed event (ContractPlanEnrolled):
 * this row was originally keyed by eventId alone. That is correct ONLY as
 * long as exactly one consumer group ever processes a given event. The
 * moment a second, independent consumer (Notification vs. BillingSync,
 * different consumer groups by design so Kafka delivers each of them its
 * own full copy of the topic) subscribes to the same event, a single
 * global "processed" flag is wrong: whichever consumer records its row
 * FIRST makes the SECOND, entirely independent consumer see "already
 * processed" and silently skip real work it was supposed to do -- a true
 * fan-out silently degrades into "only the fastest consumer actually
 * runs." The composite key (consumerName, eventId) scopes idempotency
 * per consumer, which is what "at-least-once delivery, exactly-once
 * processing PER CONSUMER" actually requires.
 *
 * This service IS one of the two independent fan-out consumers that bug
 * was about (the other being billing-service's own downstream sync
 * logic) -- getting the composite key right here, not a global-by-eventId
 * shortcut, is what keeps this service's own notification dispatch from
 * silently going dark if another consumer of the same
 * ContractPlanEnrolled event processes it first.
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
