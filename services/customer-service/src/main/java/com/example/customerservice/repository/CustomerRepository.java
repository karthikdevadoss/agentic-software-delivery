package com.example.customerservice.repository;

import com.example.customerservice.model.Customer;
import org.springframework.data.jpa.repository.JpaRepository;

/**
 * SIMPLIFIED relative to the monolith's CustomerRepository: no
 * searchWorkspaceCustomers admin query here -- that query exists to back
 * the monolith's admin "All Customers" screen, a responsibility this
 * service does not own. A plain JpaRepository is the whole contract this
 * service's own endpoints (create/get/update) need.
 */
public interface CustomerRepository extends JpaRepository<Customer, Long> {
}
