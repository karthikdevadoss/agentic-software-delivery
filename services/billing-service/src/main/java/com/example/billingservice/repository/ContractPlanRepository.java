package com.example.billingservice.repository;

import com.example.billingservice.model.ContractPlan;
import com.example.billingservice.model.ContractPlanStatus;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface ContractPlanRepository extends JpaRepository<ContractPlan, Long> {
    Optional<ContractPlan> findByCustomerIdAndStatus(Long customerId, ContractPlanStatus status);

    /** Full plan history for one customer, oldest first -- a real audit-trail
     * query, ported from the monolith's equivalent (used there by the
     * Incident Triage Lab, which does not exist in this service). */
    List<ContractPlan> findByCustomerIdOrderByIdAsc(Long customerId);
}
