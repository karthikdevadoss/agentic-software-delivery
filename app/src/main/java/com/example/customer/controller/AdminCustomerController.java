package com.example.customer.controller;

import com.example.customer.model.Customer;
import com.example.customer.model.ContractPlanStatus;
import com.example.customer.repository.ContractPlanRepository;
import com.example.customer.repository.CustomerRepository;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * ADMIN-only "All Customers" administration -- gated entirely by
 * SecurityConfig's requestMatcher on /admin/customers (requires the
 * "admin:read" scope, which only DemoJwtIssuer#issuePersonaToken ever
 * grants, and only for a genuinely ADMIN-role demo_identity). A USER
 * token is rejected with a real 403 by Spring Security itself before
 * this controller method is ever invoked -- no additional check needed
 * here for that boundary.
 *
 * Deliberately narrow: this is Customer-App business-data administration
 * only. It grants nothing beyond the SAME business read/write scopes
 * every persona already carries (see DemoJwtIssuer.DEMO_SCOPES) plus
 * "admin:read" -- no Git/Railway/deployment/infrastructure/secrets/
 * Workbench-owner capability exists anywhere in this scope set for an
 * ADMIN persona to be granted.
 */
@RestController
@RequestMapping("/admin/customers")
@Tag(name = "Admin", description = "ADMIN-only customer administration, scoped to the current demo workspace")
@SecurityRequirement(name = "bearerAuth")
public class AdminCustomerController {

    public record AdminCustomerRow(Long customerId, String name, String email, String planStatus) {
    }

    public record AdminCustomerPage(List<AdminCustomerRow> content, int page, int size, long totalElements, int totalPages) {
    }

    private static final int MAX_PAGE_SIZE = 100;

    private final CustomerRepository customerRepository;
    private final ContractPlanRepository contractPlanRepository;

    public AdminCustomerController(CustomerRepository customerRepository, ContractPlanRepository contractPlanRepository) {
        this.customerRepository = customerRepository;
        this.contractPlanRepository = contractPlanRepository;
    }

    @GetMapping
    public AdminCustomerPage listCustomers(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) Long customerId,
            @RequestParam(required = false) String name,
            @RequestParam(required = false) String email) {
        Pageable pageable = PageRequest.of(Math.max(page, 0), Math.min(Math.max(size, 1), MAX_PAGE_SIZE), Sort.by("id"));
        String namePattern = likePattern(name);
        String emailPattern = likePattern(email);

        Page<Customer> result = customerRepository.searchWorkspaceCustomers(customerId, namePattern, emailPattern, pageable);

        List<AdminCustomerRow> rows = result.getContent().stream()
                .map(c -> new AdminCustomerRow(c.getId(), c.getName(), c.getEmail(), activePlanStatus(c.getId())))
                .toList();
        return new AdminCustomerPage(rows, result.getNumber(), result.getSize(), result.getTotalElements(), result.getTotalPages());
    }

    private String activePlanStatus(Long customerId) {
        return contractPlanRepository.findByCustomerIdAndStatus(customerId, ContractPlanStatus.ACTIVE)
                .map(plan -> plan.getPlanName() + " (ACTIVE)")
                .orElse("NO ACTIVE PLAN");
    }

    /** Pre-builds the full "%value%" LIKE pattern, already lowercased, so
     * the repository query never wraps the bind parameter itself in
     * CONCAT/LOWER (see CustomerRepository's Javadoc for the real
     * Postgres bug this avoids). */
    private static String likePattern(String value) {
        if (value == null || value.isBlank()) return null;
        return "%" + value.trim().toLowerCase() + "%";
    }
}
