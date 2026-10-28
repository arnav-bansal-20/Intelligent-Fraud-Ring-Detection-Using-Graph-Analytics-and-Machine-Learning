-- ==============================================================================
-- Intelligent Fraud Ring Detection System - PostgreSQL Schema
-- 9 Entities: customer, account, card, merchant, device, ip_address,
--             transaction, analyst, alert
-- ==============================================================================

DROP TABLE IF EXISTS alert CASCADE;
DROP TABLE IF EXISTS analyst CASCADE;
DROP TABLE IF EXISTS transaction CASCADE;
DROP TABLE IF EXISTS ip_address CASCADE;
DROP TABLE IF EXISTS device CASCADE;
DROP TABLE IF EXISTS merchant CASCADE;
DROP TABLE IF EXISTS card CASCADE;
DROP TABLE IF EXISTS account CASCADE;
DROP TABLE IF EXISTS customer CASCADE;

-- 1. Customer
CREATE TABLE customer (
    customer_id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    gender VARCHAR(10),
    dob DATE,
    job VARCHAR(150),
    street VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(50),
    zip VARCHAR(20),
    lat DOUBLE PRECISION,
    long DOUBLE PRECISION,
    city_pop INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_customer_name_dob ON customer(first_name, last_name, dob);

-- 2. Account
CREATE TABLE account (
    account_id SERIAL PRIMARY KEY,
    customer_id INT NOT NULL REFERENCES customer(customer_id) ON DELETE CASCADE,
    account_number VARCHAR(64) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_account_customer_id ON account(customer_id);

-- 3. Card
CREATE TABLE card (
    card_id SERIAL PRIMARY KEY,
    account_id INT NOT NULL REFERENCES account(account_id) ON DELETE CASCADE,
    card_number VARCHAR(32) UNIQUE NOT NULL,
    card_type VARCHAR(20) DEFAULT 'CREDIT',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_card_account_id ON card(account_id);
CREATE INDEX idx_card_number ON card(card_number);

-- 4. Merchant
CREATE TABLE merchant (
    merchant_id SERIAL PRIMARY KEY,
    merchant_name VARCHAR(255) UNIQUE NOT NULL,
    category VARCHAR(100),
    merch_lat DOUBLE PRECISION,
    merch_long DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_merchant_name ON merchant(merchant_name);

-- 5. Device
CREATE TABLE device (
    device_id SERIAL PRIMARY KEY,
    device_fingerprint VARCHAR(128) UNIQUE NOT NULL,
    device_type VARCHAR(50) DEFAULT 'BROWSER_MOBILE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_device_fingerprint ON device(device_fingerprint);

-- 6. IP Address
CREATE TABLE ip_address (
    ip_id SERIAL PRIMARY KEY,
    ip_str VARCHAR(64) UNIQUE NOT NULL,
    lat DOUBLE PRECISION,
    long DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ip_str ON ip_address(ip_str);

-- 7. Transaction
CREATE TABLE transaction (
    transaction_id SERIAL PRIMARY KEY,
    trans_num VARCHAR(64) UNIQUE NOT NULL,
    trans_date_trans_time TIMESTAMP NOT NULL,
    unix_time BIGINT NOT NULL,
    amt NUMERIC(12, 2) NOT NULL,
    account_id INT NOT NULL REFERENCES account(account_id) ON DELETE CASCADE,
    card_id INT REFERENCES card(card_id) ON DELETE SET NULL,
    merchant_id INT NOT NULL REFERENCES merchant(merchant_id) ON DELETE CASCADE,
    device_id INT REFERENCES device(device_id) ON DELETE SET NULL,
    ip_id INT REFERENCES ip_address(ip_id) ON DELETE SET NULL,
    is_fraud SMALLINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_transaction_trans_num ON transaction(trans_num);
CREATE INDEX idx_transaction_account_id ON transaction(account_id);
CREATE INDEX idx_transaction_merchant_id ON transaction(merchant_id);
CREATE INDEX idx_transaction_device_id ON transaction(device_id);
CREATE INDEX idx_transaction_ip_id ON transaction(ip_id);
CREATE INDEX idx_transaction_unix_time ON transaction(unix_time);
CREATE INDEX idx_transaction_is_fraud ON transaction(is_fraud);

-- 8. Analyst
CREATE TABLE analyst (
    analyst_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    role VARCHAR(50) DEFAULT 'INVESTIGATOR',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. Alert
CREATE TABLE alert (
    alert_id SERIAL PRIMARY KEY,
    transaction_id INT UNIQUE NOT NULL REFERENCES transaction(transaction_id) ON DELETE CASCADE,
    risk_score DOUBLE PRECISION NOT NULL,
    alert_status VARCHAR(20) DEFAULT 'OPEN',
    analyst_id INT REFERENCES analyst(analyst_id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_alert_transaction_id ON alert(transaction_id);
CREATE INDEX idx_alert_status ON alert(alert_status);
CREATE INDEX idx_alert_risk_score ON alert(risk_score);

