package com.example.billingservice.dto;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * BL-015: the actual, demonstrable integration point -- combines a
 * customer's real usage (from metering-service) with their real active
 * plan's rate (owned here) into one estimated cost figure, closing
 * docs/MICROSERVICES_ARCHITECTURE.md's "Metering data feeding into real
 * billing calculations" deferred item.
 */
public record EstimatedUsageCostResponse(
        Long customerId,
        LocalDate periodStart,
        LocalDate periodEnd,
        BigDecimal totalKwhConsumed,
        long readingCount,
        String planName,
        BigDecimal ratePerKwh,
        BigDecimal estimatedCost) {
}
