package com.example.legacybilling.pricing;

import com.example.legacybilling.ratecard.RateCard;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigDecimal;

/**
 * The single operation the billing facade calls:
 *   GET /legacy-billing/plans/{planName}/pricing?customerId={id}
 * Response body must match billing-service's LegacyPlanRateResponse record
 * exactly (planName, ratePerKwh). customerId is REQUIRED (a real legacy
 * rate engine can apply customer-specific eligibility, so the facade always
 * sends it) -- Spring answers 400 when it is missing, which the facade
 * treats as "could not get a real answer" (Unavailable), never as a rate.
 * Unknown plan family -> 404 = PlanNotRecognized on the facade side.
 */
@RestController
public class PlanPricingController {

    private static final Logger log = LoggerFactory.getLogger(PlanPricingController.class);

    private final RateCard rateCard;

    public PlanPricingController(RateCard rateCard) {
        this.rateCard = rateCard;
    }

    public record PlanRateResponse(String planName, BigDecimal ratePerKwh) {
    }

    @GetMapping("/legacy-billing/plans/{planName}/pricing")
    public ResponseEntity<PlanRateResponse> pricing(@PathVariable String planName,
                                                    @RequestParam("customerId") long customerId) {
        return rateCard.rateFor(planName)
                .map(rate -> {
                    log.info("legacy rate card: plan '{}' for customer {} priced at {}", planName, customerId, rate);
                    return ResponseEntity.ok(new PlanRateResponse(planName, rate));
                })
                .orElseGet(() -> {
                    log.info("legacy rate card: plan '{}' not in catalog (customer {})", planName, customerId);
                    return ResponseEntity.notFound().build();
                });
    }
}
