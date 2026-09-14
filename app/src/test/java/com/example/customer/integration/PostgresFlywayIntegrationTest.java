package com.example.customer.integration;

import com.example.customer.dto.ContractPlanEnrollRequest;
import com.example.customer.model.Customer;
import com.example.customer.model.NotificationChannel;
import com.example.customer.security.DemoJwtIssuer;
import com.example.customer.testsupport.AuthTestSupport;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.web.client.RestTemplate;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.math.BigDecimal;
import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * REAL Postgres + Flyway proof — the "very high priority" requirement
 * from the overnight engineering task. Runs the actual `postgres` Spring
 * profile (Flyway-managed schema, ddl-auto=validate, PostgreSQL dialect)
 * against a real, ephemeral PostgreSQL container, not H2.
 *
 * {@code disabledWithoutDocker = true} makes this test class SKIP (not
 * fail) when no Docker daemon is available — an honest, standard
 * Testcontainers pattern, not a workaround: this exact sandbox has no
 * Docker installed (verified via `docker --version` failing), so this
 * class was written but NOT executed in this development session. It IS
 * expected to run for real in CI (GitHub Actions runners include Docker)
 * — see .github/workflows/ci.yml, which runs `mvn test` including this
 * class, and docs/PROJECT_STATE.json for the real CI run result.
 */
@Testcontainers(disabledWithoutDocker = true)
// spring.flyway.enabled=true is asserted explicitly here as belt-and-
// suspenders on top of application-postgres.properties's own
// spring.flyway.enabled=true (redundant now, but harmless, and cheap
// insurance against the exact class of bug this project just spent
// three real CI failures diagnosing -- see docs/LESSONS.md: the actual
// root cause was spring-boot-flyway, Spring Boot 4's separate
// autoconfiguration module, missing from pom.xml entirely, NOT a
// property-precedence problem as first suspected).
@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = "spring.flyway.enabled=true")
@ActiveProfiles("postgres")
class PostgresFlywayIntegrationTest {

    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

    @LocalServerPort
    private int port;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private DemoJwtIssuer demoJwtIssuer;

    private RestTemplate restTemplate;

    @BeforeEach
    void setUpAuthenticatedClient() {
        restTemplate = AuthTestSupport.authenticatedRestTemplate(demoJwtIssuer);
    }

    private String url(String path) {
        return "http://localhost:" + port + path;
    }

