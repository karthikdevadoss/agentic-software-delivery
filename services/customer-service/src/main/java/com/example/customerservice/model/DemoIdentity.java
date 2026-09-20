package com.example.customerservice.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * A PORTFOLIO DEMO login identity -- explicitly NOT a real user-management
 * system. Real credentials (a BCrypt password hash, a fixed USER/ADMIN
 * role, an enabled flag) are genuinely verified server-side (see
 * DemoLoginController), never faked -- the only thing "demo" about it is
 * that the username/password pair is intentionally public so a recruiter
 * can log in without registering. A USER identity is bound to exactly one
 * {@link Customer} (its own workspace); an ADMIN identity has no bound
 * customer and instead gets the separate "admin:read" scope (see
 * DemoJwtIssuer.ADMIN_SCOPES) checked by WorkspaceAccessGuard.
 *
 * This service has no Flyway migration (see application.properties'
 * ddl-auto=create-drop) -- the USER/ADMIN role distinction is enforced
 * only in application code (DemoIdentitySeeder/DemoJwtIssuer), not by a
 * database CHECK constraint the way the monolith's own migrated schema
 * enforces it.
 */
@Entity
@Table(name = "demo_identity")
public class DemoIdentity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true)
    private String username;

    @Column(name = "password_hash", nullable = false)
    private String passwordHash;

    /** "USER" or "ADMIN". */
    @Column(nullable = false)
    private String role;

    @Column(name = "workspace_id", nullable = false, unique = true)
    private String workspaceId;

    /** Null for ADMIN identities -- an admin is not scoped to any single customer's workspace. */
    @Column(name = "customer_id")
    private Long customerId;

    @Column(nullable = false)
    private boolean enabled = true;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getPasswordHash() {
        return passwordHash;
    }

    public void setPasswordHash(String passwordHash) {
        this.passwordHash = passwordHash;
    }

    public String getRole() {
        return role;
    }

    public void setRole(String role) {
        this.role = role;
    }

    public String getWorkspaceId() {
        return workspaceId;
    }

    public void setWorkspaceId(String workspaceId) {
        this.workspaceId = workspaceId;
    }

    public Long getCustomerId() {
        return customerId;
    }

    public void setCustomerId(Long customerId) {
        this.customerId = customerId;
    }

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }
}
