package com.example.notificationservice.notification;

import com.example.notificationservice.model.NotificationChannel;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * NOT_PRODUCTION_PROVISIONED: this is a real, tested dispatch point
 * (correctly selected by channel, correctly invoked, real metric emitted)
 * -- the one thing intentionally not wired in is a real email transport
 * (SES/SMTP), the same honest-scope boundary this project already draws
 * for Kafka/Redis: the integration point is real, the paid downstream
 * provider is not provisioned for a portfolio demo. Ported as-is from
 * app/src/main/java/com/example/customer/notification.
 */
@Component
public class EmailNotificationSender implements NotificationSender {

    private static final Logger log = LoggerFactory.getLogger(EmailNotificationSender.class);

    private final Counter dispatched;

    public EmailNotificationSender(MeterRegistry meterRegistry) {
        this.dispatched = Counter.builder("notification.dispatched").tag("channel", "EMAIL").register(meterRegistry);
    }

    @Override
    public NotificationChannel channel() {
        return NotificationChannel.EMAIL;
    }

    @Override
    public void send(Long customerId, String message) {
        log.info("EMAIL notification dispatched: customerId={}, message={}", customerId, message);
        dispatched.increment();
    }
}
