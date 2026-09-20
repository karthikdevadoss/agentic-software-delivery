package com.example.billingservice.outbox;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.UUID;

/**
 * One row = one domain event to be published, written in the SAME
 * database transaction as the business change it describes (see
 * ContractPlanService.enroll()). This is what makes the outbox pattern
 * safe where a naive "write to DB, then call Kafka" dual write is not:
 * either both the business row and this event row commit together, or
 * neither does -- there is no window where one succeeds and the other is
 * lost.
 *
 * @JdbcTypeCode(SqlTypes.LONGVARCHAR) on payload: ported from the
 * monolith's real, CI-found fix (see app/'s OutboxEvent Javadoc) -- @Lob
 * on a String maps to CLOB, which Hibernate's Postgres dialect validates
 * against the "oid" large-object column type; this service is H2-only
 * today, but the annotation is kept so a future Postgres profile (see
 * app/'s own dual-profile setup) does not silently reintroduce that bug.
 */
@Entity
public class OutboxEvent {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 36)
    private String eventId;

    @Column(nullable = false, length = 50)
    private String aggregateType;

    @Column(nullable = false)
    private Long aggregateId;

    @Column(nullable = false, length = 100)
    private String eventType;

    @JdbcTypeCode(SqlTypes.LONGVARCHAR)
    @Column(nullable = false)
    private String payload;

    @Column(nullable = false)
    private Instant createdAt;

    private Instant publishedAt;

    protected OutboxEvent() {
    }

    public OutboxEvent(String aggregateType, Long aggregateId, String eventType, String payload) {
        this.eventId = UUID.randomUUID().toString();
        this.aggregateType = aggregateType;
        this.aggregateId = aggregateId;
        this.eventType = eventType;
        this.payload = payload;
        this.createdAt = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public String getEventId() {
        return eventId;
    }

    public String getAggregateType() {
        return aggregateType;
    }

    public Long getAggregateId() {
        return aggregateId;
    }

    public String getEventType() {
        return eventType;
    }

    public String getPayload() {
        return payload;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getPublishedAt() {
        return publishedAt;
    }

    public void markPublished() {
        this.publishedAt = Instant.now();
    }
}
