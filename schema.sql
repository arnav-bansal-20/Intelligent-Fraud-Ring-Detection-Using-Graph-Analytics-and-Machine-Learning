-- ============================================================
-- Intelligent Fraud Ring Detection — PostgreSQL Schema
-- 9 entities, matching the project's ER diagram
-- ============================================================

CREATE TABLE customer (
    customer_id     SERIAL PRIMARY KEY,
    first_name      VARCHAR(100),
    last_name       VARCHAR(100),
    email           VARCHAR(255) UNIQUE,
    phone_number    VARCHAR(30),
    date_of_birth   DATE,
    kyc_verified    BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE account (
    account_id      SERIAL PRIMARY KEY,
    customer_id     INT NOT NULL REFERENCES customer(customer_id),
    account_number  VARCHAR(50) UNIQUE,
    account_type    VARCHAR(20),
    balance         DECIMAL(14,2) DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'active',
    opened_date     DATE DEFAULT CURRENT_DATE
);

CREATE TABLE card (
    card_id           SERIAL PRIMARY KEY,
    account_id        INT NOT NULL REFERENCES account(account_id),
    card_number_hash  VARCHAR(128),
    card_type         VARCHAR(20),
    expiry_date       DATE,
    status            VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE merchant (
    merchant_id     SERIAL PRIMARY KEY,
    merchant_name   VARCHAR(150),
    mcc_category    VARCHAR(50),
    location        VARCHAR(150)
);

CREATE TABLE device (
    device_id           SERIAL PRIMARY KEY,
    device_fingerprint  VARCHAR(128) UNIQUE,
    device_type         VARCHAR(30),
    last_seen_at        TIMESTAMP
);

CREATE TABLE ip_address (
    ip_id           SERIAL PRIMARY KEY,
    ip_address      VARCHAR(45),
    country         VARCHAR(60),
    is_vpn          BOOLEAN DEFAULT FALSE
);

CREATE TABLE analyst (
    analyst_id      SERIAL PRIMARY KEY,
    name            VARCHAR(100),
    email           VARCHAR(255),
    role            VARCHAR(50)
);

CREATE TABLE transaction (
    transaction_id  SERIAL PRIMARY KEY,
    account_id      INT NOT NULL REFERENCES account(account_id),
    card_id         INT REFERENCES card(card_id),           -- nullable: not every txn uses a card
    merchant_id     INT REFERENCES merchant(merchant_id),
    device_id       INT REFERENCES device(device_id),
    ip_id           INT REFERENCES ip_address(ip_id),
    amount          DECIMAL(14,2) NOT NULL,
    txn_timestamp   TIMESTAMP NOT NULL,
    status          VARCHAR(20) DEFAULT 'approved',
    fraud_label     BOOLEAN                                  -- ground truth, nullable until known
);

CREATE TABLE alert (
    alert_id        SERIAL PRIMARY KEY,
    transaction_id  INT UNIQUE NOT NULL REFERENCES transaction(transaction_id),
    analyst_id      INT REFERENCES analyst(analyst_id),      -- nullable: unassigned until reviewed
    risk_score      FLOAT,
    alert_reason    TEXT,
    alert_status    VARCHAR(20) DEFAULT 'open',
    created_at      TIMESTAMP DEFAULT NOW(),
    reviewed_at     TIMESTAMP
);

-- ============================================================
-- Indexes — support the multi-hop lookups the graph layer
-- feeds into, and the relational baseline you'll benchmark it against
-- ============================================================
CREATE INDEX idx_txn_account   ON transaction(account_id);
CREATE INDEX idx_txn_device    ON transaction(device_id);
CREATE INDEX idx_txn_ip        ON transaction(ip_id);
CREATE INDEX idx_txn_merchant  ON transaction(merchant_id);
CREATE INDEX idx_txn_timestamp ON transaction(txn_timestamp);
CREATE INDEX idx_alert_status  ON alert(alert_status);
