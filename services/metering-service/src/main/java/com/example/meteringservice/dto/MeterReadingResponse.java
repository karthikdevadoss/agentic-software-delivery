package com.example.meteringservice.dto;

import com.example.meteringservice.model.MeterReading;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;

public record MeterReadingResponse(
        Long id,
        Long customerId,
        String meterId,
        LocalDate readingDate,
        BigDecimal kWhConsumed,
        Instant submittedAt) {

    public static MeterReadingResponse from(MeterReading reading) {
        return new MeterReadingResponse(
                reading.getId(),
                reading.getCustomerId(),
                reading.getMeterId(),
                reading.getReadingDate(),
                reading.getKWhConsumed(),
                reading.getSubmittedAt());
    }
}
