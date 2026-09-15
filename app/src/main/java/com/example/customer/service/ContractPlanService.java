package com.example.customer.service;

import com.example.customer.dto.ContractPlanEnrollRequest;
import com.example.customer.model.ContractPlan;
import com.example.customer.model.ContractPlanStatus;
import com.example.customer.repository.ContractPlanRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.NoSuchElementException;
import java.util.Optional;

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

        Optional<ContractPlan> currentlyActive =
                contractPlanRepository.findByCustomerIdAndStatus(customerId, ContractPlanStatus.ACTIVE);

        // IDEMPOTENCY: a duplicate submission of the exact same enrollment
        // (a double-click, or a client retrying after a timeout whose
        // original request actually succeeded server-side) must not be
        // treated as a second business event. Before this check existed, a
        // repeat call cancelled the plan the FIRST call had just activated
        // and created another new plan identical to it -- two CANCELLED
        // rows plus a second ACTIVE row in the customer's plan history for
        // what was really one action, and any future side effect fired on
        // ACTIVE-plan creation (billing, notifications, events) would have
        // double-fired. If the currently active plan already has identical
        // terms to what's being requested, this is a no-op: return it
        // unchanged, touch nothing else.
        if (currentlyActive.filter(existing -> isSameTerms(existing, request)).isPresent()) {
            return currentlyActive.get();
        }

        // REAL BUG found only by a genuine Postgres integration test (H2's
        // ddl-auto schema has no equivalent constraint to violate, so this
        // was invisible there): Hibernate's default flush ORDER executes
        // all pending INSERTs before any pending UPDATEs in a single
        // transaction flush, regardless of the order save() was called in
        // Java code. Using plain save() here let the new plan's INSERT
        // reach Postgres before the old plan's cancellation UPDATE did --
        // for one instant, two ACTIVE rows existed for the same customer,
        // which uq_contract_plan_one_active_per_customer (a real,
        // immediate, non-deferred Postgres constraint) correctly rejected
        // with a 500. saveAndFlush() forces the cancellation to reach the
        // database BEFORE the new row is ever inserted, closing the gap.
        currentlyActive.ifPresent(existing -> {
            existing.cancel(request.effectiveStartDate());
            contractPlanRepository.saveAndFlush(existing);
        });

        ContractPlan newPlan = new ContractPlan(
                customerId, request.planName(), request.ratePerKwh(), request.effectiveStartDate());
        return contractPlanRepository.save(newPlan);
    }

    private static boolean isSameTerms(ContractPlan existing, ContractPlanEnrollRequest request) {
        return existing.getPlanName().equals(request.planName())
                && existing.getRatePerKwh().compareTo(request.ratePerKwh()) == 0
                && existing.getEffectiveStartDate().equals(request.effectiveStartDate());
    }
}
