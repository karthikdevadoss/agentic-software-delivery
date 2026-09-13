package com.example.customer.service;

import com.example.customer.dto.ContractPlanEnrollRequest;
import com.example.customer.model.ContractPlan;
import com.example.customer.model.ContractPlanStatus;
import com.example.customer.repository.ContractPlanRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.NoSuchElementException;

/**
 * BUSINESS REQUIREMENT: a customer has at most one ACTIVE energy plan at a
 * time. Enrolling in a new plan must not silently leave two plans marked
 * ACTIVE (a real data-integrity bug class this test suite specifically
 * checks for) — the prior active plan is cancelled, end-dated on the new
 * plan's start date, and kept (never deleted) so plan history is queryable.
 */
@Service
public class ContractPlanService {

    static final String NO_ACTIVE_PLAN_MESSAGE = "No active contract plan found for customer";

    private final ContractPlanRepository contractPlanRepository;
    private final CustomerService customerService;

    public ContractPlanService(ContractPlanRepository contractPlanRepository, CustomerService customerService) {
        this.contractPlanRepository = contractPlanRepository;
        this.customerService = customerService;
    }

    public ContractPlan getActivePlan(Long customerId) {
        return contractPlanRepository.findByCustomerIdAndStatus(customerId, ContractPlanStatus.ACTIVE)
                .orElseThrow(() -> new NoSuchElementException(NO_ACTIVE_PLAN_MESSAGE + ": " + customerId));
    }

    @Transactional
    public ContractPlan enroll(Long customerId, ContractPlanEnrollRequest request) {
        customerService.getById(customerId); // 404s if the customer itself does not exist

        contractPlanRepository.findByCustomerIdAndStatus(customerId, ContractPlanStatus.ACTIVE)
                .ifPresent(existing -> {
                    existing.cancel(request.effectiveStartDate());
                    contractPlanRepository.save(existing);
                });

        ContractPlan newPlan = new ContractPlan(
                customerId, request.planName(), request.ratePerKwh(), request.effectiveStartDate());
        return contractPlanRepository.save(newPlan);
    }
}
