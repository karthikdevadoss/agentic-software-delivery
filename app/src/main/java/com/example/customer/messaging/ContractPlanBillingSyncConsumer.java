package com.example.customer.messaging;

import com.example.customer.event.ContractPlanEnrolledEvent;
import com.example.customer.model.NotificationChannel;
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
 * FAN-OUT, consumer #2 of 2: independently subscribes to the SAME
 * ContractPlanEnrolled topic as {@link ContractPlanNotificationConsumer},
 * under its own consumer group -- simulates syncing the new enrollment to
 * an external billing system by writing a {@link BillingSyncRecord}, a
 * real, independently-verifiable side effect distinct from the
 * notification consumer's own. This is the concrete proof that fan-out is
 * real: one event, two unrelated downstream concerns, each fully and
 * independently satisfied.
 *
 * SAGA-STYLE COMPENSATION for a genuine BUSINESS failure, not Kafka's
 * infra-level retry+DLT: a real external billing system can permanently
 * reject a plan's terms (e.g. a rate outside what it can invoice) --
 * retrying that message would fail identically forever. No real billing
 * provider exists here (same honest scope boundary as
 * AppointmentAvailabilityClient), so this failure mode is simulated via a
 * deliberate, clearly-documented trigger (a plan name starting with
 * "SIMULATE_BILLING_FAILURE") rather than left undemonstrated. On this
 * simulated failure the message is NOT thrown back to Kafka's error
 * handler (that would incorrectly route a permanent business failure
 * through the transient-failure retry/DLT path meant for message-format
 * problems) -- instead a {@link BillingSyncCompensation} row is written
 * and an operations notification is sent, and the event is marked
 * processed: the compensation itself IS the correct, complete handling.
 */
@Component
@ConditionalOnProperty(name = "app.kafka.enabled", havingValue = "true")
public class ContractPlanBillingSyncConsumer {

    private static final Logger log = LoggerFactory.getLogger(ContractPlanBillingSyncConsumer.class);
    public static final String CONSUMER_NAME = "contract-plan-billing-sync";

    /** Demo-only trigger for the simulated permanent billing-system
     * rejection -- see class Javadoc. Never a real external system's
     * actual rejection rule. */
    static final String SIMULATED_FAILURE_PLAN_NAME_PREFIX = "SIMULATE_BILLING_FAILURE";

    private final ProcessedEventRepository processedEventRepository;
    private final BillingSyncRecordRepository billingSyncRecordRepository;
    private final BillingSyncCompensationRepository billingSyncCompensationRepository;
    private final NotificationSenderFactory notificationSenderFactory;
    private final JsonMapper jsonMapper;
    private final Counter processed;
    private final Counter duplicatesSkipped;
    private final Counter compensated;

    public ContractPlanBillingSyncConsumer(
            ProcessedEventRepository processedEventRepository,
            BillingSyncRecordRepository billingSyncRecordRepository,
            BillingSyncCompensationRepository billingSyncCompensationRepository,
            NotificationSenderFactory notificationSenderFactory,
            JsonMapper jsonMapper,
            MeterRegistry meterRegistry) {
        this.processedEventRepository = processedEventRepository;
        this.billingSyncRecordRepository = billingSyncRecordRepository;
        this.billingSyncCompensationRepository = billingSyncCompensationRepository;
        this.notificationSenderFactory = notificationSenderFactory;
        this.jsonMapper = jsonMapper;
        this.processed = Counter.builder("contract_plan_events.consumed").tag("consumer", CONSUMER_NAME).tag("result", "processed").register(meterRegistry);
        this.duplicatesSkipped = Counter.builder("contract_plan_events.consumed").tag("consumer", CONSUMER_NAME).tag("result", "duplicate-skipped").register(meterRegistry);
        this.compensated = Counter.builder("contract_plan_events.consumed").tag("consumer", CONSUMER_NAME).tag("result", "compensated").register(meterRegistry);
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

        if (event.planName().startsWith(SIMULATED_FAILURE_PLAN_NAME_PREFIX)) {
            compensate(event);
        } else {
            log.info("Processed ContractPlanEnrolled (billing sync): contractPlanId={}, customerId={}", event.contractPlanId(), event.customerId());
            billingSyncRecordRepository.save(new BillingSyncRecord(
                    event.contractPlanId(), event.customerId(), event.planName(), event.ratePerKwh()));
            processed.increment();
        }

        // Compensated is still a COMPLETE, successful handling of this
        // event -- marked processed either way, never left for Kafka's
        // retry+DLT machinery to keep re-attempting a failure retrying can't fix.
        processedEventRepository.save(new ProcessedEvent(CONSUMER_NAME, envelope.eventId()));
    }

    private void compensate(ContractPlanEnrolledEvent event) {
        String reason = "Simulated permanent billing-system rejection for plan '" + event.planName() + "'";
        log.warn("Billing sync compensating (not retrying): contractPlanId={}, reason={}", event.contractPlanId(), reason);

        billingSyncCompensationRepository.save(new BillingSyncCompensation(
                event.contractPlanId(), event.customerId(), event.planName(), reason));

        notificationSenderFactory.getSender(NotificationChannel.EMAIL)
                .send(event.customerId(), "Action needed: billing sync failed for your plan and requires manual review.");

        compensated.increment();
    }
}
