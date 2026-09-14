package com.example.customer.outbox;

import com.example.customer.messaging.KafkaMessagingConfig;
import com.example.customer.messaging.OutboxEventEnvelope;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Limit;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import tools.jackson.databind.json.JsonMapper;

import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * The relay half of the transactional outbox pattern: polls for rows the
 * business transaction already committed (see CustomerPreferenceService),
 * publishes each to Kafka, and marks it published only on confirmed send
 * -- a publish failure leaves the row unpublished for the next poll to
 * retry, so at-least-once delivery holds even across a broker outage.
 * Never deletes/marks-published speculatively.
 */
@Component
public class OutboxPublisher {

    private static final Logger log = LoggerFactory.getLogger(OutboxPublisher.class);
    private static final int BATCH_SIZE = 20;

    private final OutboxEventRepository outboxEventRepository;
    private final KafkaTemplate<String, String> kafkaTemplate;
    private final JsonMapper jsonMapper;
    private final Counter published;
    private final Counter publishFailures;

    public OutboxPublisher(
            OutboxEventRepository outboxEventRepository,
            KafkaTemplate<String, String> kafkaTemplate,
            JsonMapper jsonMapper,
            MeterRegistry meterRegistry) {
        this.outboxEventRepository = outboxEventRepository;
        this.kafkaTemplate = kafkaTemplate;
        this.jsonMapper = jsonMapper;
        this.published = Counter.builder("outbox.events").tag("result", "published").register(meterRegistry);
        this.publishFailures = Counter.builder("outbox.events").tag("result", "publish-failed").register(meterRegistry);
    }

    @Scheduled(fixedDelay = 2000)
    public void publishPendingEvents() {
        List<OutboxEvent> pending = outboxEventRepository.findByPublishedAtIsNullOrderByCreatedAtAsc(Limit.of(BATCH_SIZE));
        for (OutboxEvent event : pending) {
            publishOne(event);
        }
    }

    private void publishOne(OutboxEvent event) {
        OutboxEventEnvelope envelope = new OutboxEventEnvelope(
                event.getEventId(), event.getAggregateType(), event.getAggregateId(), event.getEventType(), event.getPayload());
        try {
            kafkaTemplate.send(KafkaMessagingConfig.CUSTOMER_PREFERENCE_EVENTS_TOPIC,
                            String.valueOf(event.getAggregateId()), jsonMapper.writeValueAsString(envelope))
                    .get(5, TimeUnit.SECONDS);
            event.markPublished();
            outboxEventRepository.save(event);
            published.increment();
        } catch (Exception publishFailed) {
            publishFailures.increment();
            log.warn("Failed to publish outbox event {} (aggregate {}#{}); left unpublished, will retry on the next poll",
                    event.getEventId(), event.getAggregateType(), event.getAggregateId(), publishFailed);
        }
    }
}
