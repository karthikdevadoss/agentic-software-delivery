package com.example.customer.cache;

import com.example.customer.dto.ContractPlanEnrollRequest;
import com.example.customer.model.Customer;
import com.example.customer.security.DemoJwtIssuer;
import com.example.customer.testsupport.AuthTestSupport;
import io.micrometer.core.instrument.MeterRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * REAL Redis proof, mirroring PostgresFlywayIntegrationTest's pattern:
 * {@code disabledWithoutDocker = true} skips cleanly on this dev machine
 * (no Docker installed here -- see docs/LESSONS.md), and runs for real on
 * GitHub Actions. Proves genuine cache-aside behavior against a real
 * Redis container, not mocks: miss-then-fill, hit avoiding a second
 * database read's cache-write, a real TTL set on the key, and eviction
 * after enroll() genuinely removing the stale entry.
 *
 * The "Redis unavailable" fallback path is proven separately and
 * constantly by every OTHER controller test in this project: no local
 * Redis exists on this dev machine at all, so every one of those tests
 * already exercises the real fallback-to-database path on every run
 * (see ContractPlanCacheService's WARN logs during any local test run).
 */
@Testcontainers(disabledWithoutDocker = true)
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ContractPlanCacheIntegrationTest {

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

    @Autowired
    private DemoJwtIssuer demoJwtIssuer;

    @Autowired
    private RedisTemplate<String, String> redisTemplate;

    @Autowired
    private MeterRegistry meterRegistry;

    private org.springframework.web.client.RestTemplate restTemplate;

    @BeforeEach
    void setUp() {
        restTemplate = AuthTestSupport.authenticatedRestTemplate(demoJwtIssuer);
    }

    private String url(String path) {
        return "http://localhost:" + port + path;
    }

    private double hitCount() {
        var counter = meterRegistry.find("cache.requests").tag("cache", "active-plan").tag("result", "hit").counter();
        return counter == null ? 0.0 : counter.count();
    }

    private double missCount() {
        var counter = meterRegistry.find("cache.requests").tag("cache", "active-plan").tag("result", "miss").counter();
        return counter == null ? 0.0 : counter.count();
    }

    @Test
    void firstRead_isAMiss_andFillsTheCacheWithARealTtl() {
        Long customerId = enrollCustomerWithPlan("Cache Miss Test", "First Plan");
        String key = "contract-plan:active:" + customerId;

        double missesBefore = missCount();
        ContractPlanResponseLike first = getActivePlan(customerId);
        assertThat(first.planName).isEqualTo("First Plan");
        assertThat(missCount()).isEqualTo(missesBefore + 1);

        String cachedRaw = redisTemplate.opsForValue().get(key);
        assertThat(cachedRaw).isNotNull().contains("First Plan");

        Long ttlSeconds = redisTemplate.getExpire(key, java.util.concurrent.TimeUnit.SECONDS);
        assertThat(ttlSeconds).isGreaterThan(0).isLessThanOrEqualTo(60);
    }

    @Test
    void secondRead_isARealCacheHit() {
        Long customerId = enrollCustomerWithPlan("Cache Hit Test", "Hit Plan");

        getActivePlan(customerId); // miss, fills cache
        double hitsBefore = hitCount();
        ContractPlanResponseLike second = getActivePlan(customerId); // real hit

        assertThat(second.planName).isEqualTo("Hit Plan");
        assertThat(hitCount()).isEqualTo(hitsBefore + 1);
    }

    @Test
    void enroll_evictsTheCache_soTheNextReadSeesTheNewPlanNotAStaleOne() {
        Long customerId = enrollCustomerWithPlan("Eviction Test", "Old Plan");
        getActivePlan(customerId); // cache now holds "Old Plan"

        restTemplate.postForEntity(url("/customers/" + customerId + "/plan"),
                new ContractPlanEnrollRequest("New Plan", new BigDecimal("0.10"), LocalDate.now().plusDays(1)), Object.class);

        String key = "contract-plan:active:" + customerId;
        assertThat(redisTemplate.opsForValue().get(key)).isNull(); // evicted, not stale

        ContractPlanResponseLike afterEnroll = getActivePlan(customerId);
        assertThat(afterEnroll.planName).isEqualTo("New Plan"); // never served the stale cached value
    }

    private record ContractPlanResponseLike(String planName) {
    }

    @SuppressWarnings("unchecked")
    private ContractPlanResponseLike getActivePlan(Long customerId) {
        Map<String, Object> body = restTemplate.getForObject(url("/customers/" + customerId + "/plan"), Map.class);
        return new ContractPlanResponseLike((String) body.get("planName"));
    }

    private Long enrollCustomerWithPlan(String customerName, String planName) {
        Customer created = restTemplate.postForObject(
                url("/customers"), new Customer(customerName, customerName.toLowerCase().replace(" ", ".") + "@example.com"), Customer.class);
        restTemplate.postForEntity(url("/customers/" + created.getId() + "/plan"),
                new ContractPlanEnrollRequest(planName, new BigDecimal("0.15"), LocalDate.now()), Object.class);
        return created.getId();
    }
}
