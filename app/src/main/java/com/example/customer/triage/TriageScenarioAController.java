package com.example.customer.triage;

import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Incident Triage Lab -- Scenario A (plan-enrollment idempotency).
 *
 * reset/reproduce/state are unauthenticated by design (see
 * SecurityConfig) -- exactly like DemoAppointmentProviderController's
 * synthetic downstream, they operate ONLY on a dedicated, clearly-labeled
 * synthetic customer, never real business data, so anonymous
 * reachability carries no real risk.
 *
 * approve is the one HUMAN APPROVAL REQUIRED action in this scenario:
 * gated by SecurityConfig to require the same ADMIN-scoped token
 * ('SCOPE_admin:read') already used everywhere else ADMIN authority is
 * required in this app -- a USER-role or anonymous caller is rejected
 * before this controller is ever reached.
 */
@RestController
@RequestMapping("/internal/triage/scenario-a")
@Tag(name = "Incident Triage Lab", description = "Scenario A: plan-enrollment idempotency (isolated, synthetic data only)")
public class TriageScenarioAController {

    private final TriageScenarioAService service;

    public TriageScenarioAController(TriageScenarioAService service) {
        this.service = service;
    }

    @PostMapping("/reset")
    public TriageState reset() {
        return service.reset();
    }

    @PostMapping("/reproduce")
    public TriageReproductionResult reproduce() {
        return service.reproduce();
    }

    @GetMapping("/state")
    public TriageState state() {
        return service.state();
    }

    @PostMapping("/approve")
    public TriageState approve() {
        return service.approveFix();
    }
}
