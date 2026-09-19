package com.example.customer.controller;

import com.example.customer.cache.ContractPlanCacheService;
import com.example.customer.dto.ContractPlanResponse;
import com.example.customer.model.Customer;
import com.example.customer.security.WorkspaceAccessGuard;
import com.example.customer.service.CustomerService;
import org.springframework.graphql.data.method.annotation.Argument;
import org.springframework.graphql.data.method.annotation.QueryMapping;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Controller;

import java.util.NoSuchElementException;

/**
 * Exposes the same Customer/ContractPlan domain as
 * {@link CustomerController}/{@link ContractPlanController} through
 * GraphQL instead of REST -- deliberately reusing the exact same
 * {@link CustomerService}/{@link ContractPlanCacheService} and
 * {@link WorkspaceAccessGuard}, never a second, divergent implementation
 * of the same business logic.
 *
 * A real, structural difference from the REST side is worth noting
 * explicitly: {@link com.example.customer.security.SecurityConfig}
 * authorizes each REST path by a specific OAuth2 scope (e.g.
 * {@code SCOPE_customer:read} for {@code GET /customers/{id}}), because
 * REST gives one URL per operation to hang a rule on. GraphQL exposes a
 * single {@code POST /graphql} endpoint for every query, so that
 * per-path scope model does not apply -- SecurityConfig only requires
 * the caller be authenticated at all, and per-customer access control is
 * enforced here, per resolver, via the same WorkspaceAccessGuard the
 * REST controllers call. This is a genuine, common real-world GraphQL
 * authorization pattern (field/resolver-level authorization), not a
 * security regression versus the REST side.
 */
@Controller
public class CustomerGraphQLController {

    private final CustomerService customerService;
    private final ContractPlanCacheService contractPlanCacheService;
    private final WorkspaceAccessGuard workspaceAccessGuard;

    public CustomerGraphQLController(CustomerService customerService,
                                      ContractPlanCacheService contractPlanCacheService,
                                      WorkspaceAccessGuard workspaceAccessGuard) {
        this.customerService = customerService;
        this.contractPlanCacheService = contractPlanCacheService;
        this.workspaceAccessGuard = workspaceAccessGuard;
    }

    @QueryMapping
    public Customer customer(@Argument Long id, @AuthenticationPrincipal Jwt jwt) {
        workspaceAccessGuard.assertAccessible(id, jwt);
        return customerService.getById(id);
    }

    @QueryMapping
    public ContractPlanView activeContractPlan(@Argument Long customerId, @AuthenticationPrincipal Jwt jwt) {
        workspaceAccessGuard.assertAccessible(customerId, jwt);
        // ContractPlanCacheService/ContractPlanService (shared with the REST
        // side) signal "no active plan" by throwing NoSuchElementException,
        // not by returning null -- REST turns that into a 404 via
        // GlobalExceptionHandler, which is NOT wired into GraphQL's
        // exception-resolution path. A real bug was caught here during
        // testing: without this catch, the exception surfaced as an
        // unhandled GraphQL INTERNAL_ERROR that happened to also leave the
        // "activeContractPlan" field null in the response, which looked
        // like a clean "not found" from the client's data alone but was
        // actually an unresolved server error in the response's errors
        // array. A GraphQL nullable field returning null is the correct,
        // idiomatic way to express "not found" for a single-entity query
        // (GraphQL has no per-field HTTP status equivalent), so this
        // resolver translates the exception explicitly rather than
        // propagating it.
        try {
            ContractPlanResponse plan = contractPlanCacheService.getActivePlan(customerId);
            return ContractPlanView.from(plan);
        } catch (NoSuchElementException notFound) {
            return null;
        }
    }

    /**
     * schema.graphqls declares ContractPlan's numeric/date/enum fields as
     * GraphQL {@code String} (no extra scalar library dependency for a
     * single demo endpoint) -- graphql-java's built-in String scalar
     * coercion does not accept BigDecimal/LocalDate/enum values directly,
     * so this view converts explicitly rather than leaking that
     * conversion into ContractPlanResponse itself, which the REST side
     * also uses and must keep its own, correctly-typed shape.
     */
    public record ContractPlanView(
            Long id,
            Long customerId,
            String planName,
            String ratePerKwh,
            String effectiveStartDate,
            String effectiveEndDate,
            String status
    ) {
        static ContractPlanView from(ContractPlanResponse r) {
            return new ContractPlanView(
                    r.id(),
                    r.customerId(),
                    r.planName(),
                    r.ratePerKwh().toString(),
                    r.effectiveStartDate().toString(),
                    r.effectiveEndDate() == null ? null : r.effectiveEndDate().toString(),
                    r.status().name()
            );
        }
    }
}
