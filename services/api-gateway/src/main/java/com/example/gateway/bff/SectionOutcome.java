package com.example.gateway.bff;

/**
 * BL-039: one dashboard section's honest outcome. A screen at NRG was one
 * aggregator call fanning out to several downstream calls; when one of
 * them was slow or down the customer still got the rest of the screen,
 * with that section marked unavailable -- never a fabricated value, never
 * the whole screen blocked by the slowest dependency.
 */
public record SectionOutcome(Status status, Object data, String reason, long elapsedMs) {

    public enum Status { OK, UNAVAILABLE }

    public static SectionOutcome ok(Object data, long elapsedMs) {
        return new SectionOutcome(Status.OK, data, null, elapsedMs);
    }

    public static SectionOutcome unavailable(String reason, long elapsedMs) {
        return new SectionOutcome(Status.UNAVAILABLE, null, reason, elapsedMs);
    }
}
