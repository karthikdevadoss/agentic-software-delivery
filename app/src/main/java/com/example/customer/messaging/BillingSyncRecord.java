package com.example.customer.messaging;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * A real, independently-verifiable side effect of the BillingSync consumer
 * (see ContractPlanBillingSyncConsumer) -- deliberately a persisted row
 * rather than a log line, so a fan-out test can assert both consumers
 * genuinely did their own separate work from the SAME event, not just that
 * neither threw. Simulates syncing a new enrollment to an external billing
 * system: no real downstream billing provider exists (same honest
 * portfolio-scope boundary as AppointmentAvailabilityClient), so this row
 * IS the observable proof of the sync rather than a real outbound call.
 */
@Entity
public class BillingSyncRecord {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private Long contractPlanId;

    @Column(nullable = false)
    private Long customerId;

    @Column(nullable = false)
    private String planName;

    @Column(nullable = false, precision = 10, scale = 4)
    private BigDecimal ratePerKwh;

    @Column(nullable = false)
    private Instant syncedAt;

    protected BillingSyncRecord() {
    }

    public BillingSyncRecord(Long contractPlanId, Long customerId, String planName, BigDecimal ratePerKwh) {
        this.contractPlanId = contractPlanId;
        this.customerId = customerId;
        this.planName = planName;
        this.ratePerKwh = ratePerKwh;
        this.syncedAt = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public Long getContractPlanId() {
        return contractPlanId;
    }

    public Long getCustomerId() {
        return customerId;
    }

    public String getPlanName() {
        return planName;
    }

    public BigDecimal getRatePerKwh() {
        return ratePerKwh;
    }

    public Instant getSyncedAt() {
        return syncedAt;
    }
}
