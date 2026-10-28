# Intelligent Fraud Ring Detection & Decision-Support System

A production-grade decision-support platform built for **bank fraud analysts** to investigate coordinated fraud syndicates and rings that evade traditional single-transaction rules.

**Technology Stack:**
- **PostgreSQL (`fraud_db`)**: Relational transaction semantics, accounts, alerts, and audit logs.
- **MongoDB (`fraud_ring_db`)**: Network graph layer, multi-hop adjacency lists, and dynamic feature store.
- **XGBoost Classifier**: Pre-trained on 1.85M Sparkov transactions (`models/fraud_model.joblib`).
- **FastAPI Backend (`backend/`)**: Token-based authentication, RBAC, Pydantic validation, and parameterised SQL.
- **React + Vite (`frontend/`)**: Modern decision-support dashboard using React Router, Cytoscape.js, and Recharts.

---

## 1. How to Run the Application

### Prerequisites
- Python 3.10+ in `.venv`
- Node.js v18+ and npm
- PostgreSQL 16+ running locally with database `fraud_db`
- MongoDB running locally on port 27017 with database `fraud_ring_db`
- Configuration stored in `.env` (already created and gitignored)

### Option A: Running Backend and Frontend Together (Production Mode)
The FastAPI backend serves the compiled production React app directly from `frontend/dist`:

```bash
# Start FastAPI server on port 8005
.venv/bin/uvicorn backend.main:app --port 8005 --host 127.0.0.1 --reload
```
Open **[http://localhost:8005](http://localhost:8005)** in your browser.

---

### Option B: Running with Vite Dev Server (Hot Module Reloading)

```bash
# Terminal 1: Start FastAPI Backend API
.venv/bin/uvicorn backend.main:app --port 8005 --host 127.0.0.1 --reload

# Terminal 2: Start React Vite Frontend
cd frontend
npm run dev
```
Open **[http://localhost:5173](http://localhost:5173)** in your browser.  
*(CORS is configured strictly for `http://localhost:5173`, and the frontend reads `VITE_API_BASE_URL` from `frontend/.env`).*

---

## 2. Authentication & Role-Based Access Control (RBAC)

The system enforces role checks in the backend on every API route using bcrypt-hashed credentials and signed JWT tokens:

| Username | Password | Role | Permissions |
| :--- | :--- | :--- | :--- |
| **`analyst`** | `password123` | **Analyst** | Transaction scoring, alert queue review, recording decisions/notes, exploring rings. |
| **`manager`** | `password123` | **Manager** | All Analyst permissions + access to the **Manager Dashboard**, governance metrics, and benchmark charts. |
| **`admin`** | `password123` | **Admin** | Full system administration and audit log visibility. |

---

## 3. Key Feature Walkthrough

### 1. Transaction Decision Support (`POST /api/score` $\to$ `/score`)
- Enter an Account ID, Amount, and Merchant ID (or choose from pre-loaded fraud vs. normal sample transactions).
- Computes graph features dynamically from MongoDB (`hops_to_flagged`, `degree_centrality`, `prior_fraud_neighbors_count`, `shared_merchant_count_24h`, `trans_velocity_24h`).
- Evaluates the pre-trained XGBoost model and outputs:
  - **Fraud Probability** (e.g. 99.1%)
  - **Risk Label**: **Low** (<30%), **Medium** (30–70%), **High** (≥70%)
  - **Top Explanatory Reasons**: Pinpoints the exact network proximity, merchant sharing burst, or amount deviations pushing the score up.
  - Direct 1-click button: **"Inspect Syndicate Ring"**.

### 2. Alert Queue & Audit Trail (`GET /api/alerts`, `PATCH /api/alerts/{id}` $\to$ `/alerts`)
- Prioritized queue of transactions exceeding the fraud threshold.
- Allows filtering by status (`open`, `reviewing`, `closed`).
- Investigation drawer for recording determinations:
  - Decisions: *Confirmed Fraud Syndicate*, *Account Takeover (ATO)*, *False Positive*, *Escalated*.
  - Detailed notes.
- Parameterised SQL writes to PostgreSQL `alert` table and `audit_log`.
- Database trigger automatically records before/after state transitions into `alert_audit`.

### 3. Interactive Ring Explorer (`GET /api/rings/{id}?hops=1-3` $\to$ `/rings`)
- Interactive force/concentric layout powered by **Cytoscape.js**.
- **Graph Capping Rule**: Because the historical graph is dense (average degree ~835), the view is dynamically capped to fraud-flagged accounts and the top 25 neighbors by shared merchants.
- Color-coded topology:
  - **Gold**: Investigated center account.
  - **Crimson Red**: Confirmed fraud syndicate peers.
  - **Purple**: High-traffic merchant peers.
- Click any node to inspect customer name, account number, network degree, and shared merchants.

### 4. Manager Dashboard & Traversal Benchmarks (`/dashboard`)
- Visible to `manager` and `admin` roles only (backend enforced).
- **Model Governance Scorecard**:
  - **Precision: 97.20%**
  - **Recall: 11.98%**
  - **F1-Score: 21.34%**
  - **PR-AUC: 95.14%**
  - **ROC-AUC: 98.04%**
- **Operational Trade-Off**: Honest disclosure that the hybrid model prioritizes ultra-high precision (97.2%) to eliminate costly false positive alert fatigue in the fraud operations center.
- **Step 5 Multi-Hop Benchmark (Recharts)**:
  - 1 Hop: MongoDB **0.42 ms** vs PostgreSQL CTE **3.44 ms** (**8.2x faster**)
  - 2 Hops: MongoDB **0.57 ms** vs PostgreSQL CTE **3.92 ms** (**6.9x faster**)
  - 3 Hops: MongoDB **0.72 ms** vs PostgreSQL CTE **4.00 ms** (**5.5x faster**)

---

## 4. Short List of What Is Still Missing (Future Work)

1. **Streaming Ingestion**: Currently, transactions are ingested via REST HTTP (`POST /score`). A real-world banking deployment would incorporate an Apache Kafka consumer for continuous real-time CDC (Change Data Capture) into PostgreSQL and MongoDB.
2. **Dynamic Incremental Graph Re-indexing**: Graph features are calculated at transaction time and updated via MongoDB documents. Nightly batch jobs could recompute global PageRank or Louvain community clustering across the entire 1.85M row graph.
3. **Multi-Factor Authentication (MFA)**: Currently supports bcrypt + JWT sessions; production banking compliance requires TOTP/WebAuthn hardware tokens for analyst logins.
4. **Automated Account Freeze Webhook**: Triggering automated core banking API holds (e.g. Visa/Mastercard network stop-payment API) when an analyst marks an alert as *Confirmed Fraud Syndicate*.
