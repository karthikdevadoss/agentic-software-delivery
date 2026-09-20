package com.example.notificationservice.messaging;

import com.example.notificationservice.event.ContractPlanEnrolledEvent;
import com.example.notificationservice.model.NotificationChannel;
import com.example.notificationservice.notification.NotificationSenderFactory;
import com.example.notificationservice.outbox.ProcessedEvent;
import com.example.notificationservice.outbox.ProcessedEventRepository;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.json.JsonMapper;

/**
 * FAN-OUT consumer of ContractPlanEnrolled events published by
 * billing-service's own transactional outbox: sends a "welcome to your
 * new plan" notification. This service is one of (at least) two
 * independent consumers of this same event -- billing-service's own
 * downstream sync logic is the other -- which is exactly the fan-out
 * scenario that makes the composite-key idempotency ledger necessary
 * rather than optional (see ProcessedEvent's Javadoc): idempotency is
 * scoped to THIS consumer's own CONSUMER_NAME, never a bare eventId,
 * so this consumer's own processing can never be silently skipped just
 * because a different, unrelated consumer happened to record its own
 * processed-row first.
 *
 * Mirrors app/src/main/java/com/example/customer/messaging/ContractPlanNotificationConsumer.java's
 * idempotent-consumer pattern.
 */
@Component
@ConditionalOnProperty(name = "app.kafka.enabled", havingValue = "true")
public class ContractPlanEventConsumer {

    private static final Logger log = LoggerFactory.getLogger(ContractPlanEventConsumer.class);
    public static final String CONSUMER_NAME = "notification-contract-plan-enrolled";

    private final ProcessedEventRepository processedEventRepository;
    private final JsonMapper jsonMapper;
    private final NotificationSenderFactory notificationSenderFactory;
    private final Counter processed;
    private final Counter duplicatesSkipped;

    public ContractPlanEventConsumer(
            ProcessedEventRepository processedEventRepository,
            JsonMapper jsonMapper,
            NotificationSenderFactory notificationSenderFactory,
            MeterRegistry meterRegistry) {
        this.processedEventRepository = processedEventRepository;
        this.jsonMapper = jsonMapper;
        this.notificationSenderFactory = notificationSenderFactory;
        this.processed = Counter.builder("contract_plan_events.consumed").tag("consumer", CONSUMER_NAME).tag("result", "processed").register(meterRegistry);
        this.duplicatesSkipped = Counter.builder("contract_plan_events.consumed").tag("consumer", CONSUMER_NAME).tag("result", "duplicate-skipped").register(meterRegistry);
    }

    @KafkaListener(topics = KafkaMessagingConfig.CONTRACT_PLAN_EVENTS_TOPIC, groupId = KafkaMessagingConfig.CONTRACT_PLAN_NOTIFICATION_GROUP_ID)
    @Transactional
    public void onMessage(String envelopeJson) {
        OutboxEventEnvelope envelope = jsonMapper.readValue(envelopeJson, OutboxEventEnvelope.class);

        if (processedEventRepository.existsByConsumerNameAndEventId(CONSUMER_NAME, envelope.eventId())) {
            duplicatesSkipped.increment();
            log.info("Skipping already-processed event {} -- idempotent duplicate delivery", envelope.eventId());
            return;
        }

        ContractPlanEnrolledEvent event = jsonMapper.readValue(envelope.payload(), ContractPlanEnrolledEvent.class);
        log.info("Processed ContractPlanEnrolled (notification): customerId={}, planName={}", event.customerId(), event.planName());

        notificationSenderFactory.getSender(NotificationChannel.EMAIL)
                .send(event.customerId(), "Welcome to your new plan: " + event.planName());

        processedEventRepository.save(new ProcessedEvent(CONSUMER_NAME, envelope.eventId()));
        processed.increment();
    }
}
