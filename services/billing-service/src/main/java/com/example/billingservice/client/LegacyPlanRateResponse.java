package com.example.billingservice.client;

import java.math.BigDecimal;

/** Response body shape for the legacy billing system's real (simulated,
 * see LegacyBillingSystemClient's Javadoc) GET /legacy-billing/plans/{planName}/pricing
 * endpoint. Deliberately minimal, same reasoning as BillingCustomerClient's
 * bodiless existence check: billing-service only needs the rate, not the
 * legacy system's full internal plan record shape. */
public record LegacyPlanRateResponse(String planName, BigDecimal ratePerKwh) {
}
