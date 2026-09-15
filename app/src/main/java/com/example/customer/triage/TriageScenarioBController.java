package com.example.customer.triage;

import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Incident Triage Lab -- Scenario B (appointment downstream resilience:
 * wrong retry predicate).
 *
 * Same authorization shape as Scenario A (see TriageScenarioAController):
 * reset/reproduce/state are unauthenticated by design -- this scenario's
 * "buggy" behavior lives entirely in an isolated Retry instance inside
 * TriageScenarioBService, never real business data, so anonymous
 * reachability carries no real risk. approve is the one HUMAN APPROVAL
 * REQUIRED action, admin-gated by SecurityConfig exactly like Scenario A.
 */
@RestController
@RequestMapping("/internal/triage/scenario-b")
@Tag(name = "Incident Triage Lab", description = "Scenario B: appointment downstream resilience (isolated retry predicate, no real customer data)")
public class TriageScenarioBController {

    private final TriageScenarioBService service;

    public TriageScenarioBController(TriageScenarioBService service) {
        this.service = service;
    }

    @PostMapping("/reset")
    public TriageBState reset() {
        return service.reset();
    }

    @PostMapping("/reproduce")
    public TriageBReproductionResult reproduce() {
        return service.reproduce();
    }

    @GetMapping("/state")
    public TriageBState state() {
        return service.state();
    }

    @PostMapping("/approve")
    public TriageBState approve() {
        return service.approveFix();
    }
}
