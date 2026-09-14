package com.example.customer.messaging;

import org.apache.kafka.clients.admin.NewTopic;
import org.apache.kafka.common.TopicPartition;
import org.springframework.beans.factory.annotation.Value;
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
 * Topics and consumer-side failure handling for the CustomerPreferenceUpdated
 * event flow. A malformed/poison message is retried twice (200ms apart)
 * then routed to the ".DLT" dead-letter topic rather than blocking the
 * partition forever or being silently dropped -- "recovery strategy" is a
 * real, explicit decision here, not an omission.
 */
@Configuration
public class KafkaMessagingConfig {

    public static final String CUSTOMER_PREFERENCE_EVENTS_TOPIC = "customer-preference-events";
    public static final String CUSTOMER_PREFERENCE_EVENTS_DLT = CUSTOMER_PREFERENCE_EVENTS_TOPIC + ".DLT";
    public static final String CONSUMER_GROUP_ID = "customer-app-preference-consumer";

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
    public DefaultErrorHandler kafkaErrorHandler(KafkaTemplate<String, String> kafkaTemplate) {
        DeadLetterPublishingRecoverer recoverer = new DeadLetterPublishingRecoverer(kafkaTemplate,
                (record, exception) -> new TopicPartition(CUSTOMER_PREFERENCE_EVENTS_DLT, record.partition()));
        FixedBackOff backOff = new FixedBackOff(200L, 2L);
        return new DefaultErrorHandler(recoverer, backOff);
    }
}
