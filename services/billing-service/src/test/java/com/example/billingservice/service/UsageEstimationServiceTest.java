package com.example.billingservice.service;

import com.example.billingservice.client.MeteringUsageClient;
import com.example.billingservice.client.UsageSummaryResponse;
import com.example.billingservice.dto.EstimatedUsageCostResponse;
import com.example.billingservice.exception.MeteringServiceUnavailableException;
import com.example.billingservice.model.ContractPlan;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.NoSuchElementException;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

/**
 * BL-015: real unit coverage for the actual cost-combination math --
 * mirrors ContractPlanServiceTest's Mockito style. ContractPlanService's
 * own getActivePlan() (already independently tested there) is mocked
 * directly here, same seam-mocking philosophy as BillingCustomerClient
 * being mocked in ContractPlanServiceTest.
 */
@ExtendWith(MockitoExtension.class)
class UsageEstimationServiceTest {

    private static final String TEST_BEARER_TOKEN = "Bearer test-token";
    private static final Long CUSTOMER_ID = 42L;
    private static final LocalDate FROM = LocalDate.of(2026, 9, 1);
    private static final LocalDate TO = LocalDate.of(2026, 9, 30);

    @Mock
    private ContractPlanService contractPlanService;

    @Mock
    private MeteringUsageClient meteringUsageClient;

    private UsageEstimationService service() {
        return new UsageEstimationService(contractPlanService, meteringUsageClient);
    }

    @Test
    void combinesRealRateAndRealUsage_intoTheCorrectEstimatedCost() {
        ContractPlan activePlan = new ContractPlan(CUSTOMER_ID, "Standard Plan", new BigDecimal("0.15"), LocalDate.of(2026, 1, 1));
        when(contractPlanService.getActivePlan(CUSTOMER_ID)).thenReturn(activePlan);
        when(meteringUsageClient.getUsageSummary(eq(CUSTOMER_ID), eq(FROM), eq(TO), any()))
                .thenReturn(Optional.of(new UsageSummaryResponse(CUSTOMER_ID, FROM, TO, new BigDecimal("100.0"), 4)));

        EstimatedUsageCostResponse result = service().estimateCost(CUSTOMER_ID, FROM, TO, TEST_BEARER_TOKEN);

        // 100.0 kWh * 0.15 = 15.00 -- the real, deterministic math this
        // service exists to prove, not just "some cost got returned".
        assertThat(result.estimatedCost()).isEqualByComparingTo("15.00");
        assertThat(result.totalKwhConsumed()).isEqualByComparingTo("100.0");
        assertThat(result.ratePerKwh()).isEqualByComparingTo("0.15");
        assertThat(result.planName()).isEqualTo("Standard Plan");
        assertThat(result.readingCount()).isEqualTo(4);
    }

    @Test
    void zeroUsage_isARealZeroCost_notAnError() {
        ContractPlan activePlan = new ContractPlan(CUSTOMER_ID, "Standard Plan", new BigDecimal("0.15"), LocalDate.of(2026, 1, 1));
        when(contractPlanService.getActivePlan(CUSTOMER_ID)).thenReturn(activePlan);
        when(meteringUsageClient.getUsageSummary(eq(CUSTOMER_ID), eq(FROM), eq(TO), any()))
                .thenReturn(Optional.of(new UsageSummaryResponse(CUSTOMER_ID, FROM, TO, BigDecimal.ZERO, 0)));

        EstimatedUsageCostResponse result = service().estimateCost(CUSTOMER_ID, FROM, TO, TEST_BEARER_TOKEN);

        assertThat(result.estimatedCost()).isEqualByComparingTo("0.00");
    }

    @Test
    void noActivePlan_propagatesNoSuchElementException_neverFabricatesACost() {
        when(contractPlanService.getActivePlan(CUSTOMER_ID)).thenThrow(new NoSuchElementException("No active contract plan found for customer: " + CUSTOMER_ID));

        assertThatThrownBy(() -> service().estimateCost(CUSTOMER_ID, FROM, TO, TEST_BEARER_TOKEN))
                .isInstanceOf(NoSuchElementException.class);
    }

    @Test
    void meteringServiceUnreachable_throwsMeteringServiceUnavailable_neverFabricatesACost() {
        ContractPlan activePlan = new ContractPlan(CUSTOMER_ID, "Standard Plan", new BigDecimal("0.15"), LocalDate.of(2026, 1, 1));
        when(contractPlanService.getActivePlan(CUSTOMER_ID)).thenReturn(activePlan);
        when(meteringUsageClient.getUsageSummary(eq(CUSTOMER_ID), eq(FROM), eq(TO), any()))
                .thenReturn(Optional.empty());

        assertThatThrownBy(() -> service().estimateCost(CUSTOMER_ID, FROM, TO, TEST_BEARER_TOKEN))
                .isInstanceOf(MeteringServiceUnavailableException.class);
    }
}
