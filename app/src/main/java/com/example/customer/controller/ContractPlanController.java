package com.example.customer.controller;

import com.example.customer.cache.ContractPlanCacheService;
import com.example.customer.dto.ContractPlanEnrollRequest;
import com.example.customer.dto.ContractPlanResponse;
import com.example.customer.security.WorkspaceAccessGuard;
import com.example.customer.service.ContractPlanService;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/customers/{customerId}/plan")
@Tag(name = "Contract Plan", description = "A customer's current energy contract/plan")
@SecurityRequirement(name = "bearerAuth")
public class ContractPlanController {

    private final ContractPlanService contractPlanService;
    private final ContractPlanCacheService contractPlanCacheService;
    private final WorkspaceAccessGuard workspaceAccessGuard;

    public ContractPlanController(ContractPlanService contractPlanService, ContractPlanCacheService contractPlanCacheService,
                                   WorkspaceAccessGuard workspaceAccessGuard) {
        this.contractPlanService = contractPlanService;
        this.contractPlanCacheService = contractPlanCacheService;
        this.workspaceAccessGuard = workspaceAccessGuard;
    }

    @GetMapping
    public ContractPlanResponse getActivePlan(@PathVariable Long customerId, @AuthenticationPrincipal Jwt jwt) {
        workspaceAccessGuard.assertAccessible(customerId, jwt);
        return contractPlanCacheService.getActivePlan(customerId);
    }

    @PostMapping
    public ResponseEntity<ContractPlanResponse> enroll(
            @PathVariable Long customerId, @Valid @RequestBody ContractPlanEnrollRequest request,
            @AuthenticationPrincipal Jwt jwt) {
        workspaceAccessGuard.assertAccessible(customerId, jwt);
        ContractPlanResponse response = ContractPlanResponse.from(contractPlanService.enroll(customerId, request));
        contractPlanCacheService.evict(customerId);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }
}
