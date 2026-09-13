package com.example.customer.dto;

import com.example.customer.model.NotificationChannel;
import jakarta.validation.constraints.NotNull;

public record CustomerPreferenceUpdateRequest(
        @NotNull(message = "paperlessBilling must not be null") Boolean paperlessBilling,
        @NotNull(message = "notificationChannel must not be null") NotificationChannel notificationChannel
) {
}
