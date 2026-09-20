package com.example.customerservice.dto;

import com.example.customerservice.model.NotificationChannel;

import java.time.Instant;

/** API contract for preferences -- deliberately separate from the JPA
 * entity so the persistence model (customerId, id) can evolve without
 * automatically changing the public API shape. Mapped from
 * {@code CustomerPreference} by {@link com.example.customerservice.mapper.CustomerPreferenceMapper}
 * (BL-037) -- this record no longer carries its own manual mapping code. */
public record CustomerPreferenceResponse(
        Long customerId,
        boolean paperlessBilling,
        NotificationChannel notificationChannel,
        Instant updatedAt
) {
}
