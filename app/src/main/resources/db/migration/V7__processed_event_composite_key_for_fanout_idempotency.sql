-- REAL BUG FIX, not a routine schema change: processed_event was originally
-- keyed by event_id alone, which is only correct as long as exactly one
-- consumer group ever processes a given event. Adding a second,
-- independently-consumed event type (ContractPlanEnrolled, fanned out to a
-- Notification consumer AND a BillingSync consumer, deliberately different
-- consumer groups) exposed the real defect: a global "processed" flag lets
-- whichever consumer records its row first make every OTHER independent
-- consumer see "already processed" and silently skip real work. See
-- ProcessedEvent's Javadoc and Triage Scenario D for the full story.
--
-- No real data is lost: Kafka has never been enabled in production
-- (app.kafka.enabled defaults to false), so this table has never held a
-- real production row.
DROP TABLE processed_event;

CREATE TABLE processed_event (
    consumer_name VARCHAR(100) NOT NULL,
    event_id      VARCHAR(36)  NOT NULL,
    processed_at  TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (consumer_name, event_id)
);
