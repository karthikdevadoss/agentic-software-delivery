package com.example.customer.messaging;

import com.example.customer.event.ContractPlanEnrolledEvent;
import com.example.customer.event.CustomerPreferenceUpdatedEvent;
import com.example.customer.model.NotificationChannel;
import com.example.customer.notification.NotificationSender;
import com.example.customer.notification.NotificationSenderFactory;
import com.example.customer.outbox.ProcessedEvent;
import com.example.customer.outbox.ProcessedEventRepository;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import tools.jackson.databind.json.JsonMapper;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * BL-057: unit tests for the two notification consumers' real logic
 * (idempotent skip + channel selection + message), independent of Kafka.
 */
@ExtendWith(MockitoExtension.class)
class NotificationConsumersTest {

    @Mock
    private ProcessedEventRepository processedEventRepository;
    @Mock
    private NotificationSenderFactory notificationSenderFactory;
    @Mock
    private NotificationSender sender;

    private final JsonMapper jsonMapper = JsonMapper.builder().build();
    private final SimpleMeterRegistry meterRegistry = new SimpleMeterRegistry();

    private String envelope(String eventId, String eventType, Object payload) {
        return jsonMapper.writeValueAsString(new OutboxEventEnvelope(eventId, "Customer", 5L, eventType,
                jsonMapper.writeValueAsString(payload)));
    }

    @Test
    void preferenceUpdate_notifiesOnTheChannelTheCustomerChose_andMarksProcessed() {
        when(processedEventRepository.existsByConsumerNameAndEventId(anyString(), anyString())).thenReturn(false);
        when(notificationSenderFactory.getSender(NotificationChannel.SMS)).thenReturn(sender);
        CustomerPreferenceEventConsumer consumer = new CustomerPreferenceEventConsumer(
                processedEventRepository, jsonMapper, notificationSenderFactory, meterRegistry);

        consumer.onMessage(envelope("pref-1", "CustomerPreferenceUpdated",
                new CustomerPreferenceUpdatedEvent(5L, true, NotificationChannel.SMS, Instant.parse("2026-09-01T10:00:00Z"))));

        verify(sender).send(5L, "Your account preferences were updated.");
        ArgumentCaptor<ProcessedEvent> processed = ArgumentCaptor.forClass(ProcessedEvent.class);
        verify(processedEventRepository).save(processed.capture());
        assertThat(processed.getValue().getEventId()).isEqualTo("pref-1");
        assertThat(meterRegistry.get("customer_preference_events.consumed").tag("result", "processed").counter().count()).isEqualTo(1.0);
    }

    @Test
    void preferenceUpdate_duplicateDelivery_sendsNothing() {
        when(processedEventRepository.existsByConsumerNameAndEventId(anyString(), anyString())).thenReturn(true);
        CustomerPreferenceEventConsumer consumer = new CustomerPreferenceEventConsumer(
                processedEventRepository, jsonMapper, notificationSenderFactory, meterRegistry);

        consumer.onMessage(envelope("pref-dup", "CustomerPreferenceUpdated",
                new CustomerPreferenceUpdatedEvent(5L, true, NotificationChannel.SMS, Instant.now())));

        verify(notificationSenderFactory, never()).getSender(any());
        verify(processedEventRepository, never()).save(any());
        assertThat(meterRegistry.get("customer_preference_events.consumed").tag("result", "duplicate-skipped").counter().count()).isEqualTo(1.0);
    }

    @Test
    void planEnrolled_sendsWelcomeEmail_andMarksProcessed() {
        when(processedEventRepository.existsByConsumerNameAndEventId(anyString(), anyString())).thenReturn(false);
        when(notificationSenderFactory.getSender(NotificationChannel.EMAIL)).thenReturn(sender);
        ContractPlanNotificationConsumer consumer = new ContractPlanNotificationConsumer(
                processedEventRepository, jsonMapper, notificationSenderFactory, meterRegistry);

        consumer.onMessage(envelope("plan-1", "ContractPlanEnrolled", new ContractPlanEnrolledEvent(
                77L, 5L, "Green-Saver-24", new BigDecimal("0.2100"), LocalDate.of(2026, 10, 1), Instant.parse("2026-09-01T10:00:00Z"))));

        verify(sender).send(5L, "Welcome to your new plan: Green-Saver-24");
        verify(processedEventRepository).save(any(ProcessedEvent.class));
        assertThat(meterRegistry.get("contract_plan_events.consumed")
                .tag("consumer", ContractPlanNotificationConsumer.CONSUMER_NAME).tag("result", "processed").counter().count()).isEqualTo(1.0);
    }

    @Test
    void planEnrolled_duplicateDelivery_sendsNothing() {
        when(processedEventRepository.existsByConsumerNameAndEventId(anyString(), anyString())).thenReturn(true);
        ContractPlanNotificationConsumer consumer = new ContractPlanNotificationConsumer(
                processedEventRepository, jsonMapper, notificationSenderFactory, meterRegistry);

        consumer.onMessage(envelope("plan-dup", "ContractPlanEnrolled", new ContractPlanEnrolledEvent(
                77L, 5L, "Green-Saver-24", new BigDecimal("0.2100"), LocalDate.now(), Instant.now())));

        verify(notificationSenderFactory, never()).getSender(any());
        verify(processedEventRepository, never()).save(any());
    }
}
