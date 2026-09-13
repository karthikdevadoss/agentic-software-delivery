package com.example.customer.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;

import java.time.Instant;

/**
 * Deliberately references the owning customer by a plain {@code customerId}
 * column rather than a JPA {@code @ManyToOne}/{@code @OneToOne} entity
 * relationship. This is a real design decision, not an oversight: every
 * service method already has the customer id in scope from the request
 * path, so no code path ever needs to navigate CustomerPreference -&gt;
 * Customer in memory. Avoiding the relationship sidesteps lazy-loading /
 * Jackson-serialization pitfalls entirely (see the {@code open-in-view=false}
 * decision in application.properties) rather than requiring a DTO-only
 * workaround for a relationship nothing actually uses.
 */
@Entity
public class CustomerPreference {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true)
    private Long customerId;

    @Column(nullable = false)
    private boolean paperlessBilling;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private NotificationChannel notificationChannel;

    @Column(nullable = false)
    private Instant updatedAt;

    protected CustomerPreference() {
    }

    public CustomerPreference(Long customerId, boolean paperlessBilling, NotificationChannel notificationChannel) {
        this.customerId = customerId;
        this.paperlessBilling = paperlessBilling;
        this.notificationChannel = notificationChannel;
        this.updatedAt = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public Long getCustomerId() {
        return customerId;
    }

    public boolean isPaperlessBilling() {
        return paperlessBilling;
    }

    public NotificationChannel getNotificationChannel() {
        return notificationChannel;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public void update(boolean paperlessBilling, NotificationChannel notificationChannel) {
        this.paperlessBilling = paperlessBilling;
        this.notificationChannel = notificationChannel;
        this.updatedAt = Instant.now();
    }
}
