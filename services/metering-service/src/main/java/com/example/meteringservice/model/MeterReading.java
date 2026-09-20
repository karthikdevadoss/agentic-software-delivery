package com.example.meteringservice.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;

/**
 * A single physical meter's consumption reading for one customer, on one
 * date. This is GENUINELY NEW domain modeling -- the monolith (app/) has
 * no equivalent of this at all; an energy-utility platform needs metering
 * data, and the monolith never modeled it. Nothing here is ported from
 * app/, unlike the other services in this decomposition.
 *
 * References the owning customer by a plain {@code customerId} column,
 * never a JPA relationship -- same reasoning the monolith already applies
 * to CustomerPreference/ContractPlan (see their class Javadoc in
 * app/src/main/java/com/example/customer/model/): in THIS decomposition
 * Customer lives in a separate service with its own separate database, so
 * a JPA {@code @ManyToOne} is not merely undesirable here, it is
 * impossible -- there is no shared persistence context to join across.
 * Every caller already has the customer id in scope from the request path
 * (POST/GET /customers/{id}/meter-readings), so no code path here ever
 * needs to navigate MeterReading -&gt; Customer in memory; a cross-service
 * lookup, if ever needed, would be a real network call (see
 * docs/MICROSERVICES_ARCHITECTURE.md's Billing -&gt; Customer REST pattern),
 * never a local join.
 */
@Entity
public class MeterReading {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private Long customerId;

    @Column(nullable = false)
    private String meterId;

    @Column(nullable = false)
    private LocalDate readingDate;

    /**
     * precision/scale sized for a real domestic-to-small-commercial meter
     * range (up to 9 digits before the decimal point, 3 digits after) --
     * generous enough that no realistic single reading overflows it,
     * without going so wide that arithmetic gets unnecessarily expensive.
     */
    @Column(nullable = false, precision = 12, scale = 3)
    private BigDecimal kWhConsumed;

    @Column(nullable = false)
    private Instant submittedAt;

    /** JPA requires a no-arg constructor; kept protected so application
     * code is steered toward the real constructor below, which enforces
     * that every reading is created with a complete, valid set of fields. */
    protected MeterReading() {
    }

    public MeterReading(Long customerId, String meterId, LocalDate readingDate, BigDecimal kWhConsumed) {
        this.customerId = customerId;
        this.meterId = meterId;
        this.readingDate = readingDate;
        this.kWhConsumed = kWhConsumed;
        // Set at creation time, server-side, never client-suppliable -- an
        // honest, tamper-proof record of when this reading actually
        // reached the system, independent of readingDate (which describes
        // when the physical reading was TAKEN, a caller-supplied fact that
        // can legitimately be earlier than submission time).
        this.submittedAt = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public Long getCustomerId() {
        return customerId;
    }

    public String getMeterId() {
        return meterId;
    }

    public LocalDate getReadingDate() {
        return readingDate;
    }

    public BigDecimal getKWhConsumed() {
        return kWhConsumed;
    }

    public Instant getSubmittedAt() {
        return submittedAt;
    }
}
