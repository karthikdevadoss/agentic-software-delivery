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
     *
     * namePattern/emailPattern take an ALREADY-BUILT, already-lowercased
     * "%value%" LIKE pattern (see AdminCustomerController), not the raw
     * search term -- a REAL production bug (not caught by H2, only by
     * real Postgres) found using JPQL's LOWER(...LIKE LOWER(CONCAT(...))):
     * PostgreSQL's JDBC driver cannot infer a concrete type for a
     * nullable String bound through CONCAT's `||` translation and
     * defaulted it to bytea, failing with "function lower(bytea) does
     * not exist". Binding a plain, pre-built String parameter directly
     * to LIKE (no CONCAT/LOWER wrapping the parameter itself) avoids the
     * ambiguous-type inference entirely.
     */
    @Query("SELECT c FROM Customer c WHERE c.id IN (SELECT d.customerId FROM DemoIdentity d WHERE d.customerId IS NOT NULL) "
            + "AND (:customerId IS NULL OR c.id = :customerId) "
            + "AND (:namePattern IS NULL OR LOWER(c.name) LIKE :namePattern) "
            + "AND (:emailPattern IS NULL OR LOWER(c.email) LIKE :emailPattern)")
    Page<Customer> searchWorkspaceCustomers(
            @Param("customerId") Long customerId,
            @Param("namePattern") String namePattern,
            @Param("emailPattern") String emailPattern,
            Pageable pageable);
}
