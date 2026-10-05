# Project Documentation: Intelligent Fraud Ring Detection

**Course Project:** College DBMS — Hybrid Database Architecture & Fraud Analytics  
**Architecture:** PostgreSQL (Transactional Core) + MongoDB (Graph/Relationship Layer) + Scikit-Learn ML  
**Status:** Step 1 Completed (Environment, Schema Initialization & PostgreSQL Relational Ingestion)

---

## 1. Project Goal & High-Level Architecture

The goal of this system is to identify coordinated **fraud rings** that traditional single-transaction monitoring fails to catch. It accomplishes this through a hybrid database design:
- **PostgreSQL**: Stores relational, normalized records ensuring strict ACID guarantees and foreign-key integrity across customers, accounts, cards, merchants, terminals, and transactions.
- **MongoDB**: Acts as the dynamic graph and relationship layer, holding device/IP link graphs, account adjacency lists, precomputed fraud features, and native transaction flow graphs (Elliptic dataset).
- **Machine Learning Layer**: Combines standard tabular transaction attributes with topological graph signals (degree centrality, shared entity counts, hop distances to flagged fraud accounts) to predict fraudulent behavior.
- **DBMS Benchmark**: Directly compares multi-hop graph traversal performance between MongoDB (`$graphLookup`) and PostgreSQL (Recursive CTE multi-table joins).
- **Interactive UI**: A FastAPI backend and modern React dashboard for analysts to inspect flagged fraud rings.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DATASETS IN /Datasets                           │
│  • fraudTrain.csv / fraudTest.csv (Kartik2112 Sparkov dataset)         │
│  • elliptic_txs_edgelist / classes / features.csv (Bitcoin tx graph)   │
│  • PS_20174392719... (PaySim 6.3M rows for scale testing)              │
└───────────────────┬───────────────────────────────┬────────────────────┘
                    │                               │
                    ▼                               ▼
       ┌────────────────────────┐      ┌─────────────────────────┐
       │  POSTGRESQL (schema)   │      │  MONGODB (Graph Layer)  │
       │  • customer, account   │      │  • device_links         │
       │  • card, merchant      │      │  • ip_links             │
       │  • device, ip_address  │      │  • account_graph        │
       │  • transaction, alert  │      │  • elliptic_nodes/edges │
       │  • analyst             │      │  • fraud_features       │
       └────────────┬───────────┘      └────────────┬────────────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │             STEP 3: GRAPH FEATURE EXTRACTION            │
       │  Shared device/IP degree, merchant concentration,       │
       │  and k-hops distance to nearest flagged account         │
       └────────────────────────────┬────────────────────────────┘
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │             STEP 4: ML FRAUD CLASSIFIER                 │
       │  70/15/15 time split • Random Forest / XGBoost          │
       │  Evaluated on Precision, Recall, F1, and AUC-ROC        │
       └────────────────────────────┬────────────────────────────┘
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │             STEP 5: HYBRID DBMS BENCHMARK               │
       │  Multi-hop k-hop traversal comparison:                  │
       │  MongoDB $graphLookup vs PostgreSQL Recursive CTE joins │
       └────────────────────────────┬────────────────────────────┘
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │             STEP 6: FASTAPI REST API                    │
       │  Ingestion, real-time risk scoring, alerts management   │
       └────────────────────────────┬────────────────────────────┘
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │             STEP 7: REACT DASHBOARD                     │
       │  Visual ring explorer, alert queue, benchmark charts    │
       └─────────────────────────────────────────────────────────┘
