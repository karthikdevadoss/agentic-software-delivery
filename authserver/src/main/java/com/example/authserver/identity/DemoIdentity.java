package com.example.authserver.identity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * Read-only mapping onto the SAME real {@code demo_identity} table the
 * Customer App owns (schema/migrations live exclusively in that other
 * service -- see app/src/main/resources/db/migration). This Authorization
 * Server is a second, independent Spring Boot deployable connecting to the
 * SAME production Postgres database via the SAME DATABASE_URL, exactly the
 * real enterprise pattern this models: a shared identity store one
 * Authorization Server authenticates against, while separate resource
 * servers validate the tokens it issues -- never a second, independently-
 * seeded, silently-diverging copy of "who the demo users are."
 *
 * No {@code @GeneratedValue}/writes anywhere in this entity or its
 * repository -- this side only ever reads.
 */
@Entity
@Table(name = "demo_identity")
public class DemoIdentity {

    @Id
    private Long id;

    @Column(nullable = false, unique = true)
    private String username;

    @Column(name = "password_hash", nullable = false)
    private String passwordHash;

    @Column(nullable = false)
    private String role;

    @Column(name = "workspace_id", nullable = false, unique = true)
    private String workspaceId;

    @Column(name = "customer_id")
    private Long customerId;

    @Column(nullable = false)
    private boolean enabled = true;

    public Long getId() { return id; }
    public String getUsername() { return username; }
    public String getPasswordHash() { return passwordHash; }
    public String getRole() { return role; }
    public String getWorkspaceId() { return workspaceId; }
    public Long getCustomerId() { return customerId; }
    public boolean isEnabled() { return enabled; }
}
