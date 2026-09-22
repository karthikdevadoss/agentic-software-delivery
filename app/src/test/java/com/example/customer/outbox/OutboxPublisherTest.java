package com.example.customer.outbox;

import com.example.customer.messaging.KafkaMessagingConfig;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Limit;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import tools.jackson.databind.json.JsonMapper;

import java.util.List;
import java.util.concurrent.CompletableFuture;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * BL-057: unit tests for the transactional-outbox publisher's real
 * decisions: publish + mark published, leave unpublished on broker failure
 * (retry next poll, never lose the event), and refuse an unmapped event type.
 * KafkaTemplate is mocked; the envelope actually sent is asserted.
 */
@ExtendWith(MockitoExtension.class)
class OutboxPublisherTest {

    @Mock
    private OutboxEventRepository outboxEventRepository;
    @Mock
    private KafkaTemplate<String, String> kafkaTemplate;

    private final JsonMapper jsonMapper = JsonMapper.builder().build();
    private final SimpleMeterRegistry meterRegistry = new SimpleMeterRegistry();
    private OutboxPublisher publisher;

    @BeforeEach
    void setUp() {
        publisher = new OutboxPublisher(outboxEventRepository, kafkaTemplate, jsonMapper, meterRegistry);
    }

    @Test
    void pendingEvent_isPublishedToTheMappedTopic_keyedByAggregateId_thenMarkedPublished() {
        OutboxEvent event = new OutboxEvent("ContractPlan", 77L, "ContractPlanEnrolled", "{\"contractPlanId\":77}");
        when(outboxEventRepository.findByPublishedAtIsNullOrderByCreatedAtAsc(any(Limit.class))).thenReturn(List.of(event));
        when(kafkaTemplate.send(anyString(), anyString(), anyString())).thenReturn(CompletableFuture.completedFuture((SendResult<String, String>) null));

        publisher.publishPendingEvents();

        ArgumentCaptor<String> body = ArgumentCaptor.forClass(String.class);
        verify(kafkaTemplate).send(eq(KafkaMessagingConfig.CONTRACT_PLAN_EVENTS_TOPIC), eq("77"), body.capture());
        assertThat(body.getValue()).contains("\"eventType\":\"ContractPlanEnrolled\"").contains(event.getEventId());
        assertThat(event.getPublishedAt()).isNotNull();
        verify(outboxEventRepository).save(event);
        assertThat(meterRegistry.get("outbox.events").tag("result", "published").counter().count()).isEqualTo(1.0);
    }

    @Test
    void brokerFailure_leavesTheEventUnpublished_forTheNextPoll() {
        OutboxEvent event = new OutboxEvent("Customer", 5L, "CustomerPreferenceUpdated", "{}");
        when(outboxEventRepository.findByPublishedAtIsNullOrderByCreatedAtAsc(any(Limit.class))).thenReturn(List.of(event));
        when(kafkaTemplate.send(anyString(), anyString(), anyString()))
                .thenReturn(CompletableFuture.failedFuture(new RuntimeException("broker unreachable")));

        publisher.publishPendingEvents();

        assertThat(event.getPublishedAt()).isNull();
        verify(outboxEventRepository, never()).save(any());
        assertThat(meterRegistry.get("outbox.events").tag("result", "publish-failed").counter().count()).isEqualTo(1.0);
    }

    @Test
    void unmappedEventType_isNeverSent_andCountedAsFailure() {
        OutboxEvent event = new OutboxEvent("Customer", 5L, "SomethingNobodyMapped", "{}");
        when(outboxEventRepository.findByPublishedAtIsNullOrderByCreatedAtAsc(any(Limit.class))).thenReturn(List.of(event));

        publisher.publishPendingEvents();

        verify(kafkaTemplate, never()).send(anyString(), anyString(), anyString());
        assertThat(event.getPublishedAt()).isNull();
        assertThat(meterRegistry.get("outbox.events").tag("result", "publish-failed").counter().count()).isEqualTo(1.0);
    }
}
