package com.example.customer.controller;

import com.example.customer.model.ContractPlan;
import com.example.customer.model.Customer;
import com.example.customer.model.CustomerPreference;
import com.example.customer.security.WorkspaceAccessGuard;
import com.example.customer.service.ContractPlanService;
import com.example.customer.service.CustomerPreferenceService;
import com.example.customer.service.CustomerService;
import org.springframework.graphql.data.method.annotation.Argument;
import org.springframework.graphql.data.method.annotation.MutationMapping;
import org.springframework.graphql.data.method.annotation.QueryMapping;
import org.springframework.graphql.data.method.annotation.SchemaMapping;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Controller;

import java.util.NoSuchElementException;
import java.util.Set;

/**
 * Real GraphQL alongside the existing REST API, not a replacement --
 * a client needing a customer's identity + active plan + preferences
 * currently makes 3 REST calls; here it is 1 query, with activePlan/
 * preferences resolved lazily per-field (@SchemaMapping) rather than
 * always eagerly joined, so a query that only asks for {id name email}
 * never touches the plan/preference tables at all.
 *
 * SECURITY, and why it differs from the REST controllers: every REST
 * endpoint maps one URL+verb to exactly one required scope, enforced
 * declaratively in SecurityConfig. GraphQL exposes every query AND
 * mutation through the SAME POST /graphql endpoint, so HTTP-layer,
 * path-based rules cannot distinguish "customer(id) query" from
 * "updateCustomerEmail mutation" -- both scope authorization (requireScope)
 * and row-level workspace isolation (WorkspaceAccessGuard, the exact same
 * component the REST controllers use, not a second implementation) are
 * therefore enforced explicitly, per-operation, inside this controller.
 */
@Controller
public class CustomerGraphQlController {

    private final CustomerService customerService;
    private final ContractPlanService contractPlanService;
    private final CustomerPreferenceService customerPreferenceService;
    private final WorkspaceAccessGuard workspaceAccessGuard;

    public CustomerGraphQlController(
            CustomerService customerService,
            ContractPlanService contractPlanService,
            CustomerPreferenceService customerPreferenceService,
            WorkspaceAccessGuard workspaceAccessGuard) {
        this.customerService = customerService;
        this.contractPlanService = contractPlanService;
        this.customerPreferenceService = customerPreferenceService;
        this.workspaceAccessGuard = workspaceAccessGuard;
    }

    @QueryMapping
    public Customer customer(@Argument Long id, @AuthenticationPrincipal Jwt jwt) {
        requireScope(jwt, "customer:read");
        workspaceAccessGuard.assertAccessible(id, jwt);
        return customerService.getById(id);
    }

    @MutationMapping
    public Customer updateCustomerEmail(@Argument Long id, @Argument String email, @AuthenticationPrincipal Jwt jwt) {
        requireScope(jwt, "customer:write");
        workspaceAccessGuard.assertAccessible(id, jwt);
        return customerService.updateEmail(id, email);
    }

    /**
     * Nested resolver: only invoked when a query actually asks for
     * {@code activePlan}. A customer with no active plan is a real,
     * valid outcome for this field specifically (GraphQL partial-response
     * semantics) -- it must not fail the whole query the way a REST 404
     * would fail the whole request.
     */
    @SchemaMapping(typeName = "Customer", field = "activePlan")
    public ContractPlan activePlan(Customer customer) {
        try {
            return contractPlanService.getActivePlan(customer.getId());
        } catch (NoSuchElementException noActivePlan) {
            return null;
        }
    }

    @SchemaMapping(typeName = "Customer", field = "preferences")
    public CustomerPreference preferences(Customer customer) {
        return customerPreferenceService.getOrCreateDefault(customer.getId());
    }

    @SchemaMapping(typeName = "ContractPlan", field = "status")
    public String status(ContractPlan plan) {
        return plan.getStatus().name();
    }

    @SchemaMapping(typeName = "CustomerPreferences", field = "notificationChannel")
    public String notificationChannel(CustomerPreference preference) {
        return preference.getNotificationChannel().name();
    }

    /**
     * Mirrors SecurityConfig's declarative {@code hasAuthority("SCOPE_...")}
     * rules, applied manually here since one POST /graphql endpoint cannot
     * be split by scope at the HTTP layer. DemoJwtIssuer always stores
     * "scope" as one space-delimited string claim (never a JSON array),
     * matching Spring Security's own default JwtAuthenticationConverter
     * convention that SecurityConfig's REST rules rely on.
     */
    private void requireScope(Jwt jwt, String requiredScope) {
        String scopeClaim = jwt.getClaimAsString("scope");
        boolean hasScope = scopeClaim != null && Set.of(scopeClaim.split(" ")).contains(requiredScope);
        if (!hasScope) {
            throw new AccessDeniedException("token does not grant the required scope for this operation: " + requiredScope);
        }
    }
}
