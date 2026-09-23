package com.example.billingservice.feature;

import org.togglz.core.Feature;
import org.togglz.core.annotation.Label;

/**
 * BL-047/BL-073: real NRG operational patterns, not demo-only toggles.
 * LEGACY_PRICING_BYPASS mirrors the on-call switch NRG flips when the
 * legacy billing system of record is down for its own maintenance --
 * rather than let every enrollment attempt time out against a system
 * known to be unavailable, the switch makes billing-service fail fast
 * and honestly (see ContractPlanService's use of
 * LegacyPlanPricingOutcome.Unavailable, the same outcome a real timeout
 * would produce -- callers never see a different failure shape).
 * MAINTENANCE_WINDOW mirrors the broader SAP monthly maintenance-window
 * duty (see coaching record: "SAP maintenance-window shutdowns... every
 * second Saturday"): reads keep working, writes fail fast with a clear,
 * retryable signal instead of racing a system known to be down.
 */
public enum BillingFeature implements Feature {

    @Label("Bypass the legacy billing system (pricing) -- treat it as unavailable without calling it")
    LEGACY_PRICING_BYPASS,

    @Label("System-wide maintenance window -- writes return 503 with Retry-After, reads keep working")
    MAINTENANCE_WINDOW,
}
