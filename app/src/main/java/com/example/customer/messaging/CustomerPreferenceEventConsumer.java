package com.example.customer.messaging;

import com.example.customer.event.CustomerPreferenceUpdatedEvent;
import com.example.customer.outbox.ProcessedEvent;
import com.example.customer.outbox.ProcessedEventRepository;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
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
 */
@Component
public class CustomerPreferenceEventConsumer {

    private static final Logger log = LoggerFactory.getLogger(CustomerPreferenceEventConsumer.class);

    private final ProcessedEventRepository processedEventRepository;
    private final JsonMapper jsonMapper;
    private final Counter processed;
    private final Counter duplicatesSkipped;

    public CustomerPreferenceEventConsumer(
            ProcessedEventRepository processedEventRepository,
            JsonMapper jsonMapper,
            MeterRegistry meterRegistry) {
        this.processedEventRepository = processedEventRepository;
        this.jsonMapper = jsonMapper;
        this.processed = Counter.builder("customer_preference_events.consumed").tag("result", "processed").register(meterRegistry);
        this.duplicatesSkipped = Counter.builder("customer_preference_events.consumed").tag("result", "duplicate-skipped").register(meterRegistry);
    }

    @KafkaListener(topics = KafkaMessagingConfig.CUSTOMER_PREFERENCE_EVENTS_TOPIC, groupId = KafkaMessagingConfig.CONSUMER_GROUP_ID)
    @Transactional
    public void onMessage(String envelopeJson) {
        OutboxEventEnvelope envelope = jsonMapper.readValue(envelopeJson, OutboxEventEnvelope.class);

        if (processedEventRepository.existsById(envelope.eventId())) {
            duplicatesSkipped.increment();
            log.info("Skipping already-processed event {} -- idempotent duplicate delivery", envelope.eventId());
            return;
        }

        CustomerPreferenceUpdatedEvent event = jsonMapper.readValue(envelope.payload(), CustomerPreferenceUpdatedEvent.class);
        log.info("Processed CustomerPreferenceUpdated: customerId={}, paperlessBilling={}, notificationChannel={}",
                event.customerId(), event.paperlessBilling(), event.notificationChannel());

        processedEventRepository.save(new ProcessedEvent(envelope.eventId()));
        processed.increment();
    }
}
