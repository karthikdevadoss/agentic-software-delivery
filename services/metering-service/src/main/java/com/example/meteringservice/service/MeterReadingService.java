package com.example.meteringservice.service;

import com.example.meteringservice.dto.MeterReadingRequest;
import com.example.meteringservice.dto.UsageSummaryResponse;
import com.example.meteringservice.model.MeterReading;
import com.example.meteringservice.repository.MeterReadingRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

/**
 * Real, new business logic for the metering domain -- this is the one
 * service in the decomposition with no monolith equivalent to port, so
 * every decision below is made fresh, not adapted.
 */
@Service
public class MeterReadingService {

    private final MeterReadingRepository repository;

    public MeterReadingService(MeterReadingRepository repository) {
        this.repository = repository;
    }

    /** Persists a validated reading for the given customer. Validation of
     * the request body itself (non-blank meterId, positive kWh, non-future
     * date) already happened at the controller boundary via Bean
     * Validation -- this method's job is purely persistence, not
     * re-validating what @Valid already guaranteed. */
    @Transactional
    public MeterReading submitReading(Long customerId, MeterReadingRequest request) {
        MeterReading reading = new MeterReading(
                customerId, request.meterId(), request.readingDate(), request.kWhConsumed());
        return repository.save(reading);
    }

    /** Full reading history for a customer, most recent first. An empty
     * result is a normal, valid outcome (a customer with no readings yet)
     * -- never treated as a not-found error, since "no meter readings
     * exist yet" is not the same failure class as "this customer doesn't
     * exist" (which this service, owning no Customer data, cannot even
     * determine -- see docs/MICROSERVICES_ARCHITECTURE.md). */
    @Transactional(readOnly = true)
    public List<MeterReading> getHistory(Long customerId) {
        return repository.findByCustomerIdOrderByReadingDateDesc(customerId);
    }

    /**
     * Real aggregation: sums kWhConsumed across every reading for this
     * customer whose readingDate falls within [from, to] inclusive, and
     * counts them. The empty-history case is handled explicitly (not left
     * to fall out of an empty-stream reduction by accident) so the
     * "genuinely zero readings" case is a deliberate branch, not an
     * implicit side effect -- see UsageSummaryResponse's Javadoc for why
     * that distinction, while structurally guaranteed here by the
     * @Positive constraint on every stored reading, is still surfaced
     * explicitly via readingCount rather than relied on silently.
     */
    @Transactional(readOnly = true)
    public UsageSummaryResponse getUsageSummary(Long customerId, LocalDate from, LocalDate to) {
        if (from.isAfter(to)) {
            throw new IllegalArgumentException("from date must not be after to date");
        }
        List<MeterReading> readings = repository.findByCustomerIdAndReadingDateBetween(customerId, from, to);
        if (readings.isEmpty()) {
            return new UsageSummaryResponse(customerId, from, to, BigDecimal.ZERO, 0);
        }
        BigDecimal total = readings.stream()
                .map(MeterReading::getKWhConsumed)
                .reduce(BigDecimal.ZERO, BigDecimal::add);
        return new UsageSummaryResponse(customerId, from, to, total, readings.size());
    }
}
