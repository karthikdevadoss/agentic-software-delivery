CREATE TABLE demo_identity (
    id            BIGSERIAL PRIMARY KEY,
    username      VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(100) NOT NULL,
    role          VARCHAR(10) NOT NULL CHECK (role IN ('USER', 'ADMIN')),
    workspace_id  VARCHAR(64) NOT NULL UNIQUE,
    customer_id   BIGINT REFERENCES customer(id),
    enabled       BOOLEAN NOT NULL DEFAULT TRUE
);
