CREATE TABLE customer_preference (
    id                   BIGSERIAL PRIMARY KEY,
    customer_id          BIGINT NOT NULL,
    paperless_billing    BOOLEAN NOT NULL,
    notification_channel VARCHAR(20) NOT NULL,
    updated_at           TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT uq_customer_preference_customer_id UNIQUE (customer_id),
    CONSTRAINT fk_customer_preference_customer FOREIGN KEY (customer_id) REFERENCES customer (id)
);
