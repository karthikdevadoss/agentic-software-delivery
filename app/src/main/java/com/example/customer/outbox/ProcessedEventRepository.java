package com.example.customer.outbox;

import org.springframework.data.jpa.repository.JpaRepository;

public interface ProcessedEventRepository extends JpaRepository<ProcessedEvent, ProcessedEventId> {

    boolean existsByConsumerNameAndEventId(String consumerName, String eventId);

    /** FOR INCIDENT TRIAGE LAB SCENARIO D ONLY -- replays the real,
     * pre-fix "global by eventId" idempotency check (ignoring
     * consumerName entirely) against the current, correctly-composite-
     * keyed table, so the historical defect can be demonstrated live
     * without a second parallel schema. Production code must never call
     * this -- see ProcessedEvent's Javadoc and TriageScenarioDService. */
    boolean existsByEventId(String eventId);
}
