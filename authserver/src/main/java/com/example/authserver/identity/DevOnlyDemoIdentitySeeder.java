package com.example.authserver.identity;

import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Profile;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

/**
 * LOCAL DEV / TEST ONLY -- mirrors the Customer App's own real demo
 * personas (see that app's DemoIdentitySeeder) into this service's
 * isolated, throwaway H2 instance, so local development/tests have real
 * identities to authenticate against without a live Postgres connection.
 *
 * {@code @Profile("!postgres")} is the real, structural guarantee this
 * never runs against the shared production database: the "postgres"
 * profile (real production) is the ONE case this seeder must never fire
 * in, since that table is owned and already populated by the Customer
 * App -- this service only ever READS it there (see DemoIdentityRepository,
 * which exposes no write methods at all, a second, independent layer of
 * the same guarantee).
 */
@Component
@Profile("!postgres")
public class DevOnlyDemoIdentitySeeder implements ApplicationRunner {

    @PersistenceContext
    private EntityManager entityManager;

    private final PasswordEncoder passwordEncoder;

    public DevOnlyDemoIdentitySeeder(PasswordEncoder passwordEncoder) {
        this.passwordEncoder = passwordEncoder;
    }

    @Override
    @Transactional
    public void run(ApplicationArguments args) {
        seed(1L, "user1", "USER", "ws-user1", 101L);
        seed(2L, "user2", "USER", "ws-user2", 102L);
        seed(3L, "user3", "USER", "ws-user3", 103L);
        seed(4L, "admin1", "ADMIN", "ws-admin1", null);
        seed(5L, "admin2", "ADMIN", "ws-admin2", null);
    }

    private void seed(Long id, String username, String role, String workspaceId, Long customerId) {
        // Native insert, not entityManager.persist(new DemoIdentity()): the
        // entity deliberately has no setters (read-only mapping, see its
        // own Javadoc) -- this dev-only seeder is the one legitimate
        // exception, going around the entity via a direct native statement
        // rather than adding write methods the production read path could
        // then also accidentally call.
        entityManager.createNativeQuery(
                "INSERT INTO demo_identity (id, username, password_hash, role, workspace_id, customer_id, enabled) "
                        + "VALUES (:id, :username, :passwordHash, :role, :workspaceId, :customerId, true)")
                .setParameter("id", id)
                .setParameter("username", username)
                .setParameter("passwordHash", passwordEncoder.encode("Demo@123"))
                .setParameter("role", role)
                .setParameter("workspaceId", workspaceId)
                .setParameter("customerId", customerId)
                .executeUpdate();
    }
}
