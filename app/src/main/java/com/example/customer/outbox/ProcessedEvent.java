package com.example.customer.outbox;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;

import java.time.Instant;

/**
 * Durable idempotency ledger for the CONSUMER side. The outbox pattern
 * guarantees at-least-once delivery -- a consumer restart, rebalance, or
 * broker retry can and will redeliver the same event_id more than once.
 * A row existing here means "already processed"; a listener checks this
 * before doing any real work, and a duplicate delivery becomes a safe
 * no-op instead of a repeated side effect.
 */
@Entity
public class ProcessedEvent {

    @Id
    @Column(length = 36)
    private String eventId;

    @Column(nullable = false)
    private Instant processedAt;

    protected ProcessedEvent() {
    }

    public ProcessedEvent(String eventId) {
        this.eventId = eventId;
        this.processedAt = Instant.now();
    }

    public String getEventId() {
        return eventId;
    }

    public Instant getProcessedAt() {
        return processedAt;
    }
}
