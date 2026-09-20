package com.example.meteringservice.dto;

import com.example.meteringservice.validation.NotInFuture;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * Inbound submission payload for POST /customers/{customerId}/meter-readings.
 * customerId is deliberately NOT a field here -- it comes only from the URL
 * path, the single source of truth for which customer a reading belongs to,
 * so a caller can never submit a reading body claiming a different customer
 * id than the one WorkspaceAccessGuard has already authorized against the
 * path.
 */
public record MeterReadingRequest(

        @NotBlank(message = "meterId is required")
        String meterId,

        @NotNull(message = "readingDate is required")
        @NotInFuture
        LocalDate readingDate,

        @NotNull(message = "kWhConsumed is required")
        @Positive(message = "kWhConsumed must be a positive value")
        BigDecimal kWhConsumed) {
}
