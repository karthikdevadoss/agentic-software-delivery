package com.example.legacybilling.ratecard;

import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;

/**
 * The legacy system's authoritative rate card, keyed by PLAN FAMILY.
 * A real legacy rating engine prices a plan by its product family and
 * tariff, not by the free-text name a modern front end sends -- so the
 * lookup here is "which family does this plan name belong to", which is
 * also why the facade must never trust the caller-submitted rate.
 *
 * Families and rates are fixed test-tariff values (USD per kWh); they are
 * a realistic stand-in, not a claim about any real utility's prices.
 */
@Component
public class RateCard {

    private final Map<String, BigDecimal> familyRates = new LinkedHashMap<>();

    public RateCard() {
        familyRates.put("residential", new BigDecimal("0.1825"));
        familyRates.put("business", new BigDecimal("0.1650"));
        familyRates.put("prepay", new BigDecimal("0.1990"));
        familyRates.put("green", new BigDecimal("0.2100"));
    }

    /** Empty when the plan name matches no family the legacy system knows. */
    public Optional<BigDecimal> rateFor(String planName) {
        if (planName == null || planName.isBlank()) {
            return Optional.empty();
        }
        String normalized = planName.toLowerCase(Locale.ROOT);
        return familyRates.entrySet().stream()
                .filter(e -> normalized.contains(e.getKey()))
                .map(Map.Entry::getValue)
                .findFirst();
    }
}
