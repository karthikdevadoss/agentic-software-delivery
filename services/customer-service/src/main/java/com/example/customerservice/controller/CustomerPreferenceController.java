package com.example.customerservice.controller;

import com.example.customerservice.dto.CustomerPreferenceResponse;
import com.example.customerservice.dto.CustomerPreferenceUpdateRequest;
import com.example.customerservice.mapper.CustomerPreferenceMapper;
import com.example.customerservice.security.WorkspaceAccessGuard;
import com.example.customerservice.service.CustomerPreferenceService;
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
public class CustomerPreferenceController {

    private final CustomerPreferenceService preferenceService;
    private final WorkspaceAccessGuard workspaceAccessGuard;
    private final CustomerPreferenceMapper preferenceMapper;

    public CustomerPreferenceController(CustomerPreferenceService preferenceService, WorkspaceAccessGuard workspaceAccessGuard, CustomerPreferenceMapper preferenceMapper) {
        this.preferenceService = preferenceService;
        this.workspaceAccessGuard = workspaceAccessGuard;
        this.preferenceMapper = preferenceMapper;
    }

    @GetMapping
    public CustomerPreferenceResponse getPreferences(@PathVariable Long customerId, @AuthenticationPrincipal Jwt jwt) {
        workspaceAccessGuard.assertAccessible(customerId, jwt);
        return preferenceMapper.toResponse(preferenceService.getOrCreateDefault(customerId));
    }

    @PutMapping
    public CustomerPreferenceResponse updatePreferences(
            @PathVariable Long customerId, @Valid @RequestBody CustomerPreferenceUpdateRequest request,
            @AuthenticationPrincipal Jwt jwt) {
        workspaceAccessGuard.assertAccessible(customerId, jwt);
        return preferenceMapper.toResponse(
                preferenceService.update(customerId, request.paperlessBilling(), request.notificationChannel()));
    }
}
