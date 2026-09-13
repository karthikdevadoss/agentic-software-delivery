CREATE TABLE contract_plan (
    id                    BIGSERIAL PRIMARY KEY,
    customer_id           BIGINT NOT NULL,
    plan_name             VARCHAR(255) NOT NULL,
    rate_per_kwh          NUMERIC(10, 4) NOT NULL,
    effective_start_date  DATE NOT NULL,
    effective_end_date    DATE,
    status                VARCHAR(20) NOT NULL,
    CONSTRAINT fk_contract_plan_customer FOREIGN KEY (customer_id) REFERENCES customer (id)
);

-- Enforces the "at most one ACTIVE plan per customer" business rule at
-- the database level too, not only in ContractPlanService -- a partial
-- unique index is the correct Postgres-native way to express "unique
-- among ACTIVE rows only" without a broader, incorrect uniqueness
-- constraint across all statuses (a customer legitimately has many
-- CANCELLED plans in their history).
CREATE UNIQUE INDEX uq_contract_plan_one_active_per_customer
    ON contract_plan (customer_id)
    WHERE status = 'ACTIVE';

CREATE INDEX ix_contract_plan_customer_id ON contract_plan (customer_id);
