package com.example.customer.messaging;

import com.example.customer.dto.ContractPlanEnrollRequest;
import com.example.customer.model.Customer;
import com.example.customer.outbox.OutboxEventRepository;
import com.example.customer.outbox.ProcessedEventRepository;
import com.example.customer.security.DemoJwtIssuer;
import com.example.customer.testsupport.AuthTestSupport;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.kafka.ConfluentKafkaContainer;
import org.testcontainers.utility.DockerImageName;
import tools.jackson.databind.json.JsonMapper;

import java.math.BigDecimal;
import java.time.Duration;
import java.time.LocalDate;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

/**
 * REAL end-to-end proof of the ContractPlanEnrolled FAN-OUT: one outbox
 * event, published once, independently consumed by TWO separate consumer
 * groups (Notification and BillingSync) -- each leaves its own,
 * independently-observable trace (a ProcessedEvent row scoped to its own
 * consumer name, and for BillingSync a real BillingSyncRecord row). This is
 * the test that would have caught the real global-idempotency bug this
 * session found and fixed (see ProcessedEvent's Javadoc and Triage
 * Scenario D): before the fix, only the faster consumer's row would exist.
 *
 * Same Testcontainers pattern as CustomerPreferenceEventFlowIntegrationTest
 * (disabledWithoutDocker=true): skips on this Docker-less dev machine,
 * runs for real in CI.
 */
