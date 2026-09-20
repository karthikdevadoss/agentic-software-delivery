package com.example.notificationservice.notification;

import com.example.notificationservice.model.NotificationChannel;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Real senders, a real (in-memory) MeterRegistry -- no mocks. Proves the
 * FACTORY correctly resolves the STRATEGY registered for each channel,
 * that each sender's own real send() runs (not a mock verifying a call
 * happened), and that a channel with no registered sender fails loudly
 * rather than silently doing nothing. Ported as-is from
 * app/src/test/java/com/example/customer/notification/NotificationSenderFactoryTest.java.
 */
class NotificationSenderFactoryTest {

    private final SimpleMeterRegistry meterRegistry = new SimpleMeterRegistry();
    private final EmailNotificationSender emailSender = new EmailNotificationSender(meterRegistry);
    private final SmsNotificationSender smsSender = new SmsNotificationSender(meterRegistry);
    private final NoOpNotificationSender noOpSender = new NoOpNotificationSender(meterRegistry);
    private final NotificationSenderFactory factory =
            new NotificationSenderFactory(List.of(emailSender, smsSender, noOpSender));

    @Test
    void resolvesTheEmailSenderForTheEmailChannel() {
        assertThat(factory.getSender(NotificationChannel.EMAIL)).isSameAs(emailSender);
    }

    @Test
    void resolvesTheSmsSenderForTheSmsChannel() {
        assertThat(factory.getSender(NotificationChannel.SMS)).isSameAs(smsSender);
    }

    @Test
    void resolvesTheNoOpSenderForTheNoneChannel() {
        assertThat(factory.getSender(NotificationChannel.NONE)).isSameAs(noOpSender);
    }

    @Test
    void aChannelWithNoRegisteredSender_failsLoudly_notSilently() {
        NotificationSenderFactory incompleteFactory = new NotificationSenderFactory(List.of(emailSender));

        assertThatThrownBy(() -> incompleteFactory.getSender(NotificationChannel.SMS))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("SMS");
    }

    @Test
    void emailSender_realSendIncrementsARealCounter_notAMockedCall() {
        double before = meterRegistry.get("notification.dispatched").tag("channel", "EMAIL").counter().count();

        emailSender.send(42L, "test message");

        double after = meterRegistry.get("notification.dispatched").tag("channel", "EMAIL").counter().count();
        assertThat(after).isEqualTo(before + 1.0);
    }

    @Test
    void smsSender_realSendIncrementsARealCounter() {
        double before = meterRegistry.get("notification.dispatched").tag("channel", "SMS").counter().count();

        smsSender.send(42L, "test message");

        double after = meterRegistry.get("notification.dispatched").tag("channel", "SMS").counter().count();
        assertThat(after).isEqualTo(before + 1.0);
    }

    @Test
    void noOpSender_stillIncrementsARealCounter_soANoneChoiceIsObservableNotInvisible() {
        double before = meterRegistry.get("notification.dispatched").tag("channel", "NONE").counter().count();

        noOpSender.send(42L, "test message");

        double after = meterRegistry.get("notification.dispatched").tag("channel", "NONE").counter().count();
        assertThat(after).isEqualTo(before + 1.0);
    }
}
