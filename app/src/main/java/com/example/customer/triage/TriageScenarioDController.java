package com.example.customer.triage;

import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Incident Triage Lab -- Scenario D (Kafka fan-out idempotency).
 *
 * Same security shape as Scenarios A/B/C: reset/reproduce/state are
 * unauthenticated (operate only on a synthetic eventId, never real
 * business data); approve is the one HUMAN APPROVAL REQUIRED action,
 * gated to an ADMIN-scoped token by SecurityConfig.
 */
@RestController
@RequestMapping("/internal/triage/scenario-d")
@Tag(name = "Incident Triage Lab", description = "Scenario D: Kafka fan-out idempotency (isolated, synthetic event only)")
public class TriageScenarioDController {

    private final TriageScenarioDService service;

    public TriageScenarioDController(TriageScenarioDService service) {
        this.service = service;
    }

    @PostMapping("/reset")
    public TriageScenarioDState reset() {
        return service.reset();
    }

    @PostMapping("/reproduce")
    public TriageScenarioDReproductionResult reproduce() {
        return service.reproduce();
    }

    @GetMapping("/state")
    public TriageScenarioDState state() {
        return service.state();
    }

    @PostMapping("/approve")
    public TriageScenarioDState approve() {
        return service.approveFix();
    }
}
