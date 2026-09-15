package com.example.customer.triage;

import com.example.customer.model.Customer;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Incident Triage Lab -- Scenario C (admin search: Postgres bind-parameter
 * type inference).
 *
 * ISOLATION CONTRACT, mirroring TriageScenarioAService/TriageScenarioBService
 * exactly: every method here operates ONLY on dedicated, clearly-labeled
 * synthetic "Triage Scenario C" customer rows (name/email prefix
 * "triagescenarioc-"), created fresh by reset() -- never touches
 * CustomerRepository.searchWorkspaceCustomers (the real, already-fixed
 * production admin-search query) or any real customer's data. The buggy
 * query below is a byte-for-byte faithful replay of the REAL pre-fix JPQL
 * shape from CustomerRepository (before commit 9f35f27): an OPTIONAL,
 * nullable search parameter used in BOTH an ":term IS NULL" check AND
 * inside LOWER(CONCAT('%', :term, '%')) -- this specific dual-usage
 * pattern is what made PostgreSQL's JDBC driver unable to infer a
 * concrete type for the parameter, defaulting it to bytea (`function
 * lower(bytea) does not exist`).
 *
 * HONEST ABOUT H2: this dev machine has no local Docker daemon (see
 * PostgresFlywayIntegrationTest's Javadoc), so the buggy path cannot be
 * proven to fail against real Postgres in local development -- only
 * against a real Postgres Testcontainers instance (CI) or the real
 * deployed production database, both of which this scenario is designed
 * to reach. On H2, the buggy query simply succeeds (H2 has no equivalent
 * type-inference gap) -- reproduce() reports this honestly via
 * querySucceeded/defectReproduced, never fabricated either way.
 */
@Service
public class TriageScenarioCService {

    private static final AtomicLong RESET_COUNTER = new AtomicLong();
    private static final String SEARCH_TERM = "triagescenarioc";

    @PersistenceContext
    private EntityManager entityManager;

    private volatile boolean fixApplied = false;

    @Transactional
    public synchronized TriageCState reset() {
        long n = RESET_COUNTER.incrementAndGet();
        Customer customer = new Customer(
                "TriageScenarioC Search Target " + n, "triagescenarioc-" + n + "@triagelab.internal");
        entityManager.persist(customer);
        this.fixApplied = false;
        return state();
    }

    /** Runs the real, currently-active JPQL search shape (buggy pre-fix or
     * real fixed post-approval) against the real database -- never
     * simulated. Any exception is caught and reported as real evidence,
     * never swallowed into a fabricated "no defect" result. readOnly=true
     * since this never writes -- avoids any risk of a query-execution
     * failure escalating an unrelated write's transaction. */
    @Transactional(readOnly = true)
    public TriageCReproductionResult reproduce() {
        boolean querySucceeded;
        int resultCount = 0;
        String errorType = null;
        String errorMessage = null;
        try {
            List<Customer> results = fixApplied ? searchFixed() : searchBuggy();
            resultCount = results.size();
            querySucceeded = true;
        } catch (RuntimeException e) {
            querySucceeded = false;
            Throwable root = rootCause(e);
            errorType = root.getClass().getSimpleName();
            errorMessage = root.getMessage();
        }
        boolean defectReproduced = !fixApplied && !querySucceeded;
        return new TriageCReproductionResult(fixApplied, querySucceeded, resultCount, errorType, errorMessage, defectReproduced);
    }

    /**
     * REAL, DELIBERATELY-PRESERVED PRE-FIX SHAPE (isolated pedagogical
     * replay, never reachable by the real admin-search endpoint): the
     * bind parameter itself is wrapped in LOWER(CONCAT('%', :term, '%')),
     * and the same parameter is also compared via ":term IS NULL" --
     * this exact dual-context usage is the real historical trigger for
     * PostgreSQL's bytea type-inference default.
     */
    private List<Customer> searchBuggy() {
        return entityManager.createQuery(
                        "SELECT c FROM Customer c WHERE (:term IS NULL OR LOWER(c.name) LIKE LOWER(CONCAT('%', :term, '%')))",
                        Customer.class)
                .setParameter("term", SEARCH_TERM)
                .getResultList();
    }

    /**
     * REAL FIX SHAPE, mirroring CustomerRepository.searchWorkspaceCustomers's
     * actual current production query exactly: the full "%value%" LIKE
     * pattern is pre-built in Java and bound as a plain String parameter,
     * never wrapped in CONCAT/LOWER itself.
     */
    private List<Customer> searchFixed() {
        String pattern = "%" + SEARCH_TERM + "%";
        return entityManager.createQuery(
                        "SELECT c FROM Customer c WHERE (:pattern IS NULL OR LOWER(c.name) LIKE :pattern)",
                        Customer.class)
                .setParameter("pattern", pattern)
                .getResultList();
    }

    private static Throwable rootCause(Throwable t) {
        Throwable cause = t;
        while (cause.getCause() != null && cause.getCause() != cause) {
            cause = cause.getCause();
        }
        return cause;
    }

    /** Requires ADMIN authorization at the controller layer (see
     * TriageScenarioCController) -- flips only this isolated scenario's
     * own state, never touches the real production search query. */
    public synchronized TriageCState approveFix() {
        this.fixApplied = true;
        return state();
    }

    public TriageCState state() {
        return new TriageCState(fixApplied);
    }
}
