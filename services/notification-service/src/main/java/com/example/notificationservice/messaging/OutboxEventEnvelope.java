package com.example.notificationservice.messaging;

/**
 * The actual Kafka message value: transport metadata (eventId, for
 * consumer-side idempotency) plus the business payload as an already-
 * serialized JSON string, so this envelope's own shape never needs to
 * change as new event/payload types are added. Ported as-is from
 * app/src/main/java/com/example/customer/messaging/OutboxEventEnvelope.java
 * -- must stay structurally identical to the producer's (billing-service)
 * envelope, since it is deserialized straight off the wire.
 */
public record OutboxEventEnvelope(
        String eventId,
        String aggregateType,
        Long aggregateId,
        String eventType,
        String payload
) {
}
