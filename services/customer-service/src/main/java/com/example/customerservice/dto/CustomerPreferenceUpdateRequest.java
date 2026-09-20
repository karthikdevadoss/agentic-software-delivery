package com.example.customerservice.dto;

import com.example.customerservice.model.NotificationChannel;
import jakarta.validation.constraints.NotNull;

public record CustomerPreferenceUpdateRequest(
        @NotNull(message = "paperlessBilling must not be null") Boolean paperlessBilling,
        @NotNull(message = "notificationChannel must not be null") NotificationChannel notificationChannel
) {
}
