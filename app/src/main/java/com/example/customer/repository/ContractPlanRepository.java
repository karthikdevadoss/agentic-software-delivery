package com.example.customer.repository;

import com.example.customer.model.ContractPlan;
import com.example.customer.model.ContractPlanStatus;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface ContractPlanRepository extends JpaRepository<ContractPlan, Long> {
    Optional<ContractPlan> findByCustomerIdAndStatus(Long customerId, ContractPlanStatus status);

    /** Full plan history for one customer, oldest first -- used by the
     * Incident Triage Lab (Scenario A) to show real evidence of duplicate
     * ACTIVE-plan churn, and available generally as a real audit-trail
     * query. */
    List<ContractPlan> findByCustomerIdOrderByIdAsc(Long customerId);
}
