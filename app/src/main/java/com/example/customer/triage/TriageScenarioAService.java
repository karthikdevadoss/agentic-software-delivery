package com.example.customer.triage;

import com.example.customer.dto.ContractPlanEnrollRequest;
import com.example.customer.dto.ContractPlanResponse;
import com.example.customer.model.ContractPlan;
import com.example.customer.model.ContractPlanStatus;
import com.example.customer.model.Customer;
import com.example.customer.repository.ContractPlanRepository;
import com.example.customer.service.ContractPlanService;
import com.example.customer.service.CustomerService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Incident Triage Lab -- Scenario A (plan-enrollment idempotency).
 *
 * ISOLATION CONTRACT: every method here operates ONLY on a dedicated,
 * clearly-labeled synthetic "Triage Scenario Customer" row (email prefix
 * "triage-scenario-a-"), created fresh by reset() -- never a real
 * persona's customer (user1/user2/user3/admin1/admin2), never any
 * customer id supplied by an HTTP caller. This mirrors the exact safety
 * pattern already established by DemoAppointmentProviderController: a
 * real code path, real database rows, real business logic -- but
 * structurally scoped so it can never touch real customer data.
 *
 * PEDAGOGICAL REPLAY, NOT A REINTRODUCED PRODUCTION BUG: enrollBuggy()
 * below is a preserved, clearly-labeled snapshot of ContractPlanService's
 * REAL pre-fix logic (before commit 2155a8a) -- the exact historical
 * defect this scenario teaches. It is never called by any real
 * customer-facing endpoint; only this isolated service can reach it, and
 * only against the dedicated triage customer. enrollFixed() delegates to
 * the real, current, production ContractPlanService -- never a second
 * copy of the fix.
 */
@Service
public class TriageScenarioAService {

    private static final AtomicLong RESET_COUNTER = new AtomicLong();

    private final ContractPlanRepository contractPlanRepository;
    private final CustomerService customerService;
    private final ContractPlanService contractPlanService;

    private volatile Long triageCustomerId;
    private volatile boolean fixApplied = false;

    public TriageScenarioAService(ContractPlanRepository contractPlanRepository, CustomerService customerService,
                                   ContractPlanService contractPlanService) {
        this.contractPlanRepository = contractPlanRepository;
        this.customerService = customerService;
        this.contractPlanService = contractPlanService;
    }

    /** Creates a brand-new, uniquely-identified triage customer and resets
     * the scenario to its defective (pre-fix) starting state, so the
     * lifecycle can be replayed from a clean slate. */
    public synchronized TriageState reset() {
        long n = RESET_COUNTER.incrementAndGet();
        Customer customer = customerService.create(
                new Customer("Triage Scenario Customer", "triage-scenario-a-" + n + "@triagelab.internal"));
        this.triageCustomerId = customer.getId();
        this.fixApplied = false;
        return state();
    }

    /** Submits the exact same enrollment request twice against the triage
     * customer -- using the buggy pre-fix path until approve() is called,
     * the real fixed ContractPlanService afterward -- and returns the
     * real resulting plan history as evidence. */
    @Transactional
    public TriageReproductionResult reproduce() {
        if (triageCustomerId == null) reset();
        ContractPlanEnrollRequest request = new ContractPlanEnrollRequest(
                "Green Energy 12mo", new BigDecimal("0.14"), LocalDate.now());

        if (fixApplied) {
            contractPlanService.enroll(triageCustomerId, request);
            contractPlanService.enroll(triageCustomerId, request);
        } else {
            enrollBuggy(triageCustomerId, request);
            enrollBuggy(triageCustomerId, request);
        }

        List<ContractPlan> history = contractPlanRepository.findByCustomerIdOrderByIdAsc(triageCustomerId);
        long activeCount = history.stream().filter(p -> p.getStatus() == ContractPlanStatus.ACTIVE).count();
        List<ContractPlanResponse> plans = history.stream().map(ContractPlanResponse::from).toList();
        return new TriageReproductionResult(triageCustomerId, fixApplied, plans, history.size() > 1, activeCount);
    }

    /** Requires ADMIN authorization at the controller layer (see
     * TriageScenarioAController) -- this method itself only flips the
     * isolated scenario's own state, never touches real production
     * code or any other customer. */
    public synchronized TriageState approveFix() {
        this.fixApplied = true;
        return state();
    }

    public TriageState state() {
        return new TriageState(triageCustomerId, fixApplied);
    }

    /**
     * REAL HISTORICAL DEFECT, preserved verbatim in spirit (see
     * ContractPlanService's pre-2155a8a history): no check at all for
     * whether the request duplicates the currently active plan. A repeat
     * call cancels the plan the first call just activated and creates a
     * second, identical one -- exactly the bug this scenario teaches.
     */
    private void enrollBuggy(Long customerId, ContractPlanEnrollRequest request) {
        customerService.getById(customerId);
        contractPlanRepository.findByCustomerIdAndStatus(customerId, ContractPlanStatus.ACTIVE)
                .ifPresent(existing -> {
                    existing.cancel(request.effectiveStartDate());
                    contractPlanRepository.saveAndFlush(existing);
                });
        ContractPlan newPlan = new ContractPlan(customerId, request.planName(), request.ratePerKwh(), request.effectiveStartDate());
        contractPlanRepository.save(newPlan);
    }
}
