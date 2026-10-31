-- ==============================================================================
-- Intelligent Fraud Ring Detection System - PostgreSQL Production Schema
-- Rebuilds all entities, relations, constraints, audit triggers, and indexes.
-- ==============================================================================

-- Clean up existing entities in dependency order
DROP TABLE IF EXISTS alert_audit CASCADE;
DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS alert CASCADE;
DROP TABLE IF EXISTS analyst CASCADE;
DROP TABLE IF EXISTS transaction CASCADE;
DROP TABLE IF EXISTS account_link CASCADE;
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
    email VARCHAR(150),
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
    account_number VARCHAR(64) UNIQUE,
    status VARCHAR(20) DEFAULT 'active',
    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_account_customer_id ON account(customer_id);
CREATE INDEX idx_account_number ON account(account_number);

-- 3. Account Link (Co-merchant relationship edge table)
CREATE TABLE account_link (
    account_a INT NOT NULL REFERENCES account(account_id) ON DELETE CASCADE,
    account_b INT NOT NULL REFERENCES account(account_id) ON DELETE CASCADE,
    shared_merchants INT DEFAULT 1 NOT NULL,
    PRIMARY KEY (account_a, account_b)
);

CREATE INDEX idx_account_link_a ON account_link(account_a);
CREATE INDEX idx_account_link_b ON account_link(account_b);

-- 4. Card
CREATE TABLE card (
    card_id SERIAL PRIMARY KEY,
    account_id INT NOT NULL REFERENCES account(account_id) ON DELETE CASCADE,
    card_number VARCHAR(32) UNIQUE NOT NULL,
    card_type VARCHAR(20) DEFAULT 'CREDIT',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_card_account_id ON card(account_id);
CREATE INDEX idx_card_number ON card(card_number);

-- 5. Merchant
CREATE TABLE merchant (
    merchant_id SERIAL PRIMARY KEY,
    merchant_name VARCHAR(255) UNIQUE NOT NULL,
    category VARCHAR(100),
    merch_lat DOUBLE PRECISION,
    merch_long DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_merchant_name ON merchant(merchant_name);

-- 6. Device
CREATE TABLE device (
    device_id SERIAL PRIMARY KEY,
    device_fingerprint VARCHAR(128) UNIQUE NOT NULL,
    device_type VARCHAR(50) DEFAULT 'BROWSER_MOBILE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_device_fingerprint ON device(device_fingerprint);

-- 7. IP Address
CREATE TABLE ip_address (
    ip_id SERIAL PRIMARY KEY,
    ip_str VARCHAR(64) UNIQUE NOT NULL,
    lat DOUBLE PRECISION,
    long DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ip_str ON ip_address(ip_str);

-- 8. Transaction
CREATE TABLE transaction (
    transaction_id SERIAL PRIMARY KEY,
    account_id INT NOT NULL REFERENCES account(account_id) ON DELETE CASCADE,
    merchant_id INT NOT NULL REFERENCES merchant(merchant_id) ON DELETE CASCADE,
    device_id INT REFERENCES device(device_id) ON DELETE SET NULL,
    ip_id INT REFERENCES ip_address(ip_id) ON DELETE SET NULL,
    trans_num VARCHAR(64) UNIQUE NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    txn_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_fraud BOOLEAN DEFAULT FALSE NOT NULL,
    source VARCHAR(50) DEFAULT 'training_dataset',
    predicted_fraud BOOLEAN DEFAULT FALSE,
    fraud_probability NUMERIC(5, 4)
);

CREATE INDEX idx_transaction_trans_num ON transaction(trans_num);
CREATE INDEX idx_transaction_account ON transaction(account_id);
CREATE INDEX idx_transaction_merchant ON transaction(merchant_id);
CREATE INDEX idx_transaction_timestamp ON transaction(txn_timestamp);
CREATE INDEX idx_transaction_is_fraud ON transaction(is_fraud);
CREATE INDEX idx_transaction_source ON transaction(source);
CREATE INDEX idx_txn_merch_time_acc ON transaction(merchant_id, txn_timestamp, account_id);

-- 9. Analyst
CREATE TABLE analyst (
    analyst_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'analyst',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_analyst_username ON analyst(username);

-- 10. Alert
CREATE TABLE alert (
    alert_id SERIAL PRIMARY KEY,
    transaction_id INT UNIQUE NOT NULL REFERENCES transaction(transaction_id) ON DELETE CASCADE,
    analyst_id INT REFERENCES analyst(analyst_id) ON DELETE SET NULL,
    fraud_probability NUMERIC(5, 4) NOT NULL,
    risk_label VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'reviewing', 'closed')),
    decision VARCHAR(100),
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_alert_transaction_id ON alert(transaction_id);
CREATE INDEX idx_alert_status ON alert(status);
CREATE INDEX idx_alert_fraud_prob ON alert(fraud_probability);
CREATE INDEX idx_alert_risk_label ON alert(risk_label);

-- 11. Alert Audit (Maintained via trigger on alert state change)
CREATE TABLE alert_audit (
    audit_id SERIAL PRIMARY KEY,
    alert_id INT NOT NULL REFERENCES alert(alert_id) ON DELETE CASCADE,
    changed_by INT REFERENCES analyst(analyst_id) ON DELETE SET NULL,
    old_status VARCHAR(20),
    new_status VARCHAR(20),
    old_decision VARCHAR(100),
    new_decision VARCHAR(100),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_alert_audit_alert_id ON alert_audit(alert_id);
CREATE INDEX idx_alert_audit_changed_at ON alert_audit(changed_at);

-- 12. General Audit Log
CREATE TABLE audit_log (
    log_id SERIAL PRIMARY KEY,
    analyst_id INT REFERENCES analyst(analyst_id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(50),
    target_id INT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_log_analyst_id ON audit_log(analyst_id);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at);

-- 13. Audit Trigger on Alert State Changes
CREATE OR REPLACE FUNCTION audit_alert_changes() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO alert_audit (
        alert_id,
        changed_by,
        old_status,
        new_status,
        old_decision,
        new_decision,
        changed_at
    ) VALUES (
        NEW.alert_id,
        NEW.analyst_id,
        OLD.status,
        NEW.status,
        OLD.decision,
        NEW.decision,
        CURRENT_TIMESTAMP
    );
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_alert_audit ON alert;
CREATE TRIGGER trg_alert_audit
    AFTER UPDATE ON alert
    FOR EACH ROW
    WHEN (
        OLD.status IS DISTINCT FROM NEW.status OR
        OLD.decision IS DISTINCT FROM NEW.decision OR
        OLD.note IS DISTINCT FROM NEW.note
    )
    EXECUTE FUNCTION audit_alert_changes();
