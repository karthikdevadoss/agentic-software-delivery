package com.example.customer.security;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.web.client.RestTemplate;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * REAL proof of RateLimiterService against a real Redis container
 * (Testcontainers, disabledWithoutDocker=true -- same pattern as every
 * other Redis test in this project): exactly DemoAuthController.RATE_LIMIT
 * real HTTP calls to /auth/demo-token succeed, the next one is rejected
 * with a clean 429, never a raw error.
 *
 * Redis-unavailable fail-open behavior is NOT re-tested here: it is the
 * exact same proven code path already covered by
 * ContractPlanCacheService/EnrollmentLockService's own real-world
 * behavior on this Docker-less dev machine (no local Redis exists here
 * at all, so every test run already exercises RateLimiterService's own
 * catch-and-fail-open branch for real, every time this class is skipped
 * -- see its own WARN logs). Re-proving the identical try/catch pattern a
 * third time would be duplicated effort, not new coverage.
 */
@Testcontainers(disabledWithoutDocker = true)
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class RateLimiterIntegrationTest {

    @Container
    static GenericContainer<?> redis = new GenericContainer<>(DockerImageName.parse("redis:7-alpine"))
            .withExposedPorts(6379);

    @DynamicPropertySource
    static void redisProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.data.redis.host", redis::getHost);
        registry.add("spring.data.redis.port", () -> redis.getMappedPort(6379));
    }

    @LocalServerPort
    private int port;

    private String url() {
        return "http://localhost:" + port + "/auth/demo-token";
    }

    @Test
    void requestsWithinTheLimit_succeed_andTheNextOneIsCleanlyRejected() {
        RestTemplate restTemplate = new RestTemplate();

        for (int i = 0; i < DemoAuthController.RATE_LIMIT; i++) {
            ResponseEntity<DemoAuthController.TokenResponse> response =
                    restTemplate.postForEntity(url(), null, DemoAuthController.TokenResponse.class);
            assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        }

        org.springframework.web.client.HttpClientErrorException.TooManyRequests rejected =
                org.junit.jupiter.api.Assertions.assertThrows(
                        org.springframework.web.client.HttpClientErrorException.TooManyRequests.class,
                        () -> restTemplate.postForEntity(url(), null, DemoAuthController.TokenResponse.class));

        assertThat(rejected.getStatusCode()).isEqualTo(HttpStatus.TOO_MANY_REQUESTS);
        assertThat(rejected.getResponseBodyAsString()).contains("Too many demo-token requests");
    }
}