@Testcontainers(disabledWithoutDocker = true)
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ContractPlanEnrollmentEventFlowIntegrationTest {

    @Container
    static ConfluentKafkaContainer kafka = new ConfluentKafkaContainer(DockerImageName.parse("confluentinc/cp-kafka:7.7.0"));

    @DynamicPropertySource
    static void kafkaProperties(DynamicPropertyRegistry registry) {
        registry.add("app.kafka.enabled", () -> "true");
        registry.add("spring.kafka.bootstrap-servers", kafka::getBootstrapServers);
    }

    @LocalServerPort
    private int port;

    @Autowired
    private DemoJwtIssuer demoJwtIssuer;
    @Autowired
    private OutboxEventRepository outboxEventRepository;
    @Autowired
    private ProcessedEventRepository processedEventRepository;
    @Autowired
    private BillingSyncRecordRepository billingSyncRecordRepository;
    @Autowired
    private KafkaTemplate<String, String> kafkaTemplate;
    @Autowired
    private JsonMapper jsonMapper;

    private org.springframework.web.client.RestTemplate restTemplate;

    @BeforeEach
    void setUp() {
        restTemplate = AuthTestSupport.authenticatedRestTemplate(demoJwtIssuer);
    }

    private String url(String path) {
        return "http://localhost:" + port + path;
    }

    @Test
    void enrollment_isPublishedOnce_andConsumedIndependentlyByBothFanOutConsumers() {
        Customer created = restTemplate.postForObject(
                url("/customers"), new Customer("Fan-Out Test", "fanout-test@example.com"), Customer.class);

        restTemplate.postForEntity(url("/customers/" + created.getId() + "/plan"),
                new ContractPlanEnrollRequest("Solar Saver 12mo", new BigDecimal("0.18"), LocalDate.now()),
                com.example.customer.dto.ContractPlanResponse.class);

        // 1. Outbox row committed by the same transaction as the enrollment write.
        var event = await().atMost(Duration.ofSeconds(2)).until(() ->
                outboxEventRepository.findAll().stream()
                        .filter(e -> e.getEventType().equals("ContractPlanEnrolled") && e.getAggregateType().equals("ContractPlan"))
                        .filter(e -> e.getPayload().contains("Solar Saver 12mo"))
                        .findFirst().orElse(null),
                java.util.Objects::nonNull);

        // 2. Real fan-out proof: BOTH independent consumer groups process the
        //    SAME event, each recording its OWN processed_event row (composite
        //    key on consumer_name -- the exact bug this test would have caught
        //    against the pre-fix global-by-eventId design).
        await().atMost(Duration.ofSeconds(40)).untilAsserted(() -> {
            var republished = outboxEventRepository.findAll().stream()
                    .filter(e -> e.getEventId().equals(event.getEventId())).findFirst().orElseThrow();
            assertThat(republished.getPublishedAt()).isNotNull();
            assertThat(processedEventRepository.existsByConsumerNameAndEventId("contract-plan-notification", event.getEventId())).isTrue();
            assertThat(processedEventRepository.existsByConsumerNameAndEventId("contract-plan-billing-sync", event.getEventId())).isTrue();
        });

        // 3. BillingSync's own real, independently-observable side effect.
        await().atMost(Duration.ofSeconds(5)).untilAsserted(() ->
                assertThat(billingSyncRecordRepository.findAll())
                        .anyMatch(r -> r.getPlanName().equals("Solar Saver 12mo") && r.getCustomerId().equals(created.getId())));
    }

    @Test
    void duplicateDelivery_isANoOp_independentlyForEachFanOutConsumer() throws Exception {
        Customer created = restTemplate.postForObject(
                url("/customers"), new Customer("Fan-Out Dup Test", "fanout-dup@example.com"), Customer.class);
        restTemplate.postForEntity(url("/customers/" + created.getId() + "/plan"),
                new ContractPlanEnrollRequest("Basic 6mo", new BigDecimal("0.20"), LocalDate.now()),
                com.example.customer.dto.ContractPlanResponse.class);

        var event = await().atMost(Duration.ofSeconds(40)).until(() ->
                outboxEventRepository.findAll().stream()
                        .filter(e -> e.getEventType().equals("ContractPlanEnrolled") && e.getPayload().contains("Basic 6mo") && e.getPublishedAt() != null)
                        .findFirst().orElse(null),
                java.util.Objects::nonNull);

        long processedCountBefore = processedEventRepository.count();
        long billingRecordsBefore = billingSyncRecordRepository.count();

        OutboxEventEnvelope envelope = new OutboxEventEnvelope(
                event.getEventId(), event.getAggregateType(), event.getAggregateId(), event.getEventType(), event.getPayload());
        kafkaTemplate.send(KafkaMessagingConfig.CONTRACT_PLAN_EVENTS_TOPIC,
                        String.valueOf(event.getAggregateId()), jsonMapper.writeValueAsString(envelope))
                .get(5, TimeUnit.SECONDS);

        Thread.sleep(2000);
        assertThat(processedEventRepository.count()).isEqualTo(processedCountBefore);
        assertThat(billingSyncRecordRepository.count()).isEqualTo(billingRecordsBefore);
    }

    @Test
    void malformedMessage_isRoutedToItsOwnDeadLetterTopic() throws Exception {
        kafkaTemplate.send(KafkaMessagingConfig.CONTRACT_PLAN_EVENTS_TOPIC, "poison-key", "not valid json at all")
                .get(5, TimeUnit.SECONDS);

        try (var consumer = new org.apache.kafka.clients.consumer.KafkaConsumer<String, String>(java.util.Map.of(
                org.apache.kafka.clients.consumer.ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, kafka.getBootstrapServers(),
                org.apache.kafka.clients.consumer.ConsumerConfig.GROUP_ID_CONFIG, "contract-plan-dlt-test-reader-" + System.nanoTime(),
                org.apache.kafka.clients.consumer.ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest",
                org.apache.kafka.clients.consumer.ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, "org.apache.kafka.common.serialization.StringDeserializer",
                org.apache.kafka.clients.consumer.ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, "org.apache.kafka.common.serialization.StringDeserializer"))) {
            consumer.subscribe(java.util.List.of(KafkaMessagingConfig.CONTRACT_PLAN_EVENTS_DLT));

            var records = await().atMost(Duration.ofSeconds(30)).until(
                    () -> consumer.poll(Duration.ofMillis(500)),
                    r -> r.count() > 0);

            assertThat(records.count()).isGreaterThan(0);
        }
    }
}
