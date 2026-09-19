package com.example.customer.messaging;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface BillingSyncRecordRepository extends JpaRepository<BillingSyncRecord, Long> {

    List<BillingSyncRecord> findByContractPlanId(Long contractPlanId);
}
