package com.example.meteringservice.repository;

import com.example.meteringservice.model.MeterReading;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDate;
import java.util.List;

public interface MeterReadingRepository extends JpaRepository<MeterReading, Long> {

    /** Full history for one customer, most recent reading first -- the
     * natural order for a "usage history" screen/API consumer. */
    List<MeterReading> findByCustomerIdOrderByReadingDateDesc(Long customerId);

    /** Backs the usage-summary aggregation: every reading for one customer
     * whose readingDate falls within [from, to] inclusive on both ends --
     * matches how a human would describe a billing/reporting period
     * ("from the 1st to the 31st"), not an exclusive-end range. */
    List<MeterReading> findByCustomerIdAndReadingDateBetween(Long customerId, LocalDate from, LocalDate to);
}
