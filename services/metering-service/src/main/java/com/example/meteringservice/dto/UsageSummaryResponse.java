package com.example.meteringservice.dto;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * readingCount travels alongside totalKwhConsumed explicitly so a caller
 * never has to guess whether a zero total means "genuinely zero readings
 * in this period" versus "readings exist but happened to sum to zero." In
 * practice the latter can never actually occur -- every persisted
 * MeterReading passed MeterReadingRequest's @Positive validation, so each
 * one contributes a strictly-positive amount to the sum -- but this
 * response is deliberately self-explanatory on its own rather than
 * silently relying on that invariant: readingCount == 0 is the one and
 * only honest way to read "no data for this period," never an ambiguous
 * bare zero.
 */
public record UsageSummaryResponse(
        Long customerId,
        LocalDate periodStart,
        LocalDate periodEnd,
        BigDecimal totalKwhConsumed,
        long readingCount) {
}
