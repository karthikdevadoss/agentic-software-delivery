package com.example.customer.notification;

import com.example.customer.model.NotificationChannel;

/**
 * STRATEGY PATTERN: one interchangeable dispatch strategy per
 * NotificationChannel. CustomerPreferenceEventConsumer depends only on
 * this interface (via NotificationSenderFactory), never on a concrete
 * sender or a channel-specific if/else chain -- adding a new channel
 * means adding a new implementation, not editing existing dispatch code
 * (Open/Closed Principle).
 */
public interface NotificationSender {

    NotificationChannel channel();

    void send(Long customerId, String message);
}
