package com.example.billingservice.messaging;

import org.apache.kafka.clients.admin.NewTopic;
import org.apache.kafka.common.TopicPartition;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.core.ProducerFactory;
import org.springframework.kafka.config.TopicBuilder;
import org.springframework.kafka.listener.DeadLetterPublishingRecoverer;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.util.backoff.FixedBackOff;

import java.util.HashMap;
import java.util.Map;

/**
 * Topic + consumer-side failure handling for this service's one outbox-
 * published event flow (ContractPlanEnrolled). SIMPLIFIED from the
 * monolith's version (see app/'s KafkaMessagingConfig): that class carried
 * an eventType-&gt;topic registry (EVENT_TYPE_TO_TOPIC) because it relayed
 * TWO event types through one shared OutboxPublisher. billing-service only
 * ever publishes one event type, so OutboxPublisher here hardcodes the
 * single topic directly -- porting the registry generalization would be
 * over-engineering for a service that will never need the second branch.
 *
 * Entirely conditional on app.kafka.enabled -- see application.properties
 * and app/'s own KafkaMessagingConfig Javadoc for the real production
 * incident (unreachable-broker reconnect log flooding) this gate exists
 * to prevent. Nothing here even attempts to connect until Kafka is
 * actually provisioned and this flag is explicitly turned on.
 */
@Configuration
@ConditionalOnProperty(name = "app.kafka.enabled", havingValue = "true")
public class KafkaMessagingConfig {

    public static final String CONTRACT_PLAN_EVENTS_TOPIC = "contract-plan-events";
    public static final String CONTRACT_PLAN_EVENTS_DLT = CONTRACT_PLAN_EVENTS_TOPIC + ".DLT";

    /**
     * Boot's own auto-configured KafkaTemplate bean is generically typed
     * KafkaTemplate&lt;Object, Object&gt; -- it does not satisfy an
     * injection point asking for KafkaTemplate&lt;String, String&gt; by
     * Spring's generics-aware autowiring (real error hit and fixed while
     * porting this, same as app/'s original discovery: "required a bean
     * of type KafkaTemplate that could not be found"). Declaring this
     * explicitly-typed bean is the correct fix, not a workaround.
     */
    @Bean
    public ProducerFactory<String, String> producerFactory(
            @Value("${spring.kafka.bootstrap-servers}") String bootstrapServers) {
        Map<String, Object> configProps = new HashMap<>();
        configProps.put(org.apache.kafka.clients.producer.ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        configProps.put(org.apache.kafka.clients.producer.ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, org.apache.kafka.common.serialization.StringSerializer.class);
        configProps.put(org.apache.kafka.clients.producer.ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, org.apache.kafka.common.serialization.StringSerializer.class);
        // Same real production finding as app/'s KafkaMessagingConfig: without
        // a reachable broker, the default ~50ms backoff meant this producer
        // would retry far more often than useful, flooding production logs.
        configProps.put(org.apache.kafka.clients.producer.ProducerConfig.RECONNECT_BACKOFF_MS_CONFIG, 10000);
        configProps.put(org.apache.kafka.clients.producer.ProducerConfig.RECONNECT_BACKOFF_MAX_MS_CONFIG, 60000);
        return new DefaultKafkaProducerFactory<>(configProps);
    }

    @Bean
    public KafkaTemplate<String, String> kafkaTemplate(ProducerFactory<String, String> producerFactory) {
        return new KafkaTemplate<>(producerFactory);
    }

    @Bean
    public NewTopic contractPlanEventsTopic() {
        return TopicBuilder.name(CONTRACT_PLAN_EVENTS_TOPIC).partitions(3).replicas(1).build();
    }

    @Bean
    public NewTopic contractPlanEventsDeadLetterTopic() {
        return TopicBuilder.name(CONTRACT_PLAN_EVENTS_DLT).partitions(1).replicas(1).build();
    }

    /** billing-service is a producer only (no @KafkaListener here -- the
     * consumers of ContractPlanEnrolled live in notification-service and
     * customer-service's billing-sync, ported separately), but a shared
     * DefaultErrorHandler bean is kept for consistency and in case a
     * future consumer is added here. */
    @Bean
    public DefaultErrorHandler kafkaErrorHandler(KafkaTemplate<String, String> kafkaTemplate) {
        DeadLetterPublishingRecoverer recoverer = new DeadLetterPublishingRecoverer(kafkaTemplate,
                (record, exception) -> new TopicPartition(CONTRACT_PLAN_EVENTS_DLT, record.partition()));
        FixedBackOff backOff = new FixedBackOff(200L, 2L);
        return new DefaultErrorHandler(recoverer, backOff);
    }
}
