package com.example.gateway;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

/**
 * ACT-014 / BL-024: api-gateway previously had zero automated tests and
 * was excluded from .github/workflows/ci.yml's microservices matrix
 * (docs/ACTION_QUEUE.json's ACT-014) -- one of the 5 architecturally
 * central pieces the original BL-007 acceptance criteria explicitly
 * named ("an API gateway, service discovery (Eureka)") had no test
 * proving it even starts.
 *
 * Minimum real proof: the full Spring Boot context -- including
 * GatewayRoutesConfig's real RouterFunction bean and the tracing
 * autoconfiguration from BL-014 -- actually comes up on a real (randomly
 * assigned) port with no exception. @ActiveProfiles("test") disables the
 * real Eureka client (see application-test.properties) so this stays a
 * fast, network-independent context-load check, same convention already
 * established by billing-service.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class ApiGatewayApplicationTests {

    @Test
    void contextLoads() {
        // Intentionally empty -- @SpringBootTest already proved the
        // gateway application starts. See class Javadoc.
    }
}
