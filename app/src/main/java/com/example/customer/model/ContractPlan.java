package com.example.customer.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * References the owning customer by {@code customerId} only — same
 * rationale as {@link CustomerPreference}: no code path needs an in-memory
 * Plan -&gt; Customer navigation, so no JPA relationship is declared.
 */
@Entity
public class ContractPlan {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private Long customerId;

    @Column(nullable = false)
    private String planName;

    @Column(nullable = false, precision = 10, scale = 4)
    private BigDecimal ratePerKwh;

    @Column(nullable = false)
    private LocalDate effectiveStartDate;

    private LocalDate effectiveEndDate;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private ContractPlanStatus status;

    protected ContractPlan() {
    }

    public ContractPlan(Long customerId, String planName, BigDecimal ratePerKwh, LocalDate effectiveStartDate) {
        this.customerId = customerId;
        this.planName = planName;
        this.ratePerKwh = ratePerKwh;
        this.effectiveStartDate = effectiveStartDate;
        this.status = ContractPlanStatus.ACTIVE;
    }

    public Long getId() {
        return id;
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

    public LocalDate getEffectiveStartDate() {
        return effectiveStartDate;
    }

    public LocalDate getEffectiveEndDate() {
        return effectiveEndDate;
    }

    public ContractPlanStatus getStatus() {
        return status;
    }

    /** Business rule: a superseded plan is cancelled, end-dated the day the
     * replacement plan starts — never deleted, so plan history is preserved. */
    public void cancel(LocalDate effectiveEndDate) {
        this.status = ContractPlanStatus.CANCELLED;
        this.effectiveEndDate = effectiveEndDate;
    }
}
