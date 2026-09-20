package com.example.notificationservice.outbox;

import org.springframework.data.jpa.repository.JpaRepository;

/**
 * Ported from app/src/main/java/com/example/customer/outbox/ProcessedEventRepository.java,
 * minus the monolith's Incident-Triage-Lab-only existsByEventId escape
 * hatch (that lab does not exist in this service -- see ProcessedEvent's
 * Javadoc for why production code must key idempotency by the composite
 * (consumerName, eventId), never eventId alone).
 */
public interface ProcessedEventRepository extends JpaRepository<ProcessedEvent, ProcessedEventId> {

    boolean existsByConsumerNameAndEventId(String consumerName, String eventId);
}
