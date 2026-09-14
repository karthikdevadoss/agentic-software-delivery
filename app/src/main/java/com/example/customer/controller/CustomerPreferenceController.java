package com.example.customer.controller;

import com.example.customer.dto.CustomerPreferenceResponse;
import com.example.customer.dto.CustomerPreferenceUpdateRequest;
import com.example.customer.security.WorkspaceAccessGuard;
import com.example.customer.service.CustomerPreferenceService;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/customers/{customerId}/preferences")
@Tag(name = "Customer Preferences", description = "Paperless billing and notification-channel preferences")
@SecurityRequirement(name = "bearerAuth")
public class CustomerPreferenceController {

    private final CustomerPreferenceService preferenceService;
    private final WorkspaceAccessGuard workspaceAccessGuard;

    public CustomerPreferenceController(CustomerPreferenceService preferenceService, WorkspaceAccessGuard workspaceAccessGuard) {
        this.preferenceService = preferenceService;
        this.workspaceAccessGuard = workspaceAccessGuard;
    }

    @GetMapping
    public CustomerPreferenceResponse getPreferences(@PathVariable Long customerId, @AuthenticationPrincipal Jwt jwt) {
        workspaceAccessGuard.assertAccessible(customerId, jwt);
        return CustomerPreferenceResponse.from(preferenceService.getOrCreateDefault(customerId));
    }

    @PutMapping
    public CustomerPreferenceResponse updatePreferences(
            @PathVariable Long customerId, @Valid @RequestBody CustomerPreferenceUpdateRequest request,
            @AuthenticationPrincipal Jwt jwt) {
        workspaceAccessGuard.assertAccessible(customerId, jwt);
        return CustomerPreferenceResponse.from(
                preferenceService.update(customerId, request.paperlessBilling(), request.notificationChannel()));
    }
}
