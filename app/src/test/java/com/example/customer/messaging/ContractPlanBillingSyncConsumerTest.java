package com.example.customer.messaging;

import com.example.customer.event.ContractPlanEnrolledEvent;
import com.example.customer.model.NotificationChannel;
import com.example.customer.notification.NotificationSender;
import com.example.customer.notification.NotificationSenderFactory;
import com.example.customer.outbox.ProcessedEvent;
import com.example.customer.outbox.ProcessedEventRepository;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.BeforeEach;
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
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * BL-057: pure unit tests for the billing-sync consumer's real decision
 * logic (idempotent duplicate skip, normal sync record, compensation path)
 * -- previously exercised only by the Kafka Testcontainers flow test, which
 * cannot run on a machine without Docker, leaving these 33 lines unmeasured
 * locally. No Spring context, no Kafka: the consumer's onMessage is called
 * exactly as the listener container would call it.
 */
@ExtendWith(MockitoExtension.class)
class ContractPlanBillingSyncConsumerTest {

    @Mock
    private ProcessedEventRepository processedEventRepository;
    @Mock
    private BillingSyncRecordRepository billingSyncRecordRepository;
    @Mock
    private BillingSyncCompensationRepository billingSyncCompensationRepository;
    @Mock
    private NotificationSenderFactory notificationSenderFactory;
    @Mock
    private NotificationSender emailSender;

    private final JsonMapper jsonMapper = JsonMapper.builder().build();
    private final SimpleMeterRegistry meterRegistry = new SimpleMeterRegistry();
    private ContractPlanBillingSyncConsumer consumer;

    @BeforeEach
    void setUp() {
        consumer = new ContractPlanBillingSyncConsumer(processedEventRepository, billingSyncRecordRepository,
                billingSyncCompensationRepository, notificationSenderFactory, jsonMapper, meterRegistry);
    }

    private String envelope(String eventId, String planName) {
        ContractPlanEnrolledEvent event = new ContractPlanEnrolledEvent(
                77L, 5L, planName, new BigDecimal("0.1825"), LocalDate.of(2026, 9, 1), Instant.parse("2026-09-01T10:00:00Z"));
        OutboxEventEnvelope env = new OutboxEventEnvelope(eventId, "ContractPlan", 77L, "ContractPlanEnrolled",
                jsonMapper.writeValueAsString(event));
        return jsonMapper.writeValueAsString(env);
    }

    @Test
    void newEvent_writesBillingSyncRecord_andMarksEventProcessed() {
        when(processedEventRepository.existsByConsumerNameAndEventId(ContractPlanBillingSyncConsumer.CONSUMER_NAME, "evt-1"))
                .thenReturn(false);

        consumer.onMessage(envelope("evt-1", "Residential-Fixed-12"));

        ArgumentCaptor<BillingSyncRecord> record = ArgumentCaptor.forClass(BillingSyncRecord.class);
        verify(billingSyncRecordRepository).save(record.capture());
        assertThat(record.getValue().getContractPlanId()).isEqualTo(77L);
        assertThat(record.getValue().getCustomerId()).isEqualTo(5L);
        assertThat(record.getValue().getPlanName()).isEqualTo("Residential-Fixed-12");
        assertThat(record.getValue().getRatePerKwh()).isEqualByComparingTo("0.1825");
        assertThat(record.getValue().getSyncedAt()).isNotNull();

        ArgumentCaptor<ProcessedEvent> processed = ArgumentCaptor.forClass(ProcessedEvent.class);
        verify(processedEventRepository).save(processed.capture());
        assertThat(processed.getValue().getConsumerName()).isEqualTo(ContractPlanBillingSyncConsumer.CONSUMER_NAME);
        assertThat(processed.getValue().getEventId()).isEqualTo("evt-1");
        verify(billingSyncCompensationRepository, never()).save(any());
        assertThat(meterRegistry.get("contract_plan_events.consumed").tag("result", "processed").counter().count()).isEqualTo(1.0);
    }

    @Test
    void duplicateDelivery_isSkippedIdempotently_withoutTouchingBillingTables() {
        when(processedEventRepository.existsByConsumerNameAndEventId(ContractPlanBillingSyncConsumer.CONSUMER_NAME, "evt-dup"))
                .thenReturn(true);

        consumer.onMessage(envelope("evt-dup", "Residential-Fixed-12"));

        verify(billingSyncRecordRepository, never()).save(any());
        verify(billingSyncCompensationRepository, never()).save(any());
        verify(processedEventRepository, never()).save(any());
        assertThat(meterRegistry.get("contract_plan_events.consumed").tag("result", "duplicate-skipped").counter().count()).isEqualTo(1.0);
    }

    @Test
    void permanentBillingRejection_isCompensated_notRetried_andCustomerIsToldByEmail() {
        when(processedEventRepository.existsByConsumerNameAndEventId(anyString(), anyString())).thenReturn(false);
        when(notificationSenderFactory.getSender(NotificationChannel.EMAIL)).thenReturn(emailSender);

        consumer.onMessage(envelope("evt-fail", ContractPlanBillingSyncConsumer.SIMULATED_FAILURE_PLAN_NAME_PREFIX + "-Plan"));

        ArgumentCaptor<BillingSyncCompensation> compensation = ArgumentCaptor.forClass(BillingSyncCompensation.class);
        verify(billingSyncCompensationRepository).save(compensation.capture());
        assertThat(compensation.getValue().getContractPlanId()).isEqualTo(77L);
        assertThat(compensation.getValue().getReason()).contains("Simulated permanent billing-system rejection");
        assertThat(compensation.getValue().getCompensatedAt()).isNotNull();
        verify(emailSender).send(anyLong(), anyString());
        verify(billingSyncRecordRepository, never()).save(any());
        // Compensation still marks the event processed: a redelivery must not compensate twice.
        verify(processedEventRepository).save(any(ProcessedEvent.class));
        assertThat(meterRegistry.get("contract_plan_events.consumed").tag("result", "compensated").counter().count()).isEqualTo(1.0);
    }
}
