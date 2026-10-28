import os
import joblib
import numpy as np
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from backend.schemas import (
    TransactionScoreRequest, TransactionScoreResponse,
    FeatureReason, SampleTransactionOption
)
from backend.auth import get_current_user
from backend.database import get_pg_connection, get_mongo_db
from backend.config import MODEL_PATH

router = APIRouter(prefix="/score", tags=["Transaction Scoring"])

# Cache model bundle in memory
_model_bundle = None

def get_model():
    global _model_bundle
    if _model_bundle is None:
        if not os.path.exists(MODEL_PATH):
            raise RuntimeError(f"Trained model not found at {MODEL_PATH}")
        _model_bundle = joblib.load(MODEL_PATH)
    return _model_bundle

@router.post("", response_model=TransactionScoreResponse)
def score_transaction(
    req: TransactionScoreRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Score a transaction using the trained XGBoost model and dynamic MongoDB graph features.
    Computes graph features, predicts fraud probability, assigns risk label,
    and returns feature contribution reasons for decision support.
    """
    bundle = get_model()
    model = bundle["model"]
    feature_cols = bundle["feature_cols"]

    # 1. Parse timestamp
    if req.txn_timestamp:
        try:
            dt = datetime.fromisoformat(req.txn_timestamp.replace("Z", "+00:00"))
        except Exception:
            dt = datetime.now(timezone.utc)
    else:
        dt = datetime.now(timezone.utc)

    hour = dt.hour
    day_of_week = dt.weekday()

    # 2. Extract Graph Features from MongoDB & PostgreSQL
    mongo = get_mongo_db()
    conn = get_pg_connection()
    cur = conn.cursor()

    # Known fraud accounts from PostgreSQL (cached or query)
    cur.execute("SELECT DISTINCT account_id FROM transaction WHERE is_fraud = true;")
    fraud_accounts = set(r["account_id"] for r in cur.fetchall())

    # Get account graph document from MongoDB
    acc_doc = mongo.account_graph.find_one({"account_id": req.account_id})
    neighbors = acc_doc.get("neighbors", []) if acc_doc else []
    degree = acc_doc.get("degree", len(neighbors)) if acc_doc else 0
    degree_centrality = float(degree) / 999.0

    # Prior fraud neighbors count
    prior_fraud_neighbors_count = sum(1 for n in neighbors if n.get("account_id") in fraud_accounts)

    # Shortest hops to flagged fraud account
    if req.account_id in fraud_accounts:
        hops_to_flagged = 0
    elif prior_fraud_neighbors_count > 0:
        hops_to_flagged = 1
    else:
        # Check 2-hop neighbors
        neighbor_ids = [n.get("account_id") for n in neighbors[:50]]
        two_hop_flagged = mongo.account_graph.count_documents({
            "account_id": {"$in": neighbor_ids},
            "neighbors.account_id": {"$in": list(fraud_accounts)}
        })
        hops_to_flagged = 2 if two_hop_flagged > 0 else 3

    # Velocity features from PostgreSQL
    iso_time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        SELECT COUNT(*) as velocity
        FROM transaction
        WHERE account_id = %s
          AND txn_timestamp BETWEEN (%s::timestamp - interval '24 hours') AND %s::timestamp;
    """, (req.account_id, iso_time_str, iso_time_str))
    vel_row = cur.fetchone()
    trans_velocity_24h = vel_row["velocity"] if vel_row else 0

    # Shared merchant count 24h
    cur.execute("""
        SELECT COUNT(DISTINCT account_id) as shared_cnt
        FROM transaction
        WHERE merchant_id = %s
          AND txn_timestamp BETWEEN (%s::timestamp - interval '24 hours') AND %s::timestamp
          AND account_id <> %s;
    """, (req.merchant_id, iso_time_str, iso_time_str, req.account_id))
    merch_row = cur.fetchone()
    shared_merchant_count_24h = merch_row["shared_cnt"] if merch_row else 0

    # 3. Build Feature Vector according to saved model schema:
    # ['amount', 'hour', 'day_of_week', 'hops_to_flagged', 'degree_centrality',
    #  'shared_merchant_count_24h', 'trans_velocity_24h', 'prior_fraud_neighbors_count']
    feature_dict = {
        "amount": float(req.amount),
        "hour": int(hour),
        "day_of_week": int(day_of_week),
        "hops_to_flagged": float(hops_to_flagged),
        "degree_centrality": float(degree_centrality),
        "shared_merchant_count_24h": float(shared_merchant_count_24h),
        "trans_velocity_24h": float(trans_velocity_24h),
        "prior_fraud_neighbors_count": float(prior_fraud_neighbors_count)
    }

    feature_vector = np.array([[feature_dict[col] for col in feature_cols]])

    # 4. Model Inference
    pred_prob = float(model.predict_proba(feature_vector)[0, 1])
    fraud_probability = round(pred_prob, 4)

    # Determine risk label
    if fraud_probability >= 0.70:
        risk_label = "High"
    elif fraud_probability >= 0.30:
        risk_label = "Medium"
    else:
        risk_label = "Low"

    # 5. Compute Top Reasons (Explainability for Analyst Decision Support)
    top_reasons: List[FeatureReason] = []

    # Reason 1: Network Proximity to Fraud (Strongest XGBoost predictor ~80.8% importance)
    if hops_to_flagged == 0:
        top_reasons.append(FeatureReason(
            feature="hops_to_flagged",
            description="Account has direct confirmed prior fraud activity (0 hops to flagged).",
            value=float(hops_to_flagged),
            contribution_level="Critical"
        ))
    elif hops_to_flagged == 1:
        top_reasons.append(FeatureReason(
            feature="hops_to_flagged",
            description="Account is directly linked (1 hop) to confirmed fraud accounts through shared merchant history.",
            value=float(hops_to_flagged),
            contribution_level="Critical"
        ))
    else:
        top_reasons.append(FeatureReason(
            feature="hops_to_flagged",
            description=f"Account is {hops_to_flagged} hops removed from nearest flagged syndicate accounts.",
            value=float(hops_to_flagged),
            contribution_level="Moderate" if hops_to_flagged <= 2 else "Baseline"
        ))

    # Reason 2: Fraud Neighbors in Merchant Graph
    if prior_fraud_neighbors_count > 50:
        top_reasons.append(FeatureReason(
            feature="prior_fraud_neighbors_count",
            description=f"Dense syndicate overlap: Account clusters with {prior_fraud_neighbors_count} confirmed fraudulent peers.",
            value=float(prior_fraud_neighbors_count),
            contribution_level="High"
        ))
    elif prior_fraud_neighbors_count > 0:
        top_reasons.append(FeatureReason(
            feature="prior_fraud_neighbors_count",
            description=f"Account shares merchant transacting patterns with {prior_fraud_neighbors_count} fraudulent accounts.",
            value=float(prior_fraud_neighbors_count),
            contribution_level="Moderate"
        ))

    # Reason 3: Transaction Amount
    if req.amount > 500.0:
        top_reasons.append(FeatureReason(
            feature="amount",
            description=f"Unusually high transaction amount (${req.amount:.2f}) vs normal median ($45).",
            value=float(req.amount),
            contribution_level="High"
        ))
    elif req.amount > 200.0:
        top_reasons.append(FeatureReason(
            feature="amount",
            description=f"Elevated transaction amount (${req.amount:.2f}).",
            value=float(req.amount),
            contribution_level="Moderate"
        ))

    # Reason 4: Late-night hour anomaly
    if hour in [0, 1, 2, 3, 4, 5]:
        top_reasons.append(FeatureReason(
            feature="hour",
            description=f"Transaction initiated during high-risk night window ({hour:02d}:00).",
            value=float(hour),
            contribution_level="Moderate"
        ))

    # Reason 5: Velocity bursts
    if trans_velocity_24h > 5:
        top_reasons.append(FeatureReason(
            feature="trans_velocity_24h",
            description=f"High transaction velocity: {trans_velocity_24h} transactions in past 24 hours.",
            value=float(trans_velocity_24h),
            contribution_level="High"
        ))

    # 6. Save Alert if requested and risk is High
    alert_created = False
    alert_id = None
    if req.save_alert and risk_label == "High":
        # Create or fetch transaction row
        cur.execute("""
            INSERT INTO transaction (account_id, merchant_id, trans_num, amount, txn_timestamp, is_fraud)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (trans_num) DO UPDATE SET amount = EXCLUDED.amount
            RETURNING transaction_id;
        """, (
            req.account_id, req.merchant_id,
            f"sim_{int(datetime.now().timestamp() * 1000)}",
            req.amount, iso_time_str, False
        ))
        tx_row = cur.fetchone()
        if tx_row:
            tx_id = tx_row["transaction_id"]
            cur.execute("""
                INSERT INTO alert (transaction_id, analyst_id, fraud_probability, risk_label, status, note)
                VALUES (%s, %s, %s, %s, 'open', %s)
                ON CONFLICT (transaction_id) DO UPDATE
                SET fraud_probability = EXCLUDED.fraud_probability, risk_label = EXCLUDED.risk_label
                RETURNING alert_id;
            """, (
                tx_id, current_user["analyst_id"], fraud_probability, risk_label,
                f"Automated Alert: XGBoost score {fraud_probability:.2%}. Primary factor: {top_reasons[0].description}"
            ))
            al_row = cur.fetchone()
            if al_row:
                alert_created = True
                alert_id = al_row["alert_id"]
                conn.commit()

    cur.close()
    conn.close()

    return TransactionScoreResponse(
        account_id=req.account_id,
        merchant_id=req.merchant_id,
        amount=req.amount,
        fraud_probability=fraud_probability,
        risk_label=risk_label,
        top_reasons=top_reasons,
        graph_features=feature_dict,
        alert_created=alert_created,
        alert_id=alert_id,
        evaluated_at=datetime.now(timezone.utc).isoformat()
    )

