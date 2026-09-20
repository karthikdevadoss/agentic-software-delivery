package com.example.notificationservice.event;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;

/**
 * Kafka event payload for a new contract-plan enrollment, published by
 * billing-service via its own transactional outbox. Ported as-is (field
 * order and types must match the producer's serialized JSON shape) from
 * app/src/main/java/com/example/customer/event/ContractPlanEnrolledEvent.java.
 */
public record ContractPlanEnrolledEvent(
        Long contractPlanId,
        Long customerId,
        String planName,
        BigDecimal ratePerKwh,
        LocalDate effectiveStartDate,
        Instant enrolledAt
) {
}
