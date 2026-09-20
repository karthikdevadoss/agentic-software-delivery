package com.example.customer.messaging;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;

import java.time.Instant;

/**
 * SAGA-STYLE COMPENSATING ACTION, not a retry: when a billing sync fails
 * for a genuine BUSINESS reason (the external billing system would
 * permanently reject these terms -- simulated here, see
 * ContractPlanBillingSyncConsumer's Javadoc), retrying the same message
 * would fail identically forever; Kafka's retry+DLT machinery (see
 * KafkaMessagingConfig) exists for the DIFFERENT case of a transient/
 * technical failure (a malformed message, a momentary connection drop)
 * where trying again might actually succeed. The correct response to a
 * permanent business-rule failure is a compensating action: record what
 * needs manual reconciliation, alert someone, and mark the event
 * processed -- retrying it would never help and would eventually exhaust
 * the DLT's retry budget for no reason.
 */
@Entity
public class BillingSyncCompensation {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private Long contractPlanId;

    @Column(nullable = false)
    private Long customerId;

    @Column(nullable = false)
    private String planName;

    @Column(nullable = false)
    private String reason;

    @Column(nullable = false)
    private Instant compensatedAt;

    protected BillingSyncCompensation() {
    }

    public BillingSyncCompensation(Long contractPlanId, Long customerId, String planName, String reason) {
        this.contractPlanId = contractPlanId;
        this.customerId = customerId;
        this.planName = planName;
        this.reason = reason;
        this.compensatedAt = Instant.now();
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

    public String getReason() {
        return reason;
    }

    public Instant getCompensatedAt() {
        return compensatedAt;
    }
}
