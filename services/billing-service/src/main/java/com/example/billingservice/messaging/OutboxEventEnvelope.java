package com.example.billingservice.messaging;

/**
 * The actual Kafka message value: transport metadata (eventId, for
 * consumer-side idempotency) plus the business payload as an already-
 * serialized JSON string, so this envelope's own shape never needs to
 * change as new event/payload types are added.
 */
public record OutboxEventEnvelope(
        String eventId,
        String aggregateType,
        Long aggregateId,
        String eventType,
        String payload
) {
}
