package com.example.notificationservice.controller;

import com.example.notificationservice.dto.SendNotificationRequest;
import com.example.notificationservice.dto.SendNotificationResponse;
import com.example.notificationservice.notification.NotificationSenderFactory;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

/**
 * NEW real, separable capability this service has that the monolith did
 * not: a direct, synchronous trigger into the exact same
 * NotificationSenderFactory the async Kafka consumer
 * (ContractPlanEventConsumer) also calls. This demonstrates the real,
 * common hybrid pattern -- the SAME notification capability reachable
 * both via async event consumption (billing-service enrolls a customer ->
 * ContractPlanEnrolled -> Kafka -> this service) AND a direct synchronous
 * API call (an operator/admin tool, a support workflow, a manual resend)
 * -- a genuine, valuable thing to be able to discuss in an interview: when
 * you want both paths into the same capability (async for the normal,
 * decoupled, at-least-once-delivered domain-event flow; sync for a caller
 * that needs to know NOW whether dispatch was accepted, without waiting
 * on -- or coupling itself to -- the eventing pipeline).
 *
 * Deliberately thin: no idempotency ledger here (unlike the Kafka path),
 * because a direct synchronous caller already gets a real HTTP
 * success/failure signal for THIS specific call and is expected to retry
 * itself if needed -- the idempotency problem the ProcessedEvent ledger
 * solves is specific to at-least-once, fire-and-forget async delivery.
 */
@RestController
public class NotificationController {

    private final NotificationSenderFactory notificationSenderFactory;

    public NotificationController(NotificationSenderFactory notificationSenderFactory) {
        this.notificationSenderFactory = notificationSenderFactory;
    }

    @PostMapping("/notifications/send")
    public ResponseEntity<SendNotificationResponse> send(@Valid @RequestBody SendNotificationRequest request) {
        notificationSenderFactory.getSender(request.channel()).send(request.customerId(), request.message());
        return ResponseEntity.ok(new SendNotificationResponse(request.customerId(), request.channel(), "dispatched"));
    }
}
