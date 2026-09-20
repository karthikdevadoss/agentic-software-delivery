package com.example.billingservice.event;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;

/** Kafka event payload for a new contract-plan enrollment -- the outbox_event.payload column stores this as JSON. */
public record ContractPlanEnrolledEvent(
        Long contractPlanId,
        Long customerId,
        String planName,
        BigDecimal ratePerKwh,
        LocalDate effectiveStartDate,
        Instant enrolledAt
) {
}
