package com.example.notificationservice.outbox;

import java.io.Serializable;
import java.util.Objects;

/**
 * Composite key for {@link ProcessedEvent} -- see that class's Javadoc for
 * why a single global eventId is not enough once more than one independent
 * consumer group subscribes to the same event (true fan-out). Ported as-is
 * from app/src/main/java/com/example/customer/outbox/ProcessedEventId.java.
 */
public class ProcessedEventId implements Serializable {

    private String consumerName;
    private String eventId;

    public ProcessedEventId() {
    }

    public ProcessedEventId(String consumerName, String eventId) {
        this.consumerName = consumerName;
        this.eventId = eventId;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof ProcessedEventId other)) return false;
        return Objects.equals(consumerName, other.consumerName) && Objects.equals(eventId, other.eventId);
    }

    @Override
    public int hashCode() {
        return Objects.hash(consumerName, eventId);
    }
}
