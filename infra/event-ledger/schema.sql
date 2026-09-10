-- Agentic Software Delivery — durable event ledger schema.
-- Append-only. One canonical envelope for every observable event across
-- Workbench runs (and, eventually, other sources — see event_source).
-- Idempotent by design: event_id is the primary key, so a retried insert
-- (e.g. after a local-spool sync) is a safe no-op via ON CONFLICT DO NOTHING
-- rather than a duplicate row. Applied via agent/event_ledger.py's
-- ensure_schema() — this file exists for human review/reproducibility,
-- not as a migration tool (no migration framework introduced for one table).

CREATE TABLE IF NOT EXISTS delivery_events (
    event_id                   TEXT PRIMARY KEY,
    schema_version             INTEGER NOT NULL,
    timestamp_utc              TIMESTAMPTZ NOT NULL,

    event_type                 TEXT NOT NULL,
    stage                      TEXT,
    status                     TEXT,

    actor_type                 TEXT,
    actor_id                   TEXT,
    actor_role                 TEXT,

    session_id                 TEXT,
    run_id                     TEXT,
    requirement_id             TEXT,
    trace_id                   TEXT,
    correlation_id             TEXT,

    source                     TEXT,
    service                    TEXT,
    environment                TEXT,

    duration_ms                DOUBLE PRECISION,

    provider                   TEXT,
    model                      TEXT,
    input_tokens                INTEGER,
    output_tokens               INTEGER,
    cache_read_tokens           INTEGER,
    cache_write_tokens          INTEGER,

    tool_name                  TEXT,
    tool_call_id                TEXT,

    git_commit                 TEXT,
    deployment_version         TEXT,

    data_classification        TEXT,
    retention_class            TEXT,
    training_eligibility       TEXT,

    payload                    JSONB,

    -- Provenance: distinguishes a live write-through event from a
    -- one-time historical backfill import (see agent/event_ledger.py's
    -- backfill_from_run_history()). Never let reconstructed history look
    -- identical to something actually observed live.
    backfill_source             TEXT,
    evidence_quality            TEXT,

    ingested_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_delivery_events_run_id ON delivery_events (run_id);
CREATE INDEX IF NOT EXISTS idx_delivery_events_session_id ON delivery_events (session_id);
CREATE INDEX IF NOT EXISTS idx_delivery_events_timestamp ON delivery_events (timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_delivery_events_event_type ON delivery_events (event_type);

-- Added for the Claude Code development-telemetry source: distinguishes
-- PRODUCT_DEVELOPMENT activity (building this platform, via Claude Code)
-- from PRODUCT_RUNTIME activity (the Workbench executing on behalf of a
-- requirement) — both share this one table/`source` field, but this one
-- extra dimension is cheap and queried often enough to deserve a real
-- column rather than living buried in JSONB only. Additive, idempotent —
-- safe to run against a table that predates this column.
ALTER TABLE delivery_events ADD COLUMN IF NOT EXISTS activity_class TEXT;
CREATE INDEX IF NOT EXISTS idx_delivery_events_activity_class ON delivery_events (activity_class);
