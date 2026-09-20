package com.example.billingservice.dto;

import com.example.billingservice.model.ContractPlan;
import com.example.billingservice.model.ContractPlanStatus;

import java.math.BigDecimal;
import java.time.LocalDate;

public record ContractPlanResponse(
        Long id,
        Long customerId,
        String planName,
        BigDecimal ratePerKwh,
        LocalDate effectiveStartDate,
        LocalDate effectiveEndDate,
        ContractPlanStatus status
) {
    public static ContractPlanResponse from(ContractPlan plan) {
        return new ContractPlanResponse(
                plan.getId(),
                plan.getCustomerId(),
                plan.getPlanName(),
                plan.getRatePerKwh(),
                plan.getEffectiveStartDate(),
                plan.getEffectiveEndDate(),
                plan.getStatus()
        );
    }
}
