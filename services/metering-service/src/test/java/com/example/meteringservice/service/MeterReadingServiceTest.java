package com.example.meteringservice.service;

import com.example.meteringservice.dto.MeterReadingRequest;
import com.example.meteringservice.dto.UsageSummaryResponse;
import com.example.meteringservice.model.MeterReading;
import com.example.meteringservice.repository.MeterReadingRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Real unit coverage for the genuinely new aggregation logic -- this is
 * where this service's actual business-logic value lives, so the math
 * (not just wiring) is what's tested here.
 */
@ExtendWith(MockitoExtension.class)
class MeterReadingServiceTest {

    @Mock
    private MeterReadingRepository repository;

    private MeterReadingService service;

    @Test
    void submitReading_persistsAReadingBoundToTheGivenCustomer() {
        service = new MeterReadingService(repository);
        MeterReadingRequest request = new MeterReadingRequest("METER-1", LocalDate.of(2026, 9, 1), new BigDecimal("12.500"));
        MeterReading saved = new MeterReading(42L, "METER-1", LocalDate.of(2026, 9, 1), new BigDecimal("12.500"));
        when(repository.save(any(MeterReading.class))).thenReturn(saved);

        MeterReading result = service.submitReading(42L, request);

        ArgumentCaptor<MeterReading> captor = ArgumentCaptor.forClass(MeterReading.class);
        verify(repository).save(captor.capture());
        MeterReading toPersist = captor.getValue();
        assertThat(toPersist.getCustomerId()).isEqualTo(42L);
        assertThat(toPersist.getMeterId()).isEqualTo("METER-1");
        assertThat(toPersist.getReadingDate()).isEqualTo(LocalDate.of(2026, 9, 1));
        assertThat(toPersist.getKWhConsumed()).isEqualByComparingTo("12.500");
        assertThat(result).isSameAs(saved);
    }

    @Test
    void getUsageSummary_sumsMultipleReadingsWithinRangeAndCountsThem() {
        service = new MeterReadingService(repository);
        LocalDate from = LocalDate.of(2026, 9, 1);
        LocalDate to = LocalDate.of(2026, 9, 30);
        List<MeterReading> readings = List.of(
                new MeterReading(7L, "METER-A", LocalDate.of(2026, 9, 5), new BigDecimal("10.000")),
                new MeterReading(7L, "METER-A", LocalDate.of(2026, 9, 15), new BigDecimal("15.250")),
                new MeterReading(7L, "METER-A", LocalDate.of(2026, 9, 25), new BigDecimal("5.750")));
        when(repository.findByCustomerIdAndReadingDateBetween(7L, from, to)).thenReturn(readings);

        UsageSummaryResponse summary = service.getUsageSummary(7L, from, to);

        assertThat(summary.customerId()).isEqualTo(7L);
        assertThat(summary.periodStart()).isEqualTo(from);
        assertThat(summary.periodEnd()).isEqualTo(to);
        // 10.000 + 15.250 + 5.750 = 31.000 -- real decimal summation, not a rounded/approximate check.
        assertThat(summary.totalKwhConsumed()).isEqualByComparingTo("31.000");
        assertThat(summary.readingCount()).isEqualTo(3);
    }

    @Test
    void getUsageSummary_emptyHistory_returnsExplicitZeroNotAnError() {
        service = new MeterReadingService(repository);
        LocalDate from = LocalDate.of(2026, 1, 1);
        LocalDate to = LocalDate.of(2026, 1, 31);
        when(repository.findByCustomerIdAndReadingDateBetween(99L, from, to)).thenReturn(List.of());

        UsageSummaryResponse summary = service.getUsageSummary(99L, from, to);

        assertThat(summary.totalKwhConsumed()).isEqualByComparingTo(BigDecimal.ZERO);
        assertThat(summary.readingCount()).isEqualTo(0L);
    }

    @Test
    void getUsageSummary_onlyQueriesReadingsWithinTheRequestedRange_readingsOutsideAreExcludedByTheRepositoryQuery() {
        // This proves the SERVICE asks the repository for exactly the right
        // bounded range (the real exclusion contract), independent of
        // whatever a mocked repository happens to return -- the repository
        // method itself (findByCustomerIdAndReadingDateBetween) is Spring
        // Data-derived and not re-tested here; what's tested is that the
        // service does not, say, fetch full history and filter in memory
        // with different/wrong bounds.
        service = new MeterReadingService(repository);
        LocalDate from = LocalDate.of(2026, 6, 1);
        LocalDate to = LocalDate.of(2026, 6, 30);
        // Simulate the repository correctly excluding an out-of-range July
        // reading by simply never returning it for this exact from/to.
        List<MeterReading> inRangeOnly = List.of(
                new MeterReading(3L, "METER-Z", LocalDate.of(2026, 6, 10), new BigDecimal("20.000")));
        when(repository.findByCustomerIdAndReadingDateBetween(eq(3L), eq(from), eq(to))).thenReturn(inRangeOnly);

        UsageSummaryResponse summary = service.getUsageSummary(3L, from, to);

        verify(repository).findByCustomerIdAndReadingDateBetween(3L, from, to);
        assertThat(summary.totalKwhConsumed()).isEqualByComparingTo("20.000");
        assertThat(summary.readingCount()).isEqualTo(1);
    }

    @Test
    void getUsageSummary_fromAfterTo_rejectedBeforeQueryingRepository() {
        service = new MeterReadingService(repository);
        LocalDate from = LocalDate.of(2026, 9, 30);
        LocalDate to = LocalDate.of(2026, 9, 1);

        org.junit.jupiter.api.Assertions.assertThrows(IllegalArgumentException.class,
                () -> service.getUsageSummary(1L, from, to));
    }

    @Test
    void getHistory_returnsRepositoryResultUnmodified_mostRecentFirstOrderingOwnedByTheQuery() {
        service = new MeterReadingService(repository);
        List<MeterReading> history = List.of(
                new MeterReading(5L, "METER-Q", LocalDate.of(2026, 9, 10), new BigDecimal("1.000")),
                new MeterReading(5L, "METER-Q", LocalDate.of(2026, 9, 1), new BigDecimal("2.000")));
        when(repository.findByCustomerIdOrderByReadingDateDesc(5L)).thenReturn(history);

        List<MeterReading> result = service.getHistory(5L);

        assertThat(result).isEqualTo(history);
    }
}
