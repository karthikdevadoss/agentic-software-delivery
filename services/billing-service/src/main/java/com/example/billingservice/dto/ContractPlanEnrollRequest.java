package com.example.billingservice.dto;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.math.BigDecimal;
import java.time.LocalDate;

public record ContractPlanEnrollRequest(
        @NotBlank(message = "planName must not be blank") String planName,
        @NotNull(message = "ratePerKwh must not be null")
        @DecimalMin(value = "0.0", inclusive = false, message = "ratePerKwh must be greater than zero") BigDecimal ratePerKwh,
        @NotNull(message = "effectiveStartDate must not be null") LocalDate effectiveStartDate
) {
}
