package com.example.customer.repository;

import com.example.customer.model.CustomerPreference;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface CustomerPreferenceRepository extends JpaRepository<CustomerPreference, Long> {
    Optional<CustomerPreference> findByCustomerId(Long customerId);
}
