package com.example.customer.cache;

import com.example.customer.dto.ContractPlanEnrollRequest;
import com.example.customer.model.Customer;
import com.example.customer.security.DemoJwtIssuer;
import com.example.customer.testsupport.AuthTestSupport;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
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

import static org.assertj.core.api.Assertions.assertThat;

/**
 * REAL proof of the layered concurrency control described in
 * ContractPlanService.enroll()'s Javadoc, against a real Redis container
 * (Testcontainers, disabledWithoutDocker=true -- same pattern as
 * ContractPlanCacheIntegrationTest).
 *
 * Two tests, deliberately different in style:
 * 1. A DETERMINISTIC test that pre-holds the lock from the test thread
 *    itself (no wall-clock race to get right) and proves the HTTP layer
 *    returns a clean 409 -- not a 500, and not a silently-accepted request.
 * 2. A genuinely CONCURRENT test (two real threads, started together via a
 *    CountDownLatch) that proves the end-to-end invariant that actually
 *    matters under real load: the customer ends up with EXACTLY ONE active
 *    plan, and neither request receives an unguided 500 -- without
 *    asserting exactly which of the two "won", since that outcome is
 *    legitimately timing-dependent and asserting it would make the test
 *    flaky for no real benefit.
 */
@Testcontainers(disabledWithoutDocker = true)
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
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
    private DemoJwtIssuer demoJwtIssuer;

    @Autowired
    private EnrollmentLockService enrollmentLockService;

    private org.springframework.web.client.RestTemplate restTemplate;

    @BeforeEach
    void setUp() {
        restTemplate = AuthTestSupport.authenticatedRestTemplate(demoJwtIssuer);
    }

    private String url(String path) {
        return "http://localhost:" + port + path;
    }

    private Customer createCustomer(String name) {
        return restTemplate.postForObject(
                url("/customers"), new Customer(name, name.toLowerCase().replace(" ", ".") + "@example.com"), Customer.class);
    }

    @Test
    void enroll_whileAnotherEnrollmentHoldsTheLock_returnsCleanConflict_notARaw500() {
        Customer customer = createCustomer("Lock Contention Test");

        // Pre-hold the real lock exactly as ContractPlanService.enroll()
        // would, from the test thread itself -- deterministic, no race to
        // get the timing right.
        EnrollmentLockService.LockResult lock = enrollmentLockService.tryAcquire(customer.getId());
        assertThat(lock).isInstanceOf(EnrollmentLockService.LockResult.Acquired.class);

        try {
            HttpClientErrorException ex = org.junit.jupiter.api.Assertions.assertThrows(
                    HttpClientErrorException.class,
                    () -> restTemplate.postForEntity(url("/customers/" + customer.getId() + "/plan"),
                            new ContractPlanEnrollRequest("Contended Plan", new BigDecimal("0.15"), LocalDate.now()),
                            Object.class));

            assertThat(ex.getStatusCode()).isEqualTo(HttpStatus.CONFLICT); // clean 409, never a raw 500
            assertThat(ex.getResponseBodyAsString()).contains("Enrollment already in progress");
        } finally {
            enrollmentLockService.release(customer.getId(), ((EnrollmentLockService.LockResult.Acquired) lock).token());
        }

        // Once the lock is released, a real enrollment for the same
        // customer succeeds normally -- the 409 above was real contention,
        // not a permanently broken customer.
        ResponseEntity<Object> afterRelease = restTemplate.postForEntity(url("/customers/" + customer.getId() + "/plan"),
                new ContractPlanEnrollRequest("Real Plan", new BigDecimal("0.15"), LocalDate.now()), Object.class);
        assertThat(afterRelease.getStatusCode()).isEqualTo(HttpStatus.CREATED);
    }

    @Test
    void twoGenuinelyConcurrentEnrollments_neverProduceTwoActivePlans_andNeitherSeesARaw500() throws Exception {
        Customer customer = createCustomer("Real Concurrency Test");

        CountDownLatch startTogether = new CountDownLatch(1);
        ExecutorService pool = Executors.newFixedThreadPool(2);
        AtomicInteger created = new AtomicInteger();
        AtomicInteger conflicted = new AtomicInteger();
        AtomicInteger unexpectedServerErrors = new AtomicInteger();

        Runnable attempt = () -> {
            try {
                startTogether.await();
                ResponseEntity<Object> response = restTemplate.postForEntity(url("/customers/" + customer.getId() + "/plan"),
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
        // endpoint (backed by findByCustomerIdAndStatus, which the DB's own
        // uq_contract_plan_one_active_per_customer constraint guarantees can
        // never match more than one row) -- a 200 here with a real plan proves
        // exactly one ACTIVE plan exists, never zero, never two.
        @SuppressWarnings("unchecked")
        Map<String, Object> activePlan = restTemplate.getForObject(
                url("/customers/" + customer.getId() + "/plan"), Map.class);
        assertThat(activePlan.get("planName")).isEqualTo("Racing Plan");
    }
}
