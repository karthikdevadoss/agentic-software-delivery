package com.example.customer.event;

import com.example.customer.model.NotificationChannel;

import java.time.Instant;

/** Kafka event payload for a customer's preference change -- the outbox_event.payload column stores this as JSON. */
public record CustomerPreferenceUpdatedEvent(
        Long customerId,
        boolean paperlessBilling,
        NotificationChannel notificationChannel,
        Instant updatedAt
) {
}
