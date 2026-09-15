package com.example.customer.triage;

import com.example.customer.dto.ContractPlanResponse;

import java.util.List;

/** Real evidence returned to the Triage Lab UI: the actual resulting plan
 * history after two identical enrollment submissions, plus the derived
 * verdict (defectReproduced = more than one plan row exists for what
 * should have been a single business action). */
public record TriageReproductionResult(
        Long triageCustomerId,
        boolean fixApplied,
        List<ContractPlanResponse> plans,
        boolean defectReproduced,
        long activePlanCount
) {
}
