package com.example.billingservice.controller;

import com.example.billingservice.cache.ContractPlanCacheService;
import com.example.billingservice.dto.ContractPlanEnrollRequest;
import com.example.billingservice.dto.ContractPlanResponse;
import com.example.billingservice.dto.EstimatedUsageCostResponse;
import com.example.billingservice.service.ContractPlanService;
import com.example.billingservice.service.UsageEstimationService;
import jakarta.validation.Valid;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;

/**
 * Ported from app/'s ContractPlanController, with one deliberate
 * simplification: no WorkspaceAccessGuard call here. The monolith's guard
 * enforces per-persona workspace isolation using a "cid" claim minted by
 * its own DemoJwtIssuer/DemoLoginController -- login/persona issuance is
 * explicitly customer-service's responsibility in this decomposition
 * (see docs/MICROSERVICES_ARCHITECTURE.md's "Why Customer Service owns
 * auth"), and porting that guard here was not part of this service's
 * scoped file list. This service's real security boundary is SecurityConfig's
 * scope-based authorization (SCOPE_contract:read / SCOPE_contract:write) --
 * every request still requires a valid, correctly-signed JWT from the
 * shared issuer; only the finer-grained per-customer workspace check is
 * out of scope for this port.
 */
@RestController
@RequestMapping("/customers/{customerId}/plan")
public class ContractPlanController {

    private final ContractPlanService contractPlanService;
    private final ContractPlanCacheService contractPlanCacheService;
    private final UsageEstimationService usageEstimationService;

    public ContractPlanController(
            ContractPlanService contractPlanService,
            ContractPlanCacheService contractPlanCacheService,
            UsageEstimationService usageEstimationService) {
        this.contractPlanService = contractPlanService;
        this.contractPlanCacheService = contractPlanCacheService;
        this.usageEstimationService = usageEstimationService;
    }

    @GetMapping
    public ContractPlanResponse getActivePlan(@PathVariable Long customerId) {
        return contractPlanCacheService.getActivePlan(customerId);
    }

    /**
     * BL-015: real metering-to-billing integration -- see
     * UsageEstimationService for the actual combination logic.
     */
    @GetMapping("/usage-estimated-cost")
    public EstimatedUsageCostResponse getEstimatedUsageCost(
            @PathVariable Long customerId,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate from,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate to,
            @RequestHeader(HttpHeaders.AUTHORIZATION) String authorizationHeader) {
        return usageEstimationService.estimateCost(customerId, from, to, authorizationHeader);
    }

    @PostMapping
    public ResponseEntity<ContractPlanResponse> enroll(
            @PathVariable Long customerId, @Valid @RequestBody ContractPlanEnrollRequest request,
            @RequestHeader(HttpHeaders.AUTHORIZATION) String authorizationHeader) {
        // Propagated to customer-service's own JWT validation via
        // BillingCustomerClient -- see its Javadoc for why this identity-
        // propagation call is necessary, not optional.
        ContractPlanResponse response = ContractPlanResponse.from(
                contractPlanService.enroll(customerId, request, authorizationHeader));
        contractPlanCacheService.evict(customerId);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }
}
