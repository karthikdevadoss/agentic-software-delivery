package com.example.billingservice.cache;

import com.example.billingservice.client.BillingCustomerClient;
import com.example.billingservice.client.CustomerLookupOutcome;
import com.example.billingservice.dto.ContractPlanEnrollRequest;
import com.example.billingservice.testsupport.AuthTestSupport;
import com.example.billingservice.testsupport.TestJwtIssuer;
import io.micrometer.core.instrument.MeterRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

/**
 * REAL Redis proof, mirroring app/'s ContractPlanCacheIntegrationTest
 * pattern: {@code disabledWithoutDocker = true} skips cleanly on this dev
 * machine (no Docker installed here), and would run for real in CI.
 * Proves genuine cache-aside behavior against a real Redis container, not
 * mocks: miss-then-fill, hit avoiding a second database read's cache-
 * write, a real TTL set on the key, and eviction after enroll() genuinely
 * removing the stale entry.
 *
 * ADAPTED from app/'s version: billing-service does not own Customer data
 * (no POST /customers endpoint exists here), so BillingCustomerClient is
 * replaced with a @MockitoBean stubbed to always report FOUND -- this test
 * is about the cache, not the customer-service integration.
 */
@Testcontainers(disabledWithoutDocker = true)
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
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
    private TestJwtIssuer testJwtIssuer;

    @Autowired
    private RedisTemplate<String, String> redisTemplate;

    @Autowired
    private MeterRegistry meterRegistry;

    @MockitoBean
    private BillingCustomerClient billingCustomerClient;

    private static final AtomicLong CUSTOMER_ID_SEQUENCE = new AtomicLong(200_000L);

    private org.springframework.web.client.RestTemplate restTemplate;

    @BeforeEach
    void setUp() {
        restTemplate = AuthTestSupport.authenticatedRestTemplate(testJwtIssuer);
        when(billingCustomerClient.checkCustomerExists(any())).thenReturn(CustomerLookupOutcome.FOUND);
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
        Long customerId = enrollCustomerWithPlan("First Plan");
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
        Long customerId = enrollCustomerWithPlan("Hit Plan");

        getActivePlan(customerId); // miss, fills cache
        double hitsBefore = hitCount();
        ContractPlanResponseLike second = getActivePlan(customerId); // real hit

        assertThat(second.planName).isEqualTo("Hit Plan");
        assertThat(hitCount()).isEqualTo(hitsBefore + 1);
    }

    @Test
    void enroll_evictsTheCache_soTheNextReadSeesTheNewPlanNotAStaleOne() {
        Long customerId = enrollCustomerWithPlan("Old Plan");
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

    private Long enrollCustomerWithPlan(String planName) {
        Long customerId = CUSTOMER_ID_SEQUENCE.incrementAndGet();
        restTemplate.postForEntity(url("/customers/" + customerId + "/plan"),
                new ContractPlanEnrollRequest(planName, new BigDecimal("0.15"), LocalDate.now()), Object.class);
        return customerId;
    }
}
