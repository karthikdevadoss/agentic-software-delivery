package com.example.customerservice.repository;

import com.example.customerservice.model.CustomerPreference;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface CustomerPreferenceRepository extends JpaRepository<CustomerPreference, Long> {
    Optional<CustomerPreference> findByCustomerId(Long customerId);
}
