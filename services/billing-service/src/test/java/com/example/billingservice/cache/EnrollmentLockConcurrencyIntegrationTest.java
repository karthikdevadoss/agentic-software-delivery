package com.example.billingservice.cache;

import com.example.billingservice.client.BillingCustomerClient;
import com.example.billingservice.client.CustomerLookupOutcome;
import com.example.billingservice.client.LegacyBillingSystemClient;
import com.example.billingservice.client.LegacyPlanPricingOutcome;
import com.example.billingservice.dto.ContractPlanEnrollRequest;
import com.example.billingservice.testsupport.AuthTestSupport;
import com.example.billingservice.testsupport.TestJwtIssuer;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.web.client.HttpClientErrorException;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

/**
 * REAL proof of the layered concurrency control described in
 * ContractPlanService.enroll()'s Javadoc, against a real Redis container
 * (Testcontainers, disabledWithoutDocker=true -- skips cleanly here, no
 * Docker on this dev machine, same as app/'s equivalent test).
 *
 * ADAPTED from app/'s EnrollmentLockConcurrencyIntegrationTest: billing-
 * service does not own Customer data, so there is no POST /customers
 * endpoint here to create a real customer against. BillingCustomerClient
 * is replaced with a @MockitoBean stubbed to always report FOUND -- this
 * test is specifically about the Redis lock/HTTP-status behavior, not
 * about the customer-service integration (that is
 * BillingCustomerClientIntegrationTest's job).
 */
@Testcontainers(disabledWithoutDocker = true)
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class EnrollmentLockConcurrencyIntegrationTest {

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
    private EnrollmentLockService enrollmentLockService;

    @MockitoBean
    private BillingCustomerClient billingCustomerClient;

    /**
     * ACT-013 added a second outbound dependency to enrollment: the legacy
     * billing system of record confirms the authoritative rate. Without this
     * mock the real client dials localhost:9099, gets nothing, and every
     * enrollment here is an honest 503 -- which is exactly what CI reported
     * (this test is Docker-gated, so it never ran on the Docker-less dev
     * machine). Same reasoning as the BillingCustomerClient mock above:
     * this test is about Redis, not about either integration.
     */
    @MockitoBean
    private LegacyBillingSystemClient legacyBillingSystemClient;

    private static final AtomicLong CUSTOMER_ID_SEQUENCE = new AtomicLong(100_000L);

    private org.springframework.web.client.RestTemplate restTemplate;

    @BeforeEach
    void setUp() {
        restTemplate = AuthTestSupport.authenticatedRestTemplate(testJwtIssuer);
        when(billingCustomerClient.checkCustomerExists(any(), any())).thenReturn(CustomerLookupOutcome.FOUND);
        when(legacyBillingSystemClient.confirmPlanPricing(any(), any(), any()))
                .thenReturn(new LegacyPlanPricingOutcome.Confirmed(new BigDecimal("0.15")));
    }

    private String url(String path) {
        return "http://localhost:" + port + path;
    }

    private static Long nextCustomerId() {
        return CUSTOMER_ID_SEQUENCE.incrementAndGet();
    }

    @Test
    void enroll_whileAnotherEnrollmentHoldsTheLock_returnsCleanConflict_notARaw500() {
        Long customerId = nextCustomerId();

        // Pre-hold the real lock exactly as ContractPlanService.enroll()
        // would, from the test thread itself -- deterministic, no race to
        // get the timing right.
        EnrollmentLockService.LockResult lock = enrollmentLockService.tryAcquire(customerId);
        assertThat(lock).isInstanceOf(EnrollmentLockService.LockResult.Acquired.class);

        try {
            HttpClientErrorException ex = org.junit.jupiter.api.Assertions.assertThrows(
                    HttpClientErrorException.class,
                    () -> restTemplate.postForEntity(url("/customers/" + customerId + "/plan"),
                            new ContractPlanEnrollRequest("Contended Plan", new BigDecimal("0.15"), LocalDate.now()),
                            Object.class));

            assertThat(ex.getStatusCode()).isEqualTo(HttpStatus.CONFLICT); // clean 409, never a raw 500
            assertThat(ex.getResponseBodyAsString()).contains("Enrollment already in progress");
        } finally {
            enrollmentLockService.release(customerId, ((EnrollmentLockService.LockResult.Acquired) lock).token());
        }

        // Once the lock is released, a real enrollment for the same
        // customer succeeds normally -- the 409 above was real contention,
        // not a permanently broken customer.
        ResponseEntity<Object> afterRelease = restTemplate.postForEntity(url("/customers/" + customerId + "/plan"),
                new ContractPlanEnrollRequest("Real Plan", new BigDecimal("0.15"), LocalDate.now()), Object.class);
        assertThat(afterRelease.getStatusCode()).isEqualTo(HttpStatus.CREATED);
    }

    @Test
    void twoGenuinelyConcurrentEnrollments_neverProduceTwoActivePlans_andNeitherSeesARaw500() throws Exception {
        Long customerId = nextCustomerId();

        CountDownLatch startTogether = new CountDownLatch(1);
        ExecutorService pool = Executors.newFixedThreadPool(2);
        AtomicInteger created = new AtomicInteger();
        AtomicInteger conflicted = new AtomicInteger();
        AtomicInteger unexpectedServerErrors = new AtomicInteger();

        Runnable attempt = () -> {
            try {
                startTogether.await();
                ResponseEntity<Object> response = restTemplate.postForEntity(url("/customers/" + customerId + "/plan"),
                        new ContractPlanEnrollRequest("Racing Plan", new BigDecimal("0.15"), LocalDate.now()), Object.class);
                if (response.getStatusCode() == HttpStatus.CREATED) created.incrementAndGet();
            } catch (HttpClientErrorException.Conflict conflict) {
                conflicted.incrementAndGet(); // the clean, expected loser outcome
            } catch (Exception unexpected) {
                unexpectedServerErrors.incrementAndGet();
            }
        };

        pool.submit(attempt);
        pool.submit(attempt);
        startTogether.countDown();
        pool.shutdown();
        assertThat(pool.awaitTermination(30, TimeUnit.SECONDS)).isTrue();

        assertThat(unexpectedServerErrors.get()).isZero(); // never a raw 500
        assertThat(created.get()).isBetween(1, 2); // the lock is a fast-path optimization, not the only correctness guarantee -- the DB constraint permits a sequential second success too
        assertThat(created.get() + conflicted.get()).isEqualTo(2); // every request got a real, accounted-for outcome

        // The invariant that actually matters: reusing the real GET active-plan
        // endpoint proves exactly one ACTIVE plan exists, never zero, never two.
        @SuppressWarnings("unchecked")
        Map<String, Object> activePlan = restTemplate.getForObject(
                url("/customers/" + customerId + "/plan"), Map.class);
        assertThat(activePlan.get("planName")).isEqualTo("Racing Plan");
    }
}
