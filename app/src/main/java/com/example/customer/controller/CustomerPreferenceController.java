package com.example.customer.controller;

import com.example.customer.dto.CustomerPreferenceResponse;
import com.example.customer.dto.CustomerPreferenceUpdateRequest;
import com.example.customer.service.CustomerPreferenceService;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
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

    public CustomerPreferenceController(CustomerPreferenceService preferenceService) {
        this.preferenceService = preferenceService;
    }

    @GetMapping
    public CustomerPreferenceResponse getPreferences(@PathVariable Long customerId) {
        return CustomerPreferenceResponse.from(preferenceService.getOrCreateDefault(customerId));
    }

    @PutMapping
    public CustomerPreferenceResponse updatePreferences(
            @PathVariable Long customerId, @Valid @RequestBody CustomerPreferenceUpdateRequest request) {
        return CustomerPreferenceResponse.from(
                preferenceService.update(customerId, request.paperlessBilling(), request.notificationChannel()));
    }
}
