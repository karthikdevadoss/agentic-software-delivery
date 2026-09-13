package com.example.customer.dto;

import com.example.customer.model.CustomerPreference;
import com.example.customer.model.NotificationChannel;

import java.time.Instant;

/** API contract for preferences — deliberately separate from the JPA
 * entity so the persistence model (customerId, id) can evolve without
 * automatically changing the public API shape. */
public record CustomerPreferenceResponse(
        Long customerId,
        boolean paperlessBilling,
        NotificationChannel notificationChannel,
        Instant updatedAt
) {
    public static CustomerPreferenceResponse from(CustomerPreference preference) {
        return new CustomerPreferenceResponse(
                preference.getCustomerId(),
                preference.isPaperlessBilling(),
                preference.getNotificationChannel(),
                preference.getUpdatedAt()
        );
    }
}