@router.get("/sample-transactions", response_model=List[SampleTransactionOption])
def get_sample_transactions(current_user: dict = Depends(get_current_user)):
    """
    Returns a curated set of sample transactions from PostgreSQL
    for quick selection and decision-support testing by the analyst.
    """
    conn = get_pg_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            t.transaction_id,
            t.trans_num,
            t.account_id,
            c.first_name || ' ' || c.last_name as customer_name,
            t.merchant_id,
            m.merchant_name,
            t.amount,
            t.txn_timestamp,
            t.is_fraud
        FROM transaction t
        JOIN account a ON a.account_id = t.account_id
        JOIN customer c ON c.customer_id = a.customer_id
        JOIN merchant m ON m.merchant_id = t.merchant_id
        WHERE t.is_fraud = true
        LIMIT 5;
    """)
    fraud_samples = cur.fetchall()

    cur.execute("""
        SELECT
            t.transaction_id,
            t.trans_num,
            t.account_id,
            c.first_name || ' ' || c.last_name as customer_name,
            t.merchant_id,
            m.merchant_name,
            t.amount,
            t.txn_timestamp,
            t.is_fraud
        FROM transaction t
        JOIN account a ON a.account_id = t.account_id
        JOIN customer c ON c.customer_id = a.customer_id
        JOIN merchant m ON m.merchant_id = t.merchant_id
        WHERE t.is_fraud = false
        LIMIT 5;
    """)
    normal_samples = cur.fetchall()
    cur.close()
    conn.close()

    combined = list(fraud_samples) + list(normal_samples)
    return [
        SampleTransactionOption(
            transaction_id=r["transaction_id"],
            trans_num=r["trans_num"],
            account_id=r["account_id"],
            customer_name=r["customer_name"],
            merchant_id=r["merchant_id"],
            merchant_name=r["merchant_name"],
            amount=float(r["amount"]),
            txn_timestamp=str(r["txn_timestamp"]),
            is_fraud=bool(r["is_fraud"])
        )
        for r in combined
    ]

