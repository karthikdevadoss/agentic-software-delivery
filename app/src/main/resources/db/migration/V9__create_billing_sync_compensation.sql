-- Saga-style compensation ledger for billing syncs that fail for a
-- genuine business reason (not a transient/technical one) -- see
-- BillingSyncCompensation's Javadoc for the retry-vs-compensate
-- distinction this table exists to support.
CREATE TABLE billing_sync_compensation (
    id                BIGSERIAL PRIMARY KEY,
    contract_plan_id  BIGINT NOT NULL,
    customer_id       BIGINT NOT NULL,
    plan_name         VARCHAR(255) NOT NULL,
    reason            VARCHAR(500) NOT NULL,
    compensated_at    TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX idx_billing_sync_compensation_contract_plan_id ON billing_sync_compensation (contract_plan_id);