    @Test
    void flywayMigrationsCreateTheExpectedRealPostgresTables() {
        Integer tableCount = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM information_schema.tables " +
                        "WHERE table_schema = 'public' AND table_name IN ('customer', 'customer_preference', 'contract_plan')",
                Integer.class);
        assertThat(tableCount).isEqualTo(3);
    }

    @Test
    void fullApiFlow_worksAgainstRealPostgres_notJustH2() {
        Customer created = restTemplate.postForObject(url("/customers"), new Customer("Real PG", "pg@example.com"), Customer.class);
        assertThat(created.getId()).isNotNull();

        ResponseEntity<Customer> fetched = restTemplate.getForEntity(url("/customers/" + created.getId()), Customer.class);
        assertThat(fetched.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(fetched.getBody().getEmail()).isEqualTo("pg@example.com");
    }

    @Test
    void preferencesDefaultAndUpdate_persistCorrectlyInRealPostgres() {
        Customer created = restTemplate.postForObject(url("/customers"), new Customer("Pref PG", "prefpg@example.com"), Customer.class);

        var defaultPrefs = restTemplate.getForObject(url("/customers/" + created.getId() + "/preferences"), java.util.Map.class);
        assertThat(defaultPrefs.get("notificationChannel")).isEqualTo("EMAIL");

        restTemplate.put(url("/customers/" + created.getId() + "/preferences"),
                new com.example.customer.dto.CustomerPreferenceUpdateRequest(true, NotificationChannel.SMS));
        var updated = restTemplate.getForObject(url("/customers/" + created.getId() + "/preferences"), java.util.Map.class);
        assertThat(updated.get("paperlessBilling")).isEqualTo(true);
    }

    @Test
    void oneActivePlanPerCustomer_isEnforcedByTheRealDatabaseConstraint_notOnlyServiceLogic() {
        Customer created = restTemplate.postForObject(url("/customers"), new Customer("Plan PG", "planpg@example.com"), Customer.class);
        Long customerId = created.getId();

        // A direct duplicate-active-row insert (bypassing ContractPlanService's
        // own cancel-then-insert logic entirely) proves the partial unique
        // index in V3__create_contract_plan.sql is real, independent
        // defense-in-depth -- not merely something the service layer promises.
        jdbcTemplate.update(
                "INSERT INTO contract_plan (customer_id, plan_name, rate_per_kwh, effective_start_date, status) " +
                        "VALUES (?, 'Direct Insert 1', 0.10, ?, 'ACTIVE')",
                customerId, java.sql.Date.valueOf(LocalDate.now()));

        assertThatThrownBy(() -> jdbcTemplate.update(
                "INSERT INTO contract_plan (customer_id, plan_name, rate_per_kwh, effective_start_date, status) " +
                        "VALUES (?, 'Direct Insert 2', 0.12, ?, 'ACTIVE')",
                customerId, java.sql.Date.valueOf(LocalDate.now())))
                .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    void enrollTwiceThroughTheRealApi_leavesExactlyOneActiveRowInRealPostgres() {
        Customer created = restTemplate.postForObject(url("/customers"), new Customer("Enroll PG", "enrollpg@example.com"), Customer.class);
        Long customerId = created.getId();

        restTemplate.postForEntity(url("/customers/" + customerId + "/plan"),
                new ContractPlanEnrollRequest("First", new BigDecimal("0.20"), LocalDate.of(2025, 1, 1)), Object.class);
        restTemplate.postForEntity(url("/customers/" + customerId + "/plan"),
                new ContractPlanEnrollRequest("Second", new BigDecimal("0.10"), LocalDate.of(2026, 1, 1)), Object.class);

        Integer activeCount = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM contract_plan WHERE customer_id = ? AND status = 'ACTIVE'",
                Integer.class, customerId);
        assertThat(activeCount).isEqualTo(1);

        Integer totalCount = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM contract_plan WHERE customer_id = ?", Integer.class, customerId);
        assertThat(totalCount).isEqualTo(2); // history preserved, not deleted
    }

    /**
     * REAL BUG this exact test would have caught before it ever reached
     * production (2026-09-14): CustomerRepository.searchWorkspaceCustomers
     * originally wrapped its :name/:email bind parameters in JPQL's
     * LOWER(...LIKE LOWER(CONCAT('%', :param, '%'))) -- H2 (every other
     * test in this suite) accepted this fine, but real PostgreSQL's JDBC
     * driver could not infer a concrete type for the nullable String bound
     * through CONCAT's `||` translation and defaulted it to bytea, failing
     * with "function lower(bytea) does not exist" -- a genuine
     * PRODUCTION 500 on the live ADMIN search endpoint, found only by
     * curling real production after deploy. Fixed by pre-building the
     * full "%value%" LIKE pattern in Java and binding it as a plain
     * String parameter (no CONCAT/LOWER wrapping the parameter itself).
     * This test uses the real ADMIN login flow (not a hand-built token)
     * against the real Postgres-backed demo_identity seed.
     */
    @Test
    void adminCustomerSearch_byNameAndEmail_worksAgainstRealPostgres_notJustH2() {
        RestTemplate plainRestTemplate = new RestTemplate();
        var loginResponse = plainRestTemplate.postForObject(
                url("/auth/login"),
                new com.example.customer.security.DemoLoginRequest("admin1", com.example.customer.security.DemoIdentitySeeder.DEMO_PASSWORD),
                com.example.customer.security.DemoLoginResponse.class);
        var headers = new org.springframework.http.HttpHeaders();
        headers.setBearerAuth(loginResponse.accessToken());

        ResponseEntity<java.util.Map> byName = plainRestTemplate.exchange(
                url("/admin/customers?name=Alex"), org.springframework.http.HttpMethod.GET,
                new org.springframework.http.HttpEntity<>(headers), java.util.Map.class);
        assertThat(byName.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat((java.util.List) byName.getBody().get("content")).isNotEmpty();

        ResponseEntity<java.util.Map> byEmail = plainRestTemplate.exchange(
                url("/admin/customers?email=user1@energydemo.local"), org.springframework.http.HttpMethod.GET,
                new org.springframework.http.HttpEntity<>(headers), java.util.Map.class);
        assertThat(byEmail.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat((java.util.List) byEmail.getBody().get("content")).hasSize(1);
    }
}