```

---

## 2. What Has Been Completed Until Now

### A. Environment & Infrastructure Setup
1. **PostgreSQL 16**:
   - Installed via Homebrew (`postgresql@16`), initialized the cluster, and started the local background service.
   - Created the dedicated database: `fraud_db`.
2. **MongoDB**:
   - Confirmed active and responsive on `localhost:27017` via `mongosh`.
3. **Python Virtual Environment (`.venv`)**:
   - Initialized Python 3.14 virtual environment.
   - Installed all required libraries:
     - `psycopg[binary]` (PostgreSQL driver)
     - `pymongo` (MongoDB driver)
     - `pandas` & `numpy` (data processing)
     - `scikit-learn` & `scipy` (machine learning)
     - `fastapi` & `uvicorn` (backend API framework)
     - `networkx` (graph algorithms and utilities)
4. **Dataset Alignment**:
   - Identified all datasets in `Datasets/`:
     - `fraudTest.csv` (143 MB, ~555k transactions)
     - `fraudTrain.csv` (335 MB, ~1.29M transactions) symlinked from Downloads
     - `elliptic_txs_edgelist.csv`, `elliptic_txs_classes.csv`, `elliptic_txs_features.csv`
     - `PS_20174392719_1491204439457_log.csv` (471 MB)
     - `creditcard.csv` (144 MB)

---

### B. Relational Schema Execution
- Executed `schema.sql` directly on PostgreSQL `fraud_db` without any modifications.
- Successfully created all **9 relational tables**:
  - `customer` (customer_id SERIAL PRIMARY KEY, first_name, last_name, email UNIQUE, phone_number, date_of_birth, kyc_verified, created_at)
  - `account` (account_id SERIAL PRIMARY KEY, customer_id FK, account_number UNIQUE, account_type, balance, status, opened_date)
  - `card` (card_id SERIAL PRIMARY KEY, account_id FK, card_number_hash, card_type, expiry_date, status)
  - `merchant` (merchant_id SERIAL PRIMARY KEY, merchant_name, mcc_category, location)
  - `device` (device_id SERIAL PRIMARY KEY, device_fingerprint UNIQUE, device_type, last_seen_at)
  - `ip_address` (ip_id SERIAL PRIMARY KEY, ip_address, country, is_vpn)
  - `analyst` (analyst_id SERIAL PRIMARY KEY, name, email, role)
  - `transaction` (transaction_id SERIAL PRIMARY KEY, account_id FK, card_id FK, merchant_id FK, device_id FK, ip_id FK, amount, txn_timestamp, status, fraud_label)
  - `alert` (alert_id SERIAL PRIMARY KEY, transaction_id UNIQUE FK, analyst_id FK, risk_score, alert_reason, alert_status, created_at, reviewed_at)
- Successfully created all **6 indexes**:
  - `idx_txn_account`, `idx_txn_device`, `idx_txn_ip`, `idx_txn_merchant`, `idx_txn_timestamp`, `idx_alert_status`.

---

### C. Step 1: PostgreSQL Relational Loader (`src/loader_pg.py`)
Implemented and verified the ingestion script with complete deduplication and deterministic proxy derivation:

#### 1. Entity Deduplication Logic
- **Customers**: Deduplicated by `(first_name, last_name, date_of_birth)`. Clean deterministic email and phone numbers assigned.
- **Accounts & Cards**: Each card credit card number (`cc_num`) maps to a unique account and card record. Cards store SHA-256 hashed representations (`card_number_hash`) with detected card brands (Visa, Mastercard, etc.).
- **Merchants**: Deduplicated by `merchant_name` with assigned categories and location.

#### 2. Realistic Device & IP Proxy Derivation
As per project requirements (avoiding fabricated device IDs while modeling shared relationships):
- **Device Terminal Proxy**:
  ```python
  def derive_device_fingerprint(merchant_name, state):
      raw = f"TERM_{merchant_name.strip()}_{state.strip()}"
      return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
  ```
  Models merchant POS terminals and regional payment gateway clusters. Multiple accounts transacting at the same merchant network in a given region share a physical terminal device proxy.
- **IP Address Proxy**:
  ```python
  def derive_ip_address(city, state):
      octet3 = (abs(hash(state.strip())) % 250) + 1
      octet4 = (abs(hash(city.strip())) % 250) + 1
      return f"198.51.{octet3}.{octet4}"
  ```
  Models regional ISP subnets based on geographic location.

#### 3. Ingestion Verification Run
Executed `python3 src/loader_pg.py --truncate --limit 50000`:
- **Customers Synced:** 910
- **Accounts Synced:** 910
- **Cards Synced:** 910
- **Merchants Synced:** 693
- **Device Terminal Clusters:** 22,043
- **IP Address Subnets:** 819
- **Transactions Ingested:** 50,000 (199 ground-truth fraudulent transactions)

#### 4. Relational Data Verification
Executed an SQL join query against PostgreSQL confirming connected relationships across accounts:
```sql
SELECT t.transaction_id, c.first_name || ' ' || c.last_name as customer_name,
       a.account_number, m.merchant_name, d.device_fingerprint, ip.ip_address,
       t.amount, t.fraud_label
FROM transaction t
JOIN account a ON t.account_id = a.account_id
JOIN customer c ON a.customer_id = c.customer_id
JOIN merchant m ON t.merchant_id = m.merchant_id
JOIN device d ON t.device_id = d.device_id
JOIN ip_address ip ON t.ip_id = ip.ip_id
LIMIT 5;
```
Result shows accounts `ACCT-C4A1B139DFA2` (Jeff Elliott), `ACCT-A1CFB1174471` (Amanda Smith), and `ACCT-475B906DF225` (Robert Haynes) actively sharing terminal device `d83e694f3bfe00df7a9417694ff1cf12` at `fraud_Kirlin and Sons`.

---

## 3. Immediate Next Steps

1. **Step 2 (Next)**: Build `src/loader_mongo.py`
   - Ingest the Elliptic graph files (`elliptic_txs_edgelist.csv`, `classes.csv`, `features.csv`) into MongoDB collections `elliptic_nodes` and `elliptic_edges`.
   - Build relationship collections from the loaded PostgreSQL transactions:
     - `device_links`: account $\leftrightarrow$ device edges with `usage_count`, `first_used`, `last_used`.
     - `ip_links`: account $\leftrightarrow$ ip edges with `usage_count`, `first_used`, `last_used`.
     - `account_graph`: adjacency list per account (linked devices, IPs, accounts, degree).
2. **Step 3**: Build `src/graph_features.py` for feature extraction into `fraud_features`.
3. **Step 4**: Train baseline ML classifier in `src/model_trainer.py` (Random Forest / XGBoost with 70/15/15 time split and class weighting).
4. **Step 5**: Implement `src/benchmark.py` comparing MongoDB `$graphLookup` vs PostgreSQL recursive CTE joins.
5. **Step 6**: Develop FastAPI application in `backend/`.
6. **Step 7**: Build the React dashboard in `frontend/`.
