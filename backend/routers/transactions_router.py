import os
import io
import csv
import uuid
import joblib
import numpy as np
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File

from backend.schemas import (
    CompanyTransactionCreate, CompanyTransactionItem,
    BatchIngestRequest, BatchIngestResponse, FeatureReason
)
from backend.auth import get_current_user, require_roles
from backend.database import get_db, get_mongo_db, get_known_fraud_accounts
from backend.features import compute_transaction_features
from backend.config import MODEL_PATH

router = APIRouter(prefix="/transactions", tags=["Company Transactions & AI Analysis"])

# Cache model bundle in memory
_model_bundle = None

def get_model():
    global _model_bundle
    if _model_bundle is None:
        if not os.path.exists(MODEL_PATH):
            raise RuntimeError(f"Trained model not found at {MODEL_PATH}")
        _model_bundle = joblib.load(MODEL_PATH)
    return _model_bundle

def get_or_create_account(cur, account_id: Optional[int] = None, account_number: Optional[str] = None, customer_name: Optional[str] = None):
    """Resolve an account by ID or account number, or auto-create customer and account handling unique constraints."""
    if account_id:
        cur.execute("""
            SELECT a.account_id, a.account_number, c.first_name || ' ' || c.last_name as customer_name
            FROM account a
            JOIN customer c ON c.customer_id = a.customer_id
            WHERE a.account_id = %s;
        """, (account_id,))
        row = cur.fetchone()
        if row:
            return row["account_id"], row["account_number"], row["customer_name"]

    if account_number:
        cur.execute("""
            SELECT a.account_id, a.account_number, c.first_name || ' ' || c.last_name as customer_name
            FROM account a
            JOIN customer c ON c.customer_id = a.customer_id
            WHERE a.account_number = %s;
        """, (account_number,))
        row = cur.fetchone()
        if row:
            return row["account_id"], row["account_number"], row["customer_name"]

    # Create new customer & account
    cust_name = customer_name.strip() if customer_name else "Bank Client"
    parts = cust_name.split(" ", 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else "Corp"
    email = f"{first_name.lower()}.{last_name.lower()}_{uuid.uuid4().hex[:6]}@companybank.com"

    cur.execute("""
        INSERT INTO customer (first_name, last_name, email, street, city, state, zip)
        VALUES (%s, %s, %s, '100 Financial Way', 'New York', 'NY', '10001')
        RETURNING customer_id;
    """, (first_name, last_name, email))
    cust_id = cur.fetchone()["customer_id"]

    acc_num = account_number if account_number else f"ACC-{uuid.uuid4().hex[:8].upper()}"
    try:
        cur.execute("""
            INSERT INTO account (customer_id, account_number, status)
            VALUES (%s, %s, 'active')
            ON CONFLICT (account_number) DO UPDATE
            SET status = account.status
            RETURNING account_id, account_number;
        """, (cust_id, acc_num))
        acc_row = cur.fetchone()
        acc_id = acc_row["account_id"]
        acc_num = acc_row["account_number"]
    except Exception:
        cur.execute("SELECT account_id, account_number FROM account WHERE account_number = %s;", (acc_num,))
        existing = cur.fetchone()
        if existing:
            acc_id = existing["account_id"]
            acc_num = existing["account_number"]
        else:
            raise

    return acc_id, acc_num, f"{first_name} {last_name}"

def get_or_create_merchant(cur, merchant_id: Optional[int] = None, merchant_name: Optional[str] = None):
    """Resolve a merchant by ID or name, or auto-create."""
    if merchant_id:
        cur.execute("SELECT merchant_id, merchant_name FROM merchant WHERE merchant_id = %s;", (merchant_id,))
        row = cur.fetchone()
        if row:
            return row["merchant_id"], row["merchant_name"]

    if merchant_name:
        cur.execute("SELECT merchant_id, merchant_name FROM merchant WHERE LOWER(merchant_name) = LOWER(%s);", (merchant_name.strip(),))
        row = cur.fetchone()
        if row:
            return row["merchant_id"], row["merchant_name"]

        cur.execute("""
            INSERT INTO merchant (merchant_name, category)
            VALUES (%s, 'Commercial & Banking')
            ON CONFLICT (merchant_name) DO UPDATE SET category = EXCLUDED.category
            RETURNING merchant_id, merchant_name;
        """, (merchant_name.strip(),))
        row = cur.fetchone()
        if row:
            return row["merchant_id"], row["merchant_name"]

    cur.execute("SELECT merchant_id, merchant_name FROM merchant LIMIT 1;")
    fallback = cur.fetchone()
    if fallback:
        return fallback["merchant_id"], fallback["merchant_name"]
    cur.execute("INSERT INTO merchant (merchant_name, category) VALUES ('Standard Counterparty', 'General') RETURNING merchant_id;")
    return cur.fetchone()["merchant_id"], "Standard Counterparty"

def evaluate_transaction_ai(
    account_id: int,
    merchant_id: int,
    amount: float,
    dt: datetime,
    cur,
    mongo,
    model,
    feature_cols: List[str],
    high_threshold: float,
    medium_threshold: float
):
    """Extract dynamic graph & velocity features using shared module and predict with calibrated thresholds."""
    fraud_accounts = get_known_fraud_accounts(cur)

    feature_dict = compute_transaction_features(
        account_id=account_id,
        merchant_id=merchant_id,
        amount=amount,
        dt=dt,
        cur=cur,
        mongo=mongo,
        fraud_accounts=fraud_accounts
    )

    feature_vector = np.array([[feature_dict[col] for col in feature_cols]])
    pred_prob = float(model.predict_proba(feature_vector)[0, 1])
    fraud_probability = round(pred_prob, 4)

    # Calibrated risk label
    if fraud_probability >= high_threshold:
        risk_label = "High"
    elif fraud_probability >= medium_threshold:
        risk_label = "Medium"
    else:
        risk_label = "Low"

    hops_to_flagged = feature_dict["hops_to_flagged"]
    prior_fraud_neighbors_count = feature_dict["prior_fraud_neighbors_count"]
    trans_velocity_24h = feature_dict["trans_velocity_24h"]

    top_reasons: List[FeatureReason] = []
    if hops_to_flagged <= 1:
        top_reasons.append(FeatureReason(
            feature="hops_to_flagged",
            description=f"Account is {int(hops_to_flagged)} hop(s) directly adjacent to flagged syndicate nodes.",
            value=float(hops_to_flagged),
            contribution_level="Critical"
        ))
    if prior_fraud_neighbors_count > 0:
        top_reasons.append(FeatureReason(
            feature="prior_fraud_neighbors_count",
            description=f"Direct merchant network overlap with {int(prior_fraud_neighbors_count)} confirmed fraud accounts.",
            value=float(prior_fraud_neighbors_count),
            contribution_level="High"
        ))
    if amount > 500.0:
        top_reasons.append(FeatureReason(
            feature="amount",
            description=f"Elevated transaction value (${amount:.2f}) vs normal expected baseline.",
            value=float(amount),
            contribution_level="High" if amount > 1000.0 else "Moderate"
        ))
    if trans_velocity_24h >= 3:
        top_reasons.append(FeatureReason(
            feature="trans_velocity_24h",
            description=f"High transaction frequency burst: {int(trans_velocity_24h)} transactions in past 24 hours.",
            value=float(trans_velocity_24h),
            contribution_level="High"
        ))
    if not top_reasons:
        top_reasons.append(FeatureReason(
            feature="baseline",
            description="Transaction characteristics align with standard commercial banking activity.",
            value=float(fraud_probability),
            contribution_level="Baseline"
        ))

    return fraud_probability, risk_label, top_reasons, feature_dict

@router.post("", response_model=CompanyTransactionItem)
def create_and_analyze_transaction(
    req: CompanyTransactionCreate,
    conn = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Ingest a company/bank transaction record and immediately analyze with the AI fraud model.
    Saves to PostgreSQL (source='company') with predicted_fraud and fraud_probability.
    Keeps is_fraud = false until analyst confirmed.
    """
    bundle = get_model()
    model = bundle["model"]
    feature_cols = bundle["feature_cols"]

    high_threshold = float(bundle.get("threshold", 0.9735))
    medium_threshold = round(high_threshold * 0.5, 4)

    # Parse timestamp
    if req.txn_timestamp:
        try:
            dt = datetime.fromisoformat(req.txn_timestamp.replace("Z", "+00:00"))
        except Exception:
            dt = datetime.now(timezone.utc)
    else:
        dt = datetime.now(timezone.utc)

    cur = conn.cursor()
    mongo = get_mongo_db()

    # Resolve account and merchant
    acc_id, acc_num, cust_name = get_or_create_account(
        cur, req.account_id, req.account_number, req.customer_name
    )
    merch_id, merch_name = get_or_create_merchant(
        cur, req.merchant_id, req.merchant_name
    )

    # Run AI evaluation
    prob, risk_label, reasons, _ = evaluate_transaction_ai(
        acc_id, merch_id, req.amount, dt, cur, mongo, model, feature_cols,
        high_threshold, medium_threshold
    )
    predicted_fraud = (prob >= high_threshold)

    # Insert into PostgreSQL with source='company', predicted_fraud, fraud_probability, is_fraud=False
    trans_num = f"cmp_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:6]}"
    iso_time_str = dt.strftime("%Y-%m-%d %H:%M:%S")

    cur.execute("""
        INSERT INTO transaction (account_id, merchant_id, trans_num, amount, txn_timestamp, source, predicted_fraud, fraud_probability, is_fraud)
        VALUES (%s, %s, %s, %s, %s, 'company', %s, %s, false)
        RETURNING transaction_id, txn_timestamp;
    """, (acc_id, merch_id, trans_num, req.amount, iso_time_str, predicted_fraud, prob))
    tx_row = cur.fetchone()
    tx_id = tx_row["transaction_id"]
    created_at_str = str(tx_row["txn_timestamp"])

    # If High Risk, automatically generate Alert
    alert_id = None
    if risk_label == "High":
        note_text = req.notes or f"Automated AI Flag: XGBoost probability {prob:.2%}. {reasons[0].description}"
        cur.execute("""
            INSERT INTO alert (transaction_id, analyst_id, fraud_probability, risk_label, status, note)
            VALUES (%s, %s, %s, %s, 'open', %s)
            RETURNING alert_id;
        """, (tx_id, current_user.get("analyst_id"), prob, risk_label, note_text))
        al_row = cur.fetchone()
        if al_row:
            alert_id = al_row["alert_id"]

    conn.commit()
    cur.close()

    return CompanyTransactionItem(
        transaction_id=tx_id,
        trans_num=trans_num,
        account_id=acc_id,
        account_number=acc_num,
        customer_name=cust_name,
        merchant_id=merch_id,
        merchant_name=merch_name,
        amount=req.amount,
        txn_timestamp=iso_time_str,
        fraud_probability=prob,
        risk_label=risk_label,
        is_fraud=False,
        alert_id=alert_id,
        top_reasons=reasons,
        created_at=created_at_str
    )

def execute_batch_transactions(
    conn,
    cur,
    mongo,
    transactions: List[CompanyTransactionCreate],
    current_user: dict
) -> BatchIngestResponse:
    """Helper to process a list of transaction objects with row-level savepoints and return BatchIngestResponse."""
    bundle = get_model()
    model = bundle["model"]
    feature_cols = bundle["feature_cols"]
    high_threshold = float(bundle.get("threshold", 0.9735))
    medium_threshold = round(high_threshold * 0.5, 4)

    results: List[CompanyTransactionItem] = []
    high_cnt = 0
    med_cnt = 0
    low_cnt = 0
    alerts_created = 0

    for idx, item in enumerate(transactions):
        cur.execute(f"SAVEPOINT sp_{idx};")
        try:
            if item.txn_timestamp:
                try:
                    dt = datetime.fromisoformat(item.txn_timestamp.replace("Z", "+00:00"))
                except Exception:
                    dt = datetime.now(timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            acc_id, acc_num, cust_name = get_or_create_account(
                cur, item.account_id, item.account_number, item.customer_name
            )
            merch_id, merch_name = get_or_create_merchant(
                cur, item.merchant_id, item.merchant_name
            )

            prob, risk_label, reasons, _ = evaluate_transaction_ai(
                acc_id, merch_id, item.amount, dt, cur, mongo, model, feature_cols,
                high_threshold, medium_threshold
            )
            predicted_fraud = (prob >= high_threshold)

            if risk_label == "High":
                high_cnt += 1
            elif risk_label == "Medium":
                med_cnt += 1
            else:
                low_cnt += 1

            trans_num = f"cmp_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:6]}"
            iso_time_str = dt.strftime("%Y-%m-%d %H:%M:%S")

            cur.execute("""
                INSERT INTO transaction (account_id, merchant_id, trans_num, amount, txn_timestamp, source, predicted_fraud, fraud_probability, is_fraud)
                VALUES (%s, %s, %s, %s, %s, 'company', %s, %s, false)
                RETURNING transaction_id, txn_timestamp;
            """, (acc_id, merch_id, trans_num, item.amount, iso_time_str, predicted_fraud, prob))
            tx_row = cur.fetchone()
            tx_id = tx_row["transaction_id"]
            created_at_str = str(tx_row["txn_timestamp"])

            alert_id = None
            if risk_label == "High":
                note_text = item.notes or f"Batch Ingestion: XGBoost probability {prob:.2%}. {reasons[0].description}"
                cur.execute("""
                    INSERT INTO alert (transaction_id, analyst_id, fraud_probability, risk_label, status, note)
                    VALUES (%s, %s, %s, %s, 'open', %s)
                    RETURNING alert_id;
                """, (tx_id, current_user.get("analyst_id"), prob, risk_label, note_text))
                al_row = cur.fetchone()
                if al_row:
                    alert_id = al_row["alert_id"]
                    alerts_created += 1

            cur.execute(f"RELEASE SAVEPOINT sp_{idx};")

            results.append(CompanyTransactionItem(
                transaction_id=tx_id,
                trans_num=trans_num,
                account_id=acc_id,
                account_number=acc_num,
                customer_name=cust_name,
                merchant_id=merch_id,
                merchant_name=merch_name,
                amount=item.amount,
                txn_timestamp=iso_time_str,
                fraud_probability=prob,
                risk_label=risk_label,
                is_fraud=False,
                alert_id=alert_id,
                top_reasons=reasons,
                created_at=created_at_str
            ))
        except Exception as e:
            print(f"[BATCH INGESTION WARNING] Row {idx} skipped: {type(e).__name__}: {e}")
            cur.execute(f"ROLLBACK TO SAVEPOINT sp_{idx};")
            continue

    conn.commit()
    cur.close()

    return BatchIngestResponse(
        total_ingested=len(results),
        high_risk_count=high_cnt,
        medium_risk_count=med_cnt,
        low_risk_count=low_cnt,
        alerts_created=alerts_created,
        results=results
    )

@router.post("/batch", response_model=BatchIngestResponse)
def batch_ingest_transactions(
    req: BatchIngestRequest,
    conn = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Ingest multiple company/bank transaction records in batch (max 200) and run AI scoring on each.
    Handles individual bad rows gracefully with savepoints.
    """
    if len(req.transactions) > 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch size {len(req.transactions)} exceeds maximum allowed limit of 200 transactions."
        )

    cur = conn.cursor()
    mongo = get_mongo_db()
    return execute_batch_transactions(conn, cur, mongo, req.transactions, current_user)

@router.post("/upload-csv", response_model=BatchIngestResponse)
async def upload_transactions_csv(
    file: UploadFile = File(...),
    conn = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload a CSV file containing company/bank transaction records.
    Parses headers or positional columns, and evaluates each record with the XGBoost model.
    """
    filename = file.filename or "upload.csv"
    if not filename.lower().endswith(".csv") and file.content_type not in (
        "text/csv", "application/vnd.ms-excel", "text/plain", "application/csv"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a valid .csv file."
        )

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded CSV file is empty.")

    reader = csv.reader(io.StringIO("\n".join(lines)))
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No readable rows found in CSV.")

    # Check for header
    header = [h.strip().lower().replace(" ", "_") for h in rows[0]]
    has_header = False
    col_map = {}
    if any(h in header for h in ["account", "account_number", "customer", "customer_name", "amount", "merchant", "merchant_name"]):
        has_header = True
        for idx, col in enumerate(header):
            col_map[col] = idx

    data_rows = rows[1:] if has_header else rows
    if not data_rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV contains only a header row.")

    if len(data_rows) > 300:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV file contains {len(data_rows)} rows. Maximum allowed per upload is 300 rows."
        )

    transactions: List[CompanyTransactionCreate] = []
    for r_idx, row in enumerate(data_rows):
        if not row or all(not cell.strip() for cell in row):
            continue

        try:
            if has_header:
                def get_val(names, default=None):
                    for name in names:
                        if name in col_map and col_map[name] < len(row):
                            v = row[col_map[name]].strip()
                            if v:
                                return v
                    return default

                acc_num = get_val(["account_number", "account_id", "account", "acc_num"], f"ACC-CSV-{r_idx+1}")
                cust_name = get_val(["customer_name", "customer", "client_name", "name"], "Bank Client")
                merch_name = get_val(["merchant_name", "merchant", "counterparty", "vendor"], "Commercial Merchant")
                amt_str = get_val(["amount", "amt", "transaction_amount", "value"], "50.0")
                ts_str = get_val(["txn_timestamp", "timestamp", "datetime", "date", "time"], None)
                notes_str = get_val(["notes", "note", "description"], "CSV Upload")

                try:
                    amt = float(amt_str.replace("$", "").replace(",", ""))
                except Exception:
                    amt = 50.0
            else:
                acc_num = row[0].strip() if len(row) > 0 and row[0].strip() else f"ACC-CSV-{r_idx+1}"
                cust_name = row[1].strip() if len(row) > 1 and row[1].strip() else "Bank Client"
                merch_name = row[2].strip() if len(row) > 2 and row[2].strip() else "Commercial Merchant"
                try:
                    amt = float(row[3].strip().replace("$", "").replace(",", "")) if len(row) > 3 else 50.0
                except Exception:
                    amt = 50.0
                ts_str = row[4].strip() if len(row) > 4 and row[4].strip() else None
                notes_str = row[5].strip() if len(row) > 5 and row[5].strip() else "CSV Upload"

            transactions.append(CompanyTransactionCreate(
                account_number=acc_num,
                customer_name=cust_name,
                merchant_name=merch_name,
                amount=amt,
                txn_timestamp=ts_str,
                notes=notes_str
            ))
        except Exception:
            continue

    if not transactions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not parse any valid transaction rows from the CSV file."
        )

    cur = conn.cursor()
    mongo = get_mongo_db()
    return execute_batch_transactions(conn, cur, mongo, transactions, current_user)

@router.get("", response_model=List[CompanyTransactionItem])
def list_company_transactions(
    risk_label: Optional[str] = Query(None, pattern="^(Low|Medium|High)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    conn = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve user-added company/bank transaction records with their real stored AI analysis scores.
    Correctly filters by risk label across all transactions (including Low/Medium without alerts).
    """
    bundle = get_model()
    high_threshold = float(bundle.get("threshold", 0.9735))
    medium_threshold = round(high_threshold * 0.5, 4)

    cur = conn.cursor()

    sql = """
        SELECT
            t.transaction_id,
            t.trans_num,
            t.account_id,
            a.account_number,
            c.first_name || ' ' || c.last_name as customer_name,
            t.merchant_id,
            m.merchant_name,
            t.amount,
            t.txn_timestamp::text as txn_timestamp,
            t.is_fraud,
            t.predicted_fraud,
            t.fraud_probability::float as fraud_probability,
            t.txn_timestamp::text as created_at,
            al.alert_id,
            al.risk_label as alert_risk_label
        FROM transaction t
        JOIN account a ON a.account_id = t.account_id
        JOIN customer c ON c.customer_id = a.customer_id
        JOIN merchant m ON m.merchant_id = t.merchant_id
        LEFT JOIN alert al ON al.transaction_id = t.transaction_id
        WHERE t.source = 'company'
    """
    params = []

    if risk_label == "High":
        sql += " AND (al.risk_label = 'High' OR t.fraud_probability >= %s)"
        params.append(high_threshold)
    elif risk_label == "Medium":
        sql += " AND (al.risk_label = 'Medium' OR (t.fraud_probability >= %s AND t.fraud_probability < %s))"
        params.extend([medium_threshold, high_threshold])
    elif risk_label == "Low":
        sql += " AND (al.risk_label = 'Low' OR t.fraud_probability < %s OR t.fraud_probability IS NULL)"
        params.append(medium_threshold)

    sql += " ORDER BY t.transaction_id DESC LIMIT %s OFFSET %s;"
    params.extend([limit, offset])

    cur.execute(sql, tuple(params))
    rows = cur.fetchall()
    cur.close()

    results = []
    for r in rows:
        prob = float(r["fraud_probability"]) if r["fraud_probability"] is not None else 0.0
        if r["alert_risk_label"]:
            label = r["alert_risk_label"]
        elif prob >= high_threshold:
            label = "High"
        elif prob >= medium_threshold:
            label = "Medium"
        else:
            label = "Low"

        results.append(CompanyTransactionItem(
            transaction_id=r["transaction_id"],
            trans_num=r["trans_num"],
            account_id=r["account_id"],
            account_number=r["account_number"],
            customer_name=r["customer_name"],
            merchant_id=r["merchant_id"],
            merchant_name=r["merchant_name"],
            amount=float(r["amount"]),
            txn_timestamp=r["txn_timestamp"],
            fraud_probability=prob,
            risk_label=label,
            is_fraud=bool(r["is_fraud"]),
            alert_id=r["alert_id"],
            top_reasons=[],
            created_at=r["created_at"]
        ))
    return results

@router.post("/demo-batch", response_model=BatchIngestResponse)
def load_company_demo_batch(
    conn = Depends(get_db),
    current_user: dict = Depends(require_roles(["admin"]))
):
    """
    Admin-only endpoint: injects a realistic set of 6 bank transactions
    so analysts can immediately evaluate the AI scoring and dashboard metrics.
    """
    demo_data = [
        CompanyTransactionCreate(
            account_number="ACC-CORP-101",
            customer_name="Acme Logistics LLC",
            merchant_name="Standard Oil Fleet",
            amount=84.50,
            notes="Routine fleet fueling payment"
        ),
        CompanyTransactionCreate(
            account_number="ACC-CORP-102",
            customer_name="Apex Global Trade",
            merchant_name="Amazon Web Services",
            amount=320.00,
            notes="Monthly cloud infrastructure invoice"
        ),
        CompanyTransactionCreate(
            account_number="ACC-CORP-103",
            customer_name="Summit Capital Partners",
            merchant_name="Stripe Digital Gateway",
            amount=42.10,
            notes="SaaS subscription charge"
        ),
        CompanyTransactionCreate(
            account_id=787,
            account_number="ACC-787-SYN",
            customer_name="David Martinez",
            merchant_id=1,
            merchant_name="Electronics Supercenter",
            amount=1450.00,
            notes="Flagged syndicate test: High amount on dense merchant node"
        ),
        CompanyTransactionCreate(
            account_id=787,
            account_number="ACC-787-SYN",
            customer_name="David Martinez",
            merchant_id=2,
            merchant_name="Prepaid Mobile Top-Up",
            amount=980.00,
            notes="Rapid subsequent velocity burst within same 24 hours"
        ),
        CompanyTransactionCreate(
            account_number="ACC-CORP-104",
            customer_name="Horizon Retailers",
            merchant_name="Wholesale Supply Co",
            amount=215.30,
            notes="Standard wholesale supplier purchase"
        ),
    ]

    return batch_ingest_transactions(
        BatchIngestRequest(transactions=demo_data),
        conn=conn,
        current_user=current_user
    )

@router.delete("/clear")
def clear_company_transactions(
    conn = Depends(get_db),
    current_user: dict = Depends(require_roles(["admin"]))
):
    """
    Admin-only endpoint: Clear all user-added company transactions and alerts.
    Leaves the pre-trained ML model and training dataset untouched.
    """
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM alert
        WHERE transaction_id IN (
            SELECT transaction_id FROM transaction WHERE source = 'company'
        );
    """)
    cur.execute("DELETE FROM transaction WHERE source = 'company';")
    conn.commit()
    cur.close()

    return {"message": "Company transaction records and alerts cleared successfully."}
