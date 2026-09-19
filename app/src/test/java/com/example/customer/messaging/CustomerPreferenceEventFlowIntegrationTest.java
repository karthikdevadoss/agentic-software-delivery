package com.example.customer.messaging;

import com.example.customer.dto.CustomerPreferenceUpdateRequest;
import com.example.customer.model.Customer;
import com.example.customer.model.NotificationChannel;
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

import java.time.Duration;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

/**
 * REAL end-to-end proof of the transactional outbox + Kafka flow, against
 * a real Kafka broker (Testcontainers, disabledWithoutDocker=true -- skips
 * on this dev machine, runs for real in CI, same pattern as
 * PostgresFlywayIntegrationTest / ContractPlanCacheIntegrationTest):
 * PUT preferences -> outbox row committed -> OutboxPublisher's real
 * scheduled poll actually publishes it -> CustomerPreferenceEventConsumer
 * actually receives and processes it -> a hand-crafted duplicate
 * redelivery is a genuine no-op -> a poison message lands on the real
 * dead-letter topic instead of blocking the partition.
 */
@Testcontainers(disabledWithoutDocker = true)
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class CustomerPreferenceEventFlowIntegrationTest {

    // REAL CI FAILURE, root-caused via the public Checks annotations API
    // (raw job logs need repo-admin auth, even on this public repo -- see
    // .github/workflows/ci.yml's failure-annotation step, added specifically
    // because of this investigation): the newer apache/kafka:3.9.0 image
    // (testcontainers-kafka's other officially documented option) exited
    // with code 1 during its own entrypoint script on GitHub's runner --
    // "Timed out waiting for log output" was a downstream symptom of the
    // container process dying, not a wait-pattern mismatch. Switched to
    // ConfluentKafkaContainer/confluentinc-cp-kafka, the far more widely
    // battle-tested combination for Testcontainers Kafka tests industry-wide.
    @Container
    static ConfluentKafkaContainer kafka = new ConfluentKafkaContainer(DockerImageName.parse("confluentinc/cp-kafka:7.7.0"));

    @DynamicPropertySource
    static void kafkaProperties(DynamicPropertyRegistry registry) {
        // app.kafka.enabled defaults to false (see application.properties'
        // real production-incident writeup) -- this test explicitly turns
        // the whole Kafka subsystem on against the real Testcontainers broker.
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
    void preferenceUpdate_isPublishedAndConsumed_endToEnd() {
        Customer created = restTemplate.postForObject(
                url("/customers"), new Customer("Kafka Flow Test", "kafka-flow@example.com"), Customer.class);

        restTemplate.put(url("/customers/" + created.getId() + "/preferences"),
                new CustomerPreferenceUpdateRequest(true, NotificationChannel.SMS));

        // 1. Outbox row committed by the same transaction as the preference write.
        await().atMost(Duration.ofSeconds(2)).untilAsserted(() ->
                assertThat(outboxEventRepository.findAll()).anyMatch(e -> e.getAggregateId().equals(created.getId())));

        // 2. OutboxPublisher's real @Scheduled poll actually publishes it, and
        //    CustomerPreferenceEventConsumer actually consumes + records it.
        // REAL CI EVIDENCE (root-caused via the failure-annotation CI step):
        // 10s was too tight on a real, previously-unwarmed Kafka
        // producer/consumer pipeline -- initial broker metadata fetch plus
        // a genuine consumer-group join/rebalance routinely takes several
        // seconds on its own, on top of the scheduled poll's own interval,
        // especially on a CI runner slower than a dev laptop. 40s gives
        // real headroom without masking an actual regression (this test
        // still fails, just later, if something is genuinely broken).
        await().atMost(Duration.ofSeconds(40)).untilAsserted(() -> {
            var event = outboxEventRepository.findAll().stream()
                    .filter(e -> e.getAggregateId().equals(created.getId())).findFirst().orElseThrow();
            assertThat(event.getPublishedAt()).isNotNull();
            assertThat(processedEventRepository.existsByConsumerNameAndEventId(
                    CustomerPreferenceEventConsumer.CONSUMER_NAME, event.getEventId())).isTrue();
        });
    }

    @Test
    void duplicateDelivery_ofAnAlreadyProcessedEvent_isANoOp() throws Exception {
        Customer created = restTemplate.postForObject(
                url("/customers"), new Customer("Kafka Dup Test", "kafka-dup@example.com"), Customer.class);
        restTemplate.put(url("/customers/" + created.getId() + "/preferences"),
                new CustomerPreferenceUpdateRequest(true, NotificationChannel.SMS));

        // Same generous window as the end-to-end test: JUnit does not
        // guarantee method execution order, so this test cannot assume the
        // Kafka pipeline was already warmed up by another test in the class.
        var event = await().atMost(Duration.ofSeconds(40)).until(() ->
                outboxEventRepository.findAll().stream()
                        .filter(e -> e.getAggregateId().equals(created.getId()) && e.getPublishedAt() != null)
                        .findFirst().orElse(null),
                java.util.Objects::nonNull);

        long processedCountBefore = processedEventRepository.count();

        // Hand-craft and resend the EXACT same envelope -- simulating a
        // real redelivery (broker retry / consumer rebalance), not a new event.
        OutboxEventEnvelope envelope = new OutboxEventEnvelope(
                event.getEventId(), event.getAggregateType(), event.getAggregateId(), event.getEventType(), event.getPayload());
        kafkaTemplate.send(KafkaMessagingConfig.CUSTOMER_PREFERENCE_EVENTS_TOPIC,
                        String.valueOf(event.getAggregateId()), jsonMapper.writeValueAsString(envelope))
                .get(5, TimeUnit.SECONDS);

        // Give the duplicate a real chance to be (mis)processed, then assert
        // no new processed_event row was created for it.
        Thread.sleep(2000);
        assertThat(processedEventRepository.count()).isEqualTo(processedCountBefore);
    }

    @Test
    void malformedMessage_isRoutedToTheDeadLetterTopic_notLostOrLoopedForever() throws Exception {
        kafkaTemplate.send(KafkaMessagingConfig.CUSTOMER_PREFERENCE_EVENTS_TOPIC, "poison-key", "not valid json at all")
                .get(5, TimeUnit.SECONDS);

        try (var consumer = new org.apache.kafka.clients.consumer.KafkaConsumer<String, String>(java.util.Map.of(
                org.apache.kafka.clients.consumer.ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, kafka.getBootstrapServers(),
                org.apache.kafka.clients.consumer.ConsumerConfig.GROUP_ID_CONFIG, "dlt-test-reader-" + System.nanoTime(),
                org.apache.kafka.clients.consumer.ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest",
                org.apache.kafka.clients.consumer.ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, "org.apache.kafka.common.serialization.StringDeserializer",
                org.apache.kafka.clients.consumer.ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, "org.apache.kafka.common.serialization.StringDeserializer"))) {
            consumer.subscribe(java.util.List.of(KafkaMessagingConfig.CUSTOMER_PREFERENCE_EVENTS_DLT));

            // Same real-CI-evidenced reasoning as the end-to-end test above:
            // a brand-new consumer group here always pays a real, one-time
            // group-join/rebalance cost, on top of the error handler's own
            // 2x200ms retry before it routes to the DLT at all.
            var records = await().atMost(Duration.ofSeconds(30)).until(
                    () -> consumer.poll(Duration.ofMillis(500)),
                    r -> r.count() > 0);

            assertThat(records.count()).isGreaterThan(0);
        }
    }
}
