package com.example.customer.triage;

import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Incident Triage Lab -- Scenario C (admin search: Postgres bind-parameter
 * type inference).
 *
 * Same authorization shape as Scenario A/B: reset/reproduce/state are
 * unauthenticated by design -- this scenario's queries run only against
 * dedicated synthetic "Triage Scenario C" customer rows created by
 * reset(), never real customer data or the real admin-search endpoint.
 * approve is the one HUMAN APPROVAL REQUIRED action, admin-gated by
 * SecurityConfig exactly like Scenarios A/B.
 */
@RestController
@RequestMapping("/internal/triage/scenario-c")
@Tag(name = "Incident Triage Lab", description = "Scenario C: admin search Postgres type-inference (isolated synthetic customers only)")
public class TriageScenarioCController {

    private final TriageScenarioCService service;

    public TriageScenarioCController(TriageScenarioCService service) {
        this.service = service;
    }

    @PostMapping("/reset")
    public TriageCState reset() {
        return service.reset();
    }

    @PostMapping("/reproduce")
    public TriageCReproductionResult reproduce() {
        return service.reproduce();
    }

    @GetMapping("/state")
    public TriageCState state() {
        return service.state();
    }

    @PostMapping("/approve")
    public TriageCState approve() {
        return service.approveFix();
    }
}
