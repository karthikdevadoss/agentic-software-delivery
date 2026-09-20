package com.example.notificationservice.notification;

import com.example.notificationservice.model.NotificationChannel;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * NOT_PRODUCTION_PROVISIONED: same honest-scope boundary as
 * EmailNotificationSender -- real dispatch selection/invocation/metric,
 * no paid SMS provider (Twilio/SNS) wired for a portfolio demo. Ported
 * as-is from app/src/main/java/com/example/customer/notification.
 */
@Component
public class SmsNotificationSender implements NotificationSender {

    private static final Logger log = LoggerFactory.getLogger(SmsNotificationSender.class);

    private final Counter dispatched;

    public SmsNotificationSender(MeterRegistry meterRegistry) {
        this.dispatched = Counter.builder("notification.dispatched").tag("channel", "SMS").register(meterRegistry);
    }

    @Override
    public NotificationChannel channel() {
        return NotificationChannel.SMS;
    }

    @Override
    public void send(Long customerId, String message) {
        log.info("SMS notification dispatched: customerId={}, message={}", customerId, message);
        dispatched.increment();
    }
}
