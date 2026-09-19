package com.example.customer.messaging;

import com.example.customer.event.CustomerPreferenceUpdatedEvent;
import com.example.customer.notification.NotificationSenderFactory;
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
 * Consumes CustomerPreferenceUpdated events. IDEMPOTENT BY DESIGN: the
 * outbox/relay pattern only guarantees at-least-once delivery, so a
 * redelivered duplicate (broker retry, consumer rebalance, etc.) must be
 * a safe no-op -- checked against the durable processed_event ledger,
 * not an in-memory set that would forget on restart.
 *
 * A message that fails to deserialize/process (e.g. malformed JSON) is
 * not swallowed silently: it propagates so KafkaMessagingConfig's
 * DefaultErrorHandler can retry it, then route it to the dead-letter
 * topic if it never succeeds -- never an infinite poison-message loop.
 *
 * Conditional on app.kafka.enabled -- see application.properties'
 * EVENTING section: an always-on @KafkaListener with no reachable broker
 * caused a real production log-flooding incident this session (Railway
 * dropped messages). This component is not even instantiated, and no
 * listener container starts, until Kafka is actually provisioned.
 */
@Component
@ConditionalOnProperty(name = "app.kafka.enabled", havingValue = "true")
public class CustomerPreferenceEventConsumer {

    private static final Logger log = LoggerFactory.getLogger(CustomerPreferenceEventConsumer.class);
    static final String CONSUMER_NAME = "customer-preference-notification";

    private final ProcessedEventRepository processedEventRepository;
    private final JsonMapper jsonMapper;
    private final NotificationSenderFactory notificationSenderFactory;
    private final Counter processed;
    private final Counter duplicatesSkipped;

    public CustomerPreferenceEventConsumer(
            ProcessedEventRepository processedEventRepository,
            JsonMapper jsonMapper,
            NotificationSenderFactory notificationSenderFactory,
            MeterRegistry meterRegistry) {
        this.processedEventRepository = processedEventRepository;
        this.jsonMapper = jsonMapper;
        this.notificationSenderFactory = notificationSenderFactory;
        this.processed = Counter.builder("customer_preference_events.consumed").tag("result", "processed").register(meterRegistry);
        this.duplicatesSkipped = Counter.builder("customer_preference_events.consumed").tag("result", "duplicate-skipped").register(meterRegistry);
    }

    @KafkaListener(topics = KafkaMessagingConfig.CUSTOMER_PREFERENCE_EVENTS_TOPIC, groupId = KafkaMessagingConfig.CONSUMER_GROUP_ID)
    @Transactional
    public void onMessage(String envelopeJson) {
        OutboxEventEnvelope envelope = jsonMapper.readValue(envelopeJson, OutboxEventEnvelope.class);

        if (processedEventRepository.existsByConsumerNameAndEventId(CONSUMER_NAME, envelope.eventId())) {
            duplicatesSkipped.increment();
            log.info("Skipping already-processed event {} -- idempotent duplicate delivery", envelope.eventId());
            return;
        }

        CustomerPreferenceUpdatedEvent event = jsonMapper.readValue(envelope.payload(), CustomerPreferenceUpdatedEvent.class);
        log.info("Processed CustomerPreferenceUpdated: customerId={}, paperlessBilling={}, notificationChannel={}",
                event.customerId(), event.paperlessBilling(), event.notificationChannel());

        notificationSenderFactory.getSender(event.notificationChannel())
                .send(event.customerId(), "Your account preferences were updated.");

        processedEventRepository.save(new ProcessedEvent(CONSUMER_NAME, envelope.eventId()));
        processed.increment();
    }
}
