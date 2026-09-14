package com.example.customer.controller;

import com.example.customer.dto.CustomerEmailUpdateRequest;
import com.example.customer.model.Customer;
import com.example.customer.security.WorkspaceAccessGuard;
import com.example.customer.service.CustomerService;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/customers")
@SecurityRequirement(name = "bearerAuth")
public class CustomerController {

    private final CustomerService customerService;
    private final WorkspaceAccessGuard workspaceAccessGuard;

    public CustomerController(CustomerService customerService, WorkspaceAccessGuard workspaceAccessGuard) {
        this.customerService = customerService;
        this.workspaceAccessGuard = workspaceAccessGuard;
    }

    @GetMapping("/{id}")
    public Customer getCustomer(@PathVariable Long id, @AuthenticationPrincipal Jwt jwt) {
        workspaceAccessGuard.assertAccessible(id, jwt);
        return customerService.getById(id);
    }

    @PostMapping
    public ResponseEntity<Customer> createCustomer(@Valid @RequestBody Customer customer) {
        Customer saved = customerService.create(customer);
        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }

    @PutMapping("/{id}")
    public Customer updateEmail(@PathVariable Long id, @Valid @RequestBody CustomerEmailUpdateRequest request,
                                 @AuthenticationPrincipal Jwt jwt) {
        workspaceAccessGuard.assertAccessible(id, jwt);
        return customerService.updateEmail(id, request.email());
    }
}
