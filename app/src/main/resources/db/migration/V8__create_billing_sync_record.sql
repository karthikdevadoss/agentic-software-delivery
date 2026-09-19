-- Real, independently-verifiable side effect of the BillingSync fan-out
-- consumer (see ContractPlanBillingSyncConsumer) -- a persisted row, not
-- just a log line, so a real integration test can assert this consumer
-- genuinely did its own work independently of the Notification consumer,
-- both reacting to the SAME ContractPlanEnrolled event.
CREATE TABLE billing_sync_record (
    id               BIGSERIAL PRIMARY KEY,
    contract_plan_id BIGINT NOT NULL,
    customer_id      BIGINT NOT NULL,
    plan_name        VARCHAR(255) NOT NULL,
    rate_per_kwh     NUMERIC(10,4) NOT NULL,
    synced_at        TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX idx_billing_sync_record_contract_plan_id ON billing_sync_record (contract_plan_id);
