package com.example.notificationservice.messaging;

/**
 * Topic and consumer-group naming for the ContractPlanEnrolled flow this
 * service consumes. CONSUMER-SIDE ONLY: unlike the monolith's
 * KafkaMessagingConfig (app/src/main/java/com/example/customer/messaging/KafkaMessagingConfig.java),
 * this service does not own topic creation (billing-service -- the
 * producer -- does, via its own NewTopic beans) and never produces to
 * Kafka itself, so no ProducerFactory/KafkaTemplate/NewTopic/
 * DefaultErrorHandler beans are declared here.
 *
 * Spring Boot's Kafka autoconfiguration (spring-boot-starter-kafka, wired
 * from spring.kafka.consumer.* / spring.kafka.bootstrap-servers in
 * application.properties) supplies the ConsumerFactory and
 * KafkaListenerContainerFactory beans @KafkaListener needs -- no manual
 * consumer factory bean is required for the plain at-least-once consume
 * path this service uses (see ContractPlanEventConsumer's own
 * idempotency handling instead of relying on a DLT/retry topology here).
 *
 * Topic/group-id string values chosen to match what billing-service's own
 * KafkaMessagingConfig actually publishes to (contract-plan-events) and a
 * distinct consumer-group id so this service gets its own full,
 * independent copy of every partition per Kafka's consumer-group
 * semantics -- these are configuration strings coordinated across
 * services, not a shared Java class.
 */
public final class KafkaMessagingConfig {

    public static final String CONTRACT_PLAN_EVENTS_TOPIC = "contract-plan-events";
    public static final String CONTRACT_PLAN_NOTIFICATION_GROUP_ID = "notification-service-consumer";

    private KafkaMessagingConfig() {
    }
}
