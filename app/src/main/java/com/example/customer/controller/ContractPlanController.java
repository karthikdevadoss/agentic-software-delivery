package com.example.customer.controller;

import com.example.customer.dto.ContractPlanEnrollRequest;
import com.example.customer.dto.ContractPlanResponse;
import com.example.customer.service.ContractPlanService;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/customers/{customerId}/plan")
@Tag(name = "Contract Plan", description = "A customer's current energy contract/plan")
public class ContractPlanController {

    private final ContractPlanService contractPlanService;

    public ContractPlanController(ContractPlanService contractPlanService) {
        this.contractPlanService = contractPlanService;
    }

    @GetMapping
    public ContractPlanResponse getActivePlan(@PathVariable Long customerId) {
        return ContractPlanResponse.from(contractPlanService.getActivePlan(customerId));
    }

    @PostMapping
    public ResponseEntity<ContractPlanResponse> enroll(
            @PathVariable Long customerId, @Valid @RequestBody ContractPlanEnrollRequest request) {
        ContractPlanResponse response = ContractPlanResponse.from(contractPlanService.enroll(customerId, request));
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }
}
