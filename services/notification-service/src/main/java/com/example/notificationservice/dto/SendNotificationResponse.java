package com.example.notificationservice.dto;

import com.example.notificationservice.model.NotificationChannel;

/** Acknowledgement body for a synchronous POST /notifications/send call. */
public record SendNotificationResponse(
        Long customerId,
        NotificationChannel channel,
        String status
) {
}
