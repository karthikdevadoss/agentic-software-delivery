-- CONSUMER-SIDE IDEMPOTENCY LEDGER: the outbox pattern guarantees
-- at-least-once delivery, never exactly-once -- a durable record of
-- which event_ids have already been processed is what makes a redelivered
-- duplicate a safe no-op instead of a repeated side effect.
CREATE TABLE processed_event (
    event_id      VARCHAR(36) PRIMARY KEY,
    processed_at  TIMESTAMP WITH TIME ZONE NOT NULL
);
