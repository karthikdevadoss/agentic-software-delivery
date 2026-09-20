package com.example.billingservice.service;

import com.example.billingservice.client.MeteringUsageClient;
import com.example.billingservice.client.UsageSummaryResponse;
import com.example.billingservice.dto.EstimatedUsageCostResponse;
import com.example.billingservice.exception.MeteringServiceUnavailableException;
import com.example.billingservice.model.ContractPlan;
import org.springframework.context.annotation.Lazy;
import org.springframework.stereotype.Service;

import java.math.RoundingMode;
import java.time.LocalDate;

/**
 * BL-015: real metering-to-billing integration -- a deliberately separate
 * class from ContractPlanService rather than a new method there, so this
 * new cross-cutting concern (which needs a genuinely new dependency,
 * MeteringUsageClient) never touches ContractPlanService's existing
 * constructor, and every test that already exercises it stays
 * unaffected. Reuses ContractPlanService.getActivePlan() for the plan
 * half of the calculation -- never re-implements that lookup.
 */
@Service
public class UsageEstimationService {

    private final ContractPlanService contractPlanService;
    private final MeteringUsageClient meteringUsageClient;

    public UsageEstimationService(ContractPlanService contractPlanService, @Lazy MeteringUsageClient meteringUsageClient) {
        this.contractPlanService = contractPlanService;
        this.meteringUsageClient = meteringUsageClient;
    }

    /**
     * Combines the customer's real active plan rate with their real usage
     * over [from, to] into one estimated cost. Propagates the caller's
     * bearer token to metering-service (same identity-propagation pattern
     * as BillingCustomerClient). Throws NoSuchElementException (-> 404,
     * via ContractPlanService.getActivePlan) if there is no active plan,
     * or MeteringServiceUnavailableException (-> 503) if metering-service
     * could not be reached -- never a fabricated cost.
     */
    public EstimatedUsageCostResponse estimateCost(Long customerId, LocalDate from, LocalDate to, String callerBearerToken) {
        ContractPlan activePlan = contractPlanService.getActivePlan(customerId);

        UsageSummaryResponse usage = meteringUsageClient.getUsageSummary(customerId, from, to, callerBearerToken)
                .orElseThrow(() -> new MeteringServiceUnavailableException(
                        "metering-service unreachable while estimating usage cost for customer " + customerId + " -- please retry"));

        java.math.BigDecimal estimatedCost = usage.totalKwhConsumed().multiply(activePlan.getRatePerKwh())
                .setScale(2, RoundingMode.HALF_UP);

        return new EstimatedUsageCostResponse(
                customerId, usage.periodStart(), usage.periodEnd(), usage.totalKwhConsumed(), usage.readingCount(),
                activePlan.getPlanName(), activePlan.getRatePerKwh(), estimatedCost);
    }
}
