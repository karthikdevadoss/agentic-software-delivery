package com.example.notificationservice.dto;

import com.example.notificationservice.model.NotificationChannel;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/**
 * Request body for the direct, synchronous POST /notifications/send
 * trigger -- see NotificationController's Javadoc for why this endpoint
 * exists alongside the async Kafka consumption path.
 */
public record SendNotificationRequest(
        @NotNull Long customerId,
        @NotNull NotificationChannel channel,
        @NotBlank String message
) {
}
