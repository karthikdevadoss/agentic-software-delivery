package com.example.notificationservice.notification;

import com.example.notificationservice.model.NotificationChannel;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * NULL OBJECT PATTERN, composed with Strategy: a customer whose
 * notification preference is NONE is a real, first-class outcome, not an
 * error case or a branch a caller has to special-case -- NotificationSenderFactory
 * selects this sender exactly like any other, and it correctly does
 * nothing. Ported as-is from app/src/main/java/com/example/customer/notification.
 */
@Component
public class NoOpNotificationSender implements NotificationSender {

    private static final Logger log = LoggerFactory.getLogger(NoOpNotificationSender.class);

    private final Counter skipped;

    public NoOpNotificationSender(MeterRegistry meterRegistry) {
        this.skipped = Counter.builder("notification.dispatched").tag("channel", "NONE").register(meterRegistry);
    }

    @Override
    public NotificationChannel channel() {
        return NotificationChannel.NONE;
    }

    @Override
    public void send(Long customerId, String message) {
        log.debug("No notification sent: customerId={} has notification channel NONE", customerId);
        skipped.increment();
    }
}
