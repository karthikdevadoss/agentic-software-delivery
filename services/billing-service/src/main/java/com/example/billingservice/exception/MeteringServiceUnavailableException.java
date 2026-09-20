package com.example.billingservice.exception;

/**
 * Thrown when MeteringUsageClient could not get a real answer from
 * metering-service -- distinct from a genuine zero-usage period (metering-
 * service always returns 200 with readingCount=0 for "no readings", never
 * 404; see MeterReadingService.getUsageSummary). This means billing-
 * service's own dependency is unreachable, not that usage was genuinely
 * zero. See GlobalExceptionHandler for the HTTP status mapping and why
 * (mirrors CustomerServiceUnavailableException's reasoning exactly).
 */
public class MeteringServiceUnavailableException extends RuntimeException {

    public MeteringServiceUnavailableException(String message) {
        super(message);
    }
}
