# Intelligent Fraud Ring Detection Using Graph Analytics and Machine Learning

A hybrid database architecture and fraud analytics system combining **PostgreSQL** (ACID transactional core), **MongoDB** (dynamic graph and relationship layer), and **Machine Learning (XGBoost)** for detecting coordinated financial fraud rings.

**Course Project:** College DBMS — Hybrid Database Architecture & Fraud Analytics  
**Architecture:** PostgreSQL 16 (Relational Core) + MongoDB (Graph Layer) + Gradient Boosted Decision Trees (XGBoost)  
**Status:** Steps 0 through 5 Completed & Verified  

---

## 1. Project Goal & High-Level Architecture

Traditional transaction fraud detection examines individual transactions in isolation (e.g., amount anomalies, velocity spikes, or merchant risk categories). However, modern financial fraud frequently operates via **coordinated fraud rings**—groups of colluding accounts sharing underlying infrastructure, cyclic transfer patterns, and burst activity at shared merchant gateways.

This project implements a hybrid DBMS architecture:
- **PostgreSQL**: Stores relational, normalized records ensuring strict ACID guarantees, constraints, and foreign-key integrity across customers, accounts, cards, merchants, and transactions.
- **MongoDB**: Acts as the dynamic graph and relationship layer, storing account adjacency lists, shared merchant edges, Bitcoin transaction flow graphs (Elliptic dataset), and the precomputed ML feature store.
- **Machine Learning Layer**: Combines standard tabular transaction attributes with topological network signals (degree centrality, temporal hops to prior fraud, 24-hour shared merchant counts, burst velocity) to classify fraud.
- **DBMS Latency Benchmark**: Directly benchmarks multi-hop graph traversal latency between MongoDB (`$graphLookup` & Document BFS) and PostgreSQL (Recursive Common Table Expressions).
- **Interactive UI (Upcoming)**: A FastAPI backend and React dashboard for analysts to inspect flagged fraud rings.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 DATASETS IN /data & /Datasets                          │
│  • Sparkov fraudTrain.csv + fraudTest.csv (1,852,394 credit card transactions)         │
│  • Elliptic Bitcoin Graph (203,769 nodes, 234,355 directed transaction edges)          │
└───────────────────────────┬───────────────────────────────────┬────────────────────────┘
                            │                                   │
                            ▼                                   ▼
               ┌─────────────────────────────┐     ┌─────────────────────────────┐
               │   POSTGRESQL (schema.sql)   │     │    MONGODB (Graph Layer)    │
               │   Database: `fraud_db`      │     │   Database: `fraud_ring_db` │
               ├─────────────────────────────┤     ├─────────────────────────────┤
               │ • customer (999 rows)       │     │ • account_graph (999 docs)  │
               │ • account (999 rows)        │     │ • merchant_links (529K docs)│
               │ • card (999 rows)           │     │ • elliptic_nodes (203K docs)│
               │ • merchant (693 rows)       │     │ • elliptic_edges (234K docs)│
               │ • transaction (1,852,394 r) │     │ • fraud_features (1.85M docs│
               │ • alert, analyst (reserved) │     └──────────────┬──────────────┘
               │ • device, ip_address (empty)│                    │
               └──────────────┬──────────────┘                    │
                              │                                   │
                              └─────────────────┬─────────────────┘
                                                ▼
               ┌─────────────────────────────────────────────────────────────────┐
               │                STEP 3: FEATURE EXTRACTION                       │
               │  • Sliding-window 24h merchant sharing counts                   │
               │  • Temporal BFS hops-to-prior-flagged (zero-leakage)            │
               │  • Account burst transaction velocity                           │
               │  • Parquet cache (`data/fraud_features.parquet` - 41 MB)        │
               └────────────────────────────────┬────────────────────────────────┘
                                                ▼
               ┌─────────────────────────────────────────────────────────────────┐
               │                 STEP 4: ML TRAINING & ABLATION                  │
               │  • Chronological Split: 85% Train (1.57M) / 15% Test (278K)     │
               │  • Model A (Baseline: Txn Only) vs Model B (Hybrid + Graph)     │
               │  • 99.88% Accuracy, 96.18% Precision, 80.6% FP reduction       │
               │  • Production Model: `models/fraud_model.joblib`                │
               └────────────────────────────────┬────────────────────────────────┘
                                                ▼
               ┌─────────────────────────────────────────────────────────────────┐
               │                 STEP 5: HYBRID DBMS BENCHMARK                   │
               │  • Multi-hop traversal latency comparison (k = 1, 2, 3 hops)    │
               │  • MongoDB Document BFS (0.64 ms, 735x faster)                  │
               │  • MongoDB $graphLookup (5.84 ms, 80x faster) vs PostgreSQL CTE │
               └────────────────────────────────┬────────────────────────────────┘
                                                ▼
               ┌─────────────────────────────────────────────────────────────────┐
               │             STEPS 6–8: EXTENSIONS, API & DASHBOARD              │
               │  • Step 6: Elliptic Bitcoin Graph GNN classification            │
               │  • Step 7: FastAPI REST backend (real-time scoring & alerts)    │
               │  • Step 8: React visual graph explorer for fraud rings          │
               └─────────────────────────────────────────────────────────────────┘
```

---

## 2. Repository Structure

```
.
├── schema.sql                 # Relational PostgreSQL DDL schema & indexes (9 tables)
├── REPORT.md                  # Comprehensive experimental report & ablation analysis
├── README.md                  # Unified project documentation & execution guide
├── data/                      # Generated feature artifacts (excluded from git)
│   └── fraud_features.parquet # Snappy-compressed feature store (41 MB, 1.85M rows)
├── models/                    # Trained model packages and evaluation metrics
│   ├── fraud_model.joblib     # Production hybrid XGBoost model package
│   ├── model_baseline.joblib  # Model A (transaction features only)
│   ├── model_hybrid.joblib    # Model B (transaction + graph features)
│   ├── metrics.json           # Raw ML metric results & feature importances
│   └── benchmark_results.json # Multi-hop query latency benchmark distributions
└── src/
    ├── loader_pg.py           # Step 0: PostgreSQL relational bulk loader & integrity checks
    ├── load_elliptic.py       # Step 1: Elliptic Bitcoin network graph loader for MongoDB
    ├── build_graph.py         # Step 2: SQL-derived shared merchant graph builder in MongoDB
    ├── extract_features.py    # Step 3: Zero-leakage temporal graph feature extractor
    ├── train_model.py         # Step 4: XGBoost training (85/15 split) & ablation study
    ├── benchmark.py           # Step 5: Multi-hop query latency benchmark (PG vs MongoDB)
    └── view_db.py             # Unified system state explorer (Postgres, Mongo, ML features)
```

---

## 3. Environment & Setup

### Prerequisites
- **macOS** or **Linux**
- **Python 3.12+** (tested with Python 3.14)
- **PostgreSQL 16+** running on `localhost:5432`
- **MongoDB 7+** running on `localhost:27017`

### 1. Database Initialization
```bash
# Create PostgreSQL database
createdb fraud_db

# Apply relational schema
psql -d fraud_db -f schema.sql
```

### 2. Python Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install required dependencies
pip install psycopg[binary] pymongo pandas numpy scipy scikit-learn xgboost networkx pyarrow joblib fastapi uvicorn
```

### 3. Verify Databases
```bash
# Verify system status across PostgreSQL, MongoDB, and ML layers
.venv/bin/python src/view_db.py
```

---

## 4. PostgreSQL Relational Schema (`schema.sql`)

PostgreSQL enforces ACID compliance, constraints, and relational consistency across 9 core entities:

| Table | Primary Key | Key Foreign Keys / Constraints | Description |
|---|---|---|---|
| `customer` | `customer_id` | `email UNIQUE` | Customer demographic records and KYC status |
| `account` | `account_id` | `customer_id` $\rightarrow$ `customer` | Bank accounts linked to customers |
| `card` | `card_id` | `account_id` $\rightarrow$ `account`, `card_number_hash UNIQUE` | Payment cards hashed with SHA-256 |
| `merchant` | `merchant_id` | `merchant_name UNIQUE` | Merchant names, coordinates (`merch_lat/long`), MCC codes |
| `device` | `device_id` | `device_fingerprint UNIQUE` | *Intentionally empty* (no synthetic/fabricated device data) |
| `ip_address` | `ip_id` | — | *Intentionally empty* (no synthetic/fabricated IP data) |
| `transaction` | `transaction_id` | `account_id`, `merchant_id`, `trans_num UNIQUE` | 1,852,394 transactions (9,651 fraud cases = 0.52%) |
| `alert` | `alert_id` | `transaction_id UNIQUE`, `analyst_id` | Real-time fraud detection alerts (Step 7 API) |
| `analyst` | `analyst_id` | — | Fraud analyst directory for alert investigations |

---

## 5. Step-by-Step Implementation & Run Guide

### Step 0: Relational Ingestion & Integrity Fixes
* **Script:** [`src/loader_pg.py`](src/loader_pg.py)
* **Execution:**
  ```bash
  .venv/bin/python src/loader_pg.py --truncate
  ```
* **Key Fixes Implemented:**
  - Ingests both `fraudTrain.csv` and `fraudTest.csv` with zero row truncation (**1,852,394 transactions**).
  - Uses true merchant coordinates (`merch_lat`, `merch_long`) rather than customer home coordinates.
  - Eliminates fabricated fake device/IP data per course specification.
  - Adds `trans_num UNIQUE` to support idempotent `ON CONFLICT DO NOTHING` reloads.

### Step 1: Elliptic Bitcoin Graph Ingestion
* **Script:** [`src/load_elliptic.py`](src/load_elliptic.py)
* **Execution:**
  ```bash
  .venv/bin/python src/load_elliptic.py
  ```
* **MongoDB Collections Populated:**
  - `elliptic_nodes`: **203,769** Bitcoin transactions (4,545 illicit, 42,019 licit, 157,205 unlabeled) with 166 features.
  - `elliptic_edges`: **234,355** directed Bitcoin payment flow edges.

### Step 2: SQL-Derived Shared-Merchant Graph Construction
* **Script:** [`src/build_graph.py`](src/build_graph.py)
* **Execution:**
  ```bash
  .venv/bin/python src/build_graph.py
  ```
* **Network Derived:** Accounts that transacted at the same merchant within a 24-hour window share an edge.
* **MongoDB Collections Populated:**
  - `merchant_links`: **529,328** account $\leftrightarrow$ merchant interaction edges.
  - `account_graph`: **999** account adjacency documents (average account degree: 834.7).

### Step 3: Zero-Leakage Feature Extraction
* **Script:** [`src/extract_features.py`](src/extract_features.py)
* **Execution:**
  ```bash
  .venv/bin/python src/extract_features.py --batch-size 50000
  ```
* **Performance:** Extracted all 1.85M feature vectors in **28.69s** (~171,626 documents/sec into MongoDB).
* **Zero Leakage:** Strictly enforces causal temporal validity—reachability to past fraud only evaluates events where $t_{\text{historical}} < t_{\text{txn}}$.
* **Outputs:**
  - MongoDB collection: `fraud_features` (1,852,394 documents, indexed).
  - Fast Parquet cache: `data/fraud_features.parquet` (41.0 MB).

### Step 4: Machine Learning Training & Graph Ablation Study
* **Script:** [`src/train_model.py`](src/train_model.py)
* **Execution:**
  ```bash
  .venv/bin/python src/train_model.py --split 0.85
  ```
* **Dataset Partition (Chronological Split):**
  - **85% Training Set:** 1,574,534 transactions (`2019-01-01` to `2020-10-03`) — 8,727 fraud cases (0.554%)
  - **15% Holdout Test Set:** 277,860 transactions (`2020-10-03` to `2020-12-31`) — 924 fraud cases (0.333%)

#### Ablation Results (Evaluated on the 277,860 Holdout Test Set)

| Metric | Model A (Txn Only) | Model B (Hybrid + Graph) | Delta / Graph Lift |
|---|---:|---:|---:|
| **Overall Accuracy** | **99.869%** | **99.877%** | **+0.008%** |
| **Precision (Fraud Class)** | **84.65%** | **96.18%** | **+11.53% Lift** |
| **Recall (Fraud Class)** | 74.03% | 65.48% | -8.55% |
| **F1-Score** | 0.7898 | 0.7791 | -0.0107 |
| **PR-AUC (Avg Precision)** | 0.8486 | 0.8476 | -0.0010 |
| **ROC-AUC** | 0.9973 | 0.9963 | -0.0010 |
| **False Positives (FP)** | **124** | **24** | **-100 (80.6% Reduction)** |
| **True Positives (TP)** | 684 | 605 | -79 |
| **False Negatives (FN)** | 240 | 319 | +79 |
| **True Negatives (TN)** | 276,812 | 276,912 | +100 |

* **Key Takeaway:** The graph layer **cuts false positives by 80.6%** (from 124 down to 24), elevating precision to **96.18%**.
* **Feature Importance:** `hops_to_flagged` is the **#1 predictive feature (32.65%)**, and graph features total **41.45% of overall model predictive power**.

### Step 5: Multi-Hop Traversal Latency Benchmark
* **Script:** [`src/benchmark.py`](src/benchmark.py)
* **Execution:**
  ```bash
  .venv/bin/python src/benchmark.py --trials 25
  ```
* **Query:** *"Find all distinct accounts connected to account $X$ within $k$ hops ($k \in \{1, 2, 3\}$)"*.

| Traversal Depth | Database & Query Engine | Mean Latency | Median (p50) | 95th Percentile (p95) | Speedup vs PostgreSQL |
|---|---|---:|---:|---:|---:|
| **1-Hop** | **MongoDB Document BFS** | **0.64 ms** | **0.55 ms** | **0.97 ms** | **735.0x faster** |
| | **MongoDB `$graphLookup`** | **5.84 ms** | **5.17 ms** | **8.71 ms** | **80.0x faster** |
| | **PostgreSQL Relational CTE** | 467.18 ms | 493.64 ms | 533.21 ms | Baseline |
| | *PostgreSQL Raw Ledger Join (1.85M rows)* | *2,989.77 ms* | *2,722.27 ms* | *4,251.07 ms* | *(4,670x slower than Mongo BFS)* |
|---|---|---:|---:|---:|---:|
| **2-Hop** | **MongoDB Document BFS** | **164.50 ms** | **161.67 ms** | **211.14 ms** | **5.9x faster** |
| | **MongoDB `$graphLookup`** | **144.64 ms** | **148.92 ms** | **162.37 ms** | **6.7x faster** |
| | **PostgreSQL Relational CTE** | 967.44 ms | 966.07 ms | 1,005.59 ms | Baseline |
|---|---|---:|---:|---:|---:|
| **3-Hop** | **MongoDB Document BFS** | **158.82 ms** | **154.25 ms** | **169.50 ms** | **11.5x faster** |
| | **MongoDB `$graphLookup`** | **162.36 ms** | **161.11 ms** | **171.27 ms** | **11.3x faster** |
| | **PostgreSQL Relational CTE** | 1,830.52 ms | 1,831.88 ms | 1,863.30 ms | Baseline |

---

## 6. System State Inspection Utility

To inspect live row counts, graph metrics, and sample feature vectors across both databases at any time:

```bash
.venv/bin/python src/view_db.py
```

This utility automatically audits:
1. **PostgreSQL Relational Tables**: Row counts across all 9 tables, customer accounts, and fraud transactions.
2. **MongoDB Graph Collections**: Document counts for `elliptic_nodes`, `elliptic_edges`, `merchant_links`, and `account_graph`.
3. **Graph Adjacency Metrics**: Degree distribution, min/max degrees, and sample neighbor arrays.
4. **Extracted Features**: Cache file status and live sample feature vector displaying both tabular and graph features.

---

## 7. Roadmap: Next Milestones

| Step | Milestone | Objectives | Status |
|---|---|---|---|
| **Step 0** | PostgreSQL Ingestion | Fixed loader, 1.85M transactions, zero synthetic data | ✅ Completed |
| **Step 1** | Elliptic Graph Loader | 203K nodes, 234K edges loaded into MongoDB | ✅ Completed |
| **Step 2** | Graph Layer Construction | 529K merchant edges, 999 account adjacencies | ✅ Completed |
| **Step 3** | Feature Extraction | 1.85M feature vectors in MongoDB & Parquet | ✅ Completed |
| **Step 4** | ML Model & Ablation | 85/15 split, 99.88% accuracy, 80.6% FP reduction | ✅ Completed |
| **Step 5** | DBMS Latency Benchmark | Multi-hop ($k=1,2,3$) PostgreSQL CTE vs MongoDB `$graphLookup` | ✅ Completed |
| **Step 6** | Elliptic GNN Experiment | Node classification on Bitcoin transaction graph | 🔜 **Next** |
| **Step 7** | FastAPI Backend | Endpoints for real-time risk scoring, alerts, and ring lookup | Pending |
| **Step 8** | Analyst Dashboard | React/Vite interface for fraud ring graph exploration | Pending |

---

*For detailed scientific discussion and complete experimental metrics, see [REPORT.md](REPORT.md).*
