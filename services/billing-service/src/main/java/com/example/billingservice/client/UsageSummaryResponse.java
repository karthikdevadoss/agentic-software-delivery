package com.example.billingservice.client;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * BL-015: billing-service's own local copy of metering-service's real
 * response shape (com.example.meteringservice.dto.UsageSummaryResponse),
 * deserialized from its real JSON response -- no shared jar between
 * services, per docs/MICROSERVICES_ARCHITECTURE.md's "Data" section (each
 * service owns its own model; a consumer keeps its own local copy of
 * whatever shape it actually needs from another service's API, never a
 * compile-time dependency on that service's internals).
 */
public record UsageSummaryResponse(
        Long customerId,
        LocalDate periodStart,
        LocalDate periodEnd,
        BigDecimal totalKwhConsumed,
        long readingCount) {
}
