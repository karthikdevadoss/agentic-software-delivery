package com.example.notificationservice.notification;

import com.example.notificationservice.model.NotificationChannel;

/**
 * STRATEGY PATTERN: one interchangeable dispatch strategy per
 * NotificationChannel. Callers (the Kafka consumer and the direct
 * POST /notifications/send endpoint alike) depend only on this interface
 * (via NotificationSenderFactory), never on a concrete sender or a
 * channel-specific if/else chain -- adding a new channel means adding a
 * new implementation, not editing existing dispatch code (Open/Closed
 * Principle). Ported as-is from app/src/main/java/com/example/customer/notification.
 */
public interface NotificationSender {

    NotificationChannel channel();

    void send(Long customerId, String message);
}
