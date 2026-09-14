-- TRANSACTIONAL OUTBOX (not a naive dual write): a business write and
-- its corresponding event are inserted together in ONE database
-- transaction (see CustomerPreferenceService.update()), so a Kafka
-- publish failure can never lose an event and a Kafka publish can never
-- happen for a database write that gets rolled back. A separate poller
-- (OutboxPublisher) reads unpublished rows and publishes them
-- asynchronously -- at-least-once delivery, with the consumer side
-- responsible for idempotency (see processed_event, V5).
CREATE TABLE outbox_event (
    id             BIGSERIAL PRIMARY KEY,
    event_id       VARCHAR(36) NOT NULL UNIQUE,
    aggregate_type VARCHAR(50) NOT NULL,
    aggregate_id   BIGINT NOT NULL,
    event_type     VARCHAR(100) NOT NULL,
    payload        TEXT NOT NULL,
    created_at     TIMESTAMP WITH TIME ZONE NOT NULL,
    published_at   TIMESTAMP WITH TIME ZONE
);

-- The publisher's poll query is always "unpublished rows, oldest first" --
-- this partial index keeps that query cheap even as published history grows.
CREATE INDEX ix_outbox_event_unpublished ON outbox_event (created_at) WHERE published_at IS NULL;
