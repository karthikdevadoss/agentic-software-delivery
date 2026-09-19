package com.example.customer.messaging;

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
 * Topics and consumer-side failure handling for the outbox-published event
 * flows. A malformed/poison message is retried twice (200ms apart) then
 * routed to the ".DLT" dead-letter topic rather than blocking the
 * partition forever or being silently dropped -- "recovery strategy" is a
 * real, explicit decision here, not an omission.
 *
 * Two independent event families are wired here: CustomerPreferenceUpdated
 * (one topic, one consumer group) and ContractPlanEnrolled (one topic, TWO
 * independent consumer groups -- Notification and BillingSync -- a real
 * fan-out: Kafka delivers each consumer group its own full copy of the
 * topic, so both process every event independently). EVENT_TYPE_TO_TOPIC
 * is what lets OutboxPublisher stay a single generic relay instead of
 * growing a topic-specific branch for every new event type added.
 *
 * Entirely conditional on app.kafka.enabled -- see application.properties'
 * EVENTING section for the real production incident that made this
 * necessary: with no broker reachable, these beans' background reconnect
 * activity flooded production logs badly enough that Railway started
 * dropping messages. Nothing here even attempts to connect until Kafka
 * is actually provisioned and this flag is explicitly turned on.
 */
@Configuration
@ConditionalOnProperty(name = "app.kafka.enabled", havingValue = "true")
public class KafkaMessagingConfig {

    public static final String CUSTOMER_PREFERENCE_EVENTS_TOPIC = "customer-preference-events";
    public static final String CUSTOMER_PREFERENCE_EVENTS_DLT = CUSTOMER_PREFERENCE_EVENTS_TOPIC + ".DLT";
    public static final String CONSUMER_GROUP_ID = "customer-app-preference-consumer";

    public static final String CONTRACT_PLAN_EVENTS_TOPIC = "contract-plan-events";
    public static final String CONTRACT_PLAN_EVENTS_DLT = CONTRACT_PLAN_EVENTS_TOPIC + ".DLT";
    public static final String CONTRACT_PLAN_NOTIFICATION_GROUP_ID = "contract-plan-notification-consumer";
    public static final String CONTRACT_PLAN_BILLING_SYNC_GROUP_ID = "contract-plan-billing-sync-consumer";

    /** eventType (OutboxEvent.eventType) -> the topic it publishes to. The
     * single source of truth OutboxPublisher looks up instead of hardcoding
     * one topic -- adding a third event type means adding one entry here. */
    public static final Map<String, String> EVENT_TYPE_TO_TOPIC = Map.of(
            "CustomerPreferenceUpdated", CUSTOMER_PREFERENCE_EVENTS_TOPIC,
            "ContractPlanEnrolled", CONTRACT_PLAN_EVENTS_TOPIC
    );

    /**
     * Boot's own auto-configured KafkaTemplate bean is generically typed
     * KafkaTemplate&lt;Object, Object&gt; -- it does not satisfy an
     * injection point asking for KafkaTemplate&lt;String, String&gt; by
     * Spring's generics-aware autowiring, even with matching serializer
     * properties configured. Declaring this explicitly-typed bean (real
     * error encountered and fixed while wiring this up: "required a bean
     * of type KafkaTemplate that could not be found") is the correct fix,
     * not a workaround.
     */
    @Bean
    public ProducerFactory<String, String> producerFactory(
            @Value("${spring.kafka.bootstrap-servers}") String bootstrapServers) {
        Map<String, Object> configProps = new HashMap<>();
        configProps.put(org.apache.kafka.clients.producer.ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        configProps.put(org.apache.kafka.clients.producer.ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, org.apache.kafka.common.serialization.StringSerializer.class);
        configProps.put(org.apache.kafka.clients.producer.ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, org.apache.kafka.common.serialization.StringSerializer.class);
        // Same real production finding as application.properties's consumer/admin
        // backoff settings (this bean bypasses those Boot-bound properties by
        // design, so it needs its own copy): without a reachable broker, the
        // default ~50ms backoff meant OutboxPublisher's producer was retrying
        // far more often than useful, flooding production logs.
        configProps.put(org.apache.kafka.clients.producer.ProducerConfig.RECONNECT_BACKOFF_MS_CONFIG, 10000);
        configProps.put(org.apache.kafka.clients.producer.ProducerConfig.RECONNECT_BACKOFF_MAX_MS_CONFIG, 60000);
        return new DefaultKafkaProducerFactory<>(configProps);
    }

    @Bean
    public KafkaTemplate<String, String> kafkaTemplate(ProducerFactory<String, String> producerFactory) {
        return new KafkaTemplate<>(producerFactory);
    }

    @Bean
    public NewTopic customerPreferenceEventsTopic() {
        return TopicBuilder.name(CUSTOMER_PREFERENCE_EVENTS_TOPIC).partitions(3).replicas(1).build();
    }

    @Bean
    public NewTopic customerPreferenceEventsDeadLetterTopic() {
        return TopicBuilder.name(CUSTOMER_PREFERENCE_EVENTS_DLT).partitions(1).replicas(1).build();
    }

    @Bean
    public NewTopic contractPlanEventsTopic() {
        return TopicBuilder.name(CONTRACT_PLAN_EVENTS_TOPIC).partitions(3).replicas(1).build();
    }

    @Bean
    public NewTopic contractPlanEventsDeadLetterTopic() {
        return TopicBuilder.name(CONTRACT_PLAN_EVENTS_DLT).partitions(1).replicas(1).build();
    }

    /** source topic -> its own dead-letter topic, so one shared error handler
     * (below) can serve every listener without each one needing its own
     * DefaultErrorHandler bean. */
    private static final Map<String, String> TOPIC_TO_DLT = Map.of(
            CUSTOMER_PREFERENCE_EVENTS_TOPIC, CUSTOMER_PREFERENCE_EVENTS_DLT,
            CONTRACT_PLAN_EVENTS_TOPIC, CONTRACT_PLAN_EVENTS_DLT
    );

    @Bean
    public DefaultErrorHandler kafkaErrorHandler(KafkaTemplate<String, String> kafkaTemplate) {
        DeadLetterPublishingRecoverer recoverer = new DeadLetterPublishingRecoverer(kafkaTemplate,
                (record, exception) -> new TopicPartition(
                        TOPIC_TO_DLT.getOrDefault(record.topic(), record.topic() + ".DLT"), record.partition()));
        FixedBackOff backOff = new FixedBackOff(200L, 2L);
        return new DefaultErrorHandler(recoverer, backOff);
    }
}
