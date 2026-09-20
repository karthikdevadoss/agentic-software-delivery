package com.example.billingservice.outbox;

import com.example.billingservice.messaging.KafkaMessagingConfig;
import com.example.billingservice.messaging.OutboxEventEnvelope;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.data.domain.Limit;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import tools.jackson.databind.json.JsonMapper;

import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * The relay half of the transactional outbox pattern: polls for rows the
 * business transaction already committed (see ContractPlanService.enroll()),
 * publishes each to Kafka, and marks it published only on confirmed send
 * -- a publish failure leaves the row unpublished for the next poll to
 * retry, so at-least-once delivery holds even across a broker outage.
 * Never deletes/marks-published speculatively.
 *
 * SIMPLIFIED from the monolith's version (see app/'s OutboxPublisher):
 * that class looked up the destination topic via KafkaMessagingConfig's
 * EVENT_TYPE_TO_TOPIC registry because it relayed two independent event
 * types. This service only ever publishes ContractPlanEnrolled to
 * contract-plan-events, so the topic is hardcoded directly -- a registry
 * of size one is not a real abstraction, just an extra indirection to
 * read through.
 *
 * Conditional on app.kafka.enabled (see application.properties): when
 * Kafka isn't provisioned, this poller simply doesn't run at all rather
 * than repeatedly attempting -- and failing -- to publish. Outbox rows
 * still accumulate correctly in the meantime (ContractPlanService writes
 * them unconditionally); they are published in order the first time this
 * poller actually runs after Kafka is enabled.
 */
@Component
@ConditionalOnProperty(name = "app.kafka.enabled", havingValue = "true")
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
            kafkaTemplate.send(KafkaMessagingConfig.CONTRACT_PLAN_EVENTS_TOPIC, String.valueOf(event.getAggregateId()), jsonMapper.writeValueAsString(envelope))
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
