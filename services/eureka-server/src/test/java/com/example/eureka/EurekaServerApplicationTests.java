package com.example.eureka;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

/**
 * ACT-014 / BL-024: eureka-server previously had zero automated tests and
 * was excluded from .github/workflows/ci.yml's microservices matrix
 * (docs/ACTION_QUEUE.json's ACT-014, a real escaped defect found by an
 * independent qa-evaluator pass retroactively re-verifying BL-007 -- one
 * of the 5 architecturally central pieces the original BL-007 acceptance
 * criteria explicitly named had no test proving it even starts).
 *
 * Minimum real proof: the full Spring Boot context -- including
 * @EnableEurekaServer's autoconfiguration -- actually comes up on a real
 * (randomly assigned) port with no exception. A context that fails to
 * load throws during this test's setup, which is exactly what this test
 * exists to catch; it needs no assertion body of its own.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class EurekaServerApplicationTests {

    @Test
    void contextLoads() {
        // Intentionally empty -- @SpringBootTest already proved the
        // registry application starts. See class Javadoc.
    }
}
