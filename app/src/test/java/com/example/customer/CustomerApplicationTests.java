package com.example.customer;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

/**
 * Smoke test: the real Spring application context (controller, service,
 * repository, JPA/H2 wiring) must actually start. This is the first
 * automated test this project has ever had for the Customer app — see
 * agent/web_server.py's TESTING — NOT CONFIGURED state, which this and
 * the tests alongside it now begin to close.
 */
@SpringBootTest
class CustomerApplicationTests {

    @Test
    void contextLoads() {
        // Intentionally empty: a failure here means the real Spring
        // context (entity mappings, repository, service, controller
        // wiring) could not start — the most basic real regression this
        // project can detect.
    }
}
