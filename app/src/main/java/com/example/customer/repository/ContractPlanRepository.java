package com.example.customer.repository;

import com.example.customer.model.ContractPlan;
import com.example.customer.model.ContractPlanStatus;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface ContractPlanRepository extends JpaRepository<ContractPlan, Long> {
    Optional<ContractPlan> findByCustomerIdAndStatus(Long customerId, ContractPlanStatus status);
}
