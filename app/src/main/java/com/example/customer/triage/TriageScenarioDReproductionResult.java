package com.example.customer.triage;

/** notificationConsumerRan is always true (it processes first in this
 * replay); billingSyncConsumerRan reveals the defect -- false under the
 * buggy global-by-eventId check (wrongly sees "already processed" from
 * the notification consumer's own row), true once the composite-key fix
 * is applied (its own, independently-scoped idempotency check). */
public record TriageScenarioDReproductionResult(
        String eventId,
        boolean fixApplied,
        boolean notificationConsumerRan,
        boolean billingSyncConsumerRan,
        boolean defectReproduced
) {
}
