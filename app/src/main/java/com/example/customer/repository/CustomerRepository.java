package com.example.customer.repository;

import com.example.customer.model.Customer;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface CustomerRepository extends JpaRepository<Customer, Long> {

    /**
     * ADMIN "All Customers" backing query -- real server-side pagination
     * and search (never fetch-everything-and-filter-in-JavaScript). The
     * "current demo workspace" is deliberately scoped to customers bound
     * to a real demo_identity row (see DemoIdentity), not every Customer
     * row ever created -- the pre-login-gate app used to auto-create a
     * fresh ephemeral Customer on every anonymous visit with no stored
     * id, so an unscoped SELECT * would surface a large amount of
     * unrelated historical clutter, not "the demo workspace's real
     * customers." Each filter parameter is optional (null = no
     * constraint on that field).
     */
    @Query("SELECT c FROM Customer c WHERE c.id IN (SELECT d.customerId FROM DemoIdentity d WHERE d.customerId IS NOT NULL) "
            + "AND (:customerId IS NULL OR c.id = :customerId) "
            + "AND (:name IS NULL OR LOWER(c.name) LIKE LOWER(CONCAT('%', :name, '%'))) "
            + "AND (:email IS NULL OR LOWER(c.email) LIKE LOWER(CONCAT('%', :email, '%')))")
    Page<Customer> searchWorkspaceCustomers(
            @Param("customerId") Long customerId,
            @Param("name") String name,
            @Param("email") String email,
            Pageable pageable);
}
