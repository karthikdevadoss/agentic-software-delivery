package com.example.customer.messaging;

import com.example.customer.event.ContractPlanEnrolledEvent;
import com.example.customer.notification.NotificationSenderFactory;
import com.example.customer.model.NotificationChannel;
import com.example.customer.outbox.ProcessedEvent;
import com.example.customer.outbox.ProcessedEventRepository;
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
 * FAN-OUT, consumer #1 of 2: independently subscribes to the SAME
 * ContractPlanEnrolled topic as {@link ContractPlanBillingSyncConsumer},
 * under its own consumer group (Kafka delivers each consumer group its own
 * full copy of every partition) -- sends a "welcome to your new plan"
 * notification. Idempotency is scoped to THIS consumer's own name (see
 * ProcessedEvent's Javadoc for why a single global eventId flag is wrong
 * once more than one independent consumer exists).
 */
@Component
@ConditionalOnProperty(name = "app.kafka.enabled", havingValue = "true")
public class ContractPlanNotificationConsumer {

    private static final Logger log = LoggerFactory.getLogger(ContractPlanNotificationConsumer.class);
    static final String CONSUMER_NAME = "contract-plan-notification";

    private final ProcessedEventRepository processedEventRepository;
    private final JsonMapper jsonMapper;
    private final NotificationSenderFactory notificationSenderFactory;
    private final Counter processed;
    private final Counter duplicatesSkipped;

    public ContractPlanNotificationConsumer(
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
