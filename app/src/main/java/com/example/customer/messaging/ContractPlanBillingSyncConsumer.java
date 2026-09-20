package com.example.customer.messaging;

import com.example.customer.event.ContractPlanEnrolledEvent;
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
 * FAN-OUT, consumer #2 of 2: independently subscribes to the SAME
 * ContractPlanEnrolled topic as {@link ContractPlanNotificationConsumer},
 * under its own consumer group -- simulates syncing the new enrollment to
 * an external billing system by writing a {@link BillingSyncRecord}, a
 * real, independently-verifiable side effect distinct from the
 * notification consumer's own. This is the concrete proof that fan-out is
 * real: one event, two unrelated downstream concerns, each fully and
 * independently satisfied.
 */
@Component
@ConditionalOnProperty(name = "app.kafka.enabled", havingValue = "true")
public class ContractPlanBillingSyncConsumer {

    private static final Logger log = LoggerFactory.getLogger(ContractPlanBillingSyncConsumer.class);
    public static final String CONSUMER_NAME = "contract-plan-billing-sync";

    private final ProcessedEventRepository processedEventRepository;
    private final BillingSyncRecordRepository billingSyncRecordRepository;
    private final JsonMapper jsonMapper;
    private final Counter processed;
    private final Counter duplicatesSkipped;

    public ContractPlanBillingSyncConsumer(
            ProcessedEventRepository processedEventRepository,
            BillingSyncRecordRepository billingSyncRecordRepository,
            JsonMapper jsonMapper,
            MeterRegistry meterRegistry) {
        this.processedEventRepository = processedEventRepository;
        this.billingSyncRecordRepository = billingSyncRecordRepository;
        this.jsonMapper = jsonMapper;
        this.processed = Counter.builder("contract_plan_events.consumed").tag("consumer", CONSUMER_NAME).tag("result", "processed").register(meterRegistry);
        this.duplicatesSkipped = Counter.builder("contract_plan_events.consumed").tag("consumer", CONSUMER_NAME).tag("result", "duplicate-skipped").register(meterRegistry);
    }

    @KafkaListener(topics = KafkaMessagingConfig.CONTRACT_PLAN_EVENTS_TOPIC, groupId = KafkaMessagingConfig.CONTRACT_PLAN_BILLING_SYNC_GROUP_ID)
    @Transactional
    public void onMessage(String envelopeJson) {
        OutboxEventEnvelope envelope = jsonMapper.readValue(envelopeJson, OutboxEventEnvelope.class);

        if (processedEventRepository.existsByConsumerNameAndEventId(CONSUMER_NAME, envelope.eventId())) {
            duplicatesSkipped.increment();
            log.info("Skipping already-processed event {} -- idempotent duplicate delivery", envelope.eventId());
            return;
        }

        ContractPlanEnrolledEvent event = jsonMapper.readValue(envelope.payload(), ContractPlanEnrolledEvent.class);
        log.info("Processed ContractPlanEnrolled (billing sync): contractPlanId={}, customerId={}", event.contractPlanId(), event.customerId());

        billingSyncRecordRepository.save(new BillingSyncRecord(
                event.contractPlanId(), event.customerId(), event.planName(), event.ratePerKwh()));

        processedEventRepository.save(new ProcessedEvent(CONSUMER_NAME, envelope.eventId()));
        processed.increment();
    }
}
