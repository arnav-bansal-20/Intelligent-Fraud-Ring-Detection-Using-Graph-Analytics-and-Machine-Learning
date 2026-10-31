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
from backend.database import get_db, get_mongo_db, get_known_fraud_accounts
from backend.features import compute_transaction_features
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
    conn = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Score a transaction using the trained XGBoost model and dynamic MongoDB graph features.
    Computes graph features, predicts fraud probability, assigns risk label based on calibrated threshold,
    and returns feature contribution reasons for decision support.
    """
    bundle = get_model()
    model = bundle["model"]
    feature_cols = bundle["feature_cols"]

    # Decision thresholds: calibrated threshold for High, 0.5 * threshold for Medium
    high_threshold = float(bundle.get("threshold", 0.9735))
    medium_threshold = round(high_threshold * 0.5, 4)

    # 1. Parse timestamp
    if req.txn_timestamp:
        try:
            dt = datetime.fromisoformat(req.txn_timestamp.replace("Z", "+00:00"))
        except Exception:
            dt = datetime.now(timezone.utc)
    else:
        dt = datetime.now(timezone.utc)

    # 2. Extract Graph & Transaction Features using shared module
    mongo = get_mongo_db()
    cur = conn.cursor()

    # Cached confirmed fraud accounts (built strictly from is_fraud = true)
    fraud_accounts = get_known_fraud_accounts(cur)

    feature_dict = compute_transaction_features(
        account_id=req.account_id,
        merchant_id=req.merchant_id,
        amount=req.amount,
        dt=dt,
        cur=cur,
        mongo=mongo,
        fraud_accounts=fraud_accounts
    )

    feature_vector = np.array([[feature_dict[col] for col in feature_cols]])

    # 3. Model Inference
    pred_prob = float(model.predict_proba(feature_vector)[0, 1])
    fraud_probability = round(pred_prob, 4)

    # Calibrated Risk Label Assignment
    if fraud_probability >= high_threshold:
        risk_label = "High"
        predicted_fraud = True
    elif fraud_probability >= medium_threshold:
        risk_label = "Medium"
        predicted_fraud = False
    else:
        risk_label = "Low"
        predicted_fraud = False

    hops_to_flagged = feature_dict["hops_to_flagged"]
    prior_fraud_neighbors_count = feature_dict["prior_fraud_neighbors_count"]
    trans_velocity_24h = feature_dict["trans_velocity_24h"]

    # 4. Compute Top Reasons (Explainability for Analyst Decision Support)
    top_reasons: List[FeatureReason] = []

    # Reason 1: Network Proximity to Fraud
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
            description=f"Account is {int(hops_to_flagged)} hops removed from nearest flagged syndicate accounts.",
            value=float(hops_to_flagged),
            contribution_level="Moderate" if hops_to_flagged <= 2 else "Baseline"
        ))

    # Reason 2: Fraud Network Concentration
    if prior_fraud_neighbors_count > 0:
        top_reasons.append(FeatureReason(
            feature="prior_fraud_neighbors_count",
            description=f"Direct merchant network overlap with {int(prior_fraud_neighbors_count)} confirmed fraud accounts.",
            value=float(prior_fraud_neighbors_count),
            contribution_level="High"
        ))

    # Reason 3: Transaction Amount
    if req.amount > 500.0:
        top_reasons.append(FeatureReason(
            feature="amount",
            description=f"Elevated transaction value (${req.amount:.2f}) vs normal expected baseline.",
            value=float(req.amount),
            contribution_level="High" if req.amount > 1000.0 else "Moderate"
        ))

    # Reason 4: 24h Velocity Spike
    if trans_velocity_24h >= 3:
        top_reasons.append(FeatureReason(
            feature="trans_velocity_24h",
            description=f"High transaction frequency burst: {int(trans_velocity_24h)} transactions in past 24 hours.",
            value=float(trans_velocity_24h),
            contribution_level="High"
        ))

    # Fallback Baseline
    if not top_reasons:
        top_reasons.append(FeatureReason(
            feature="baseline",
            description="Transaction characteristics align with standard commercial banking activity.",
            value=float(fraud_probability),
            contribution_level="Baseline"
        ))

    # 5. Save Alert if requested and risk is High
    alert_created = False
    alert_id = None
    iso_time_str = dt.strftime("%Y-%m-%d %H:%M:%S")

    if req.save_alert and risk_label == "High":
        # Create transaction row with source='company', predicted_fraud, fraud_probability, is_fraud=False
        cur.execute("""
            INSERT INTO transaction (account_id, merchant_id, trans_num, amount, txn_timestamp, source, predicted_fraud, fraud_probability, is_fraud)
            VALUES (%s, %s, %s, %s, %s, 'company', %s, %s, false)
            ON CONFLICT (trans_num) DO UPDATE SET amount = EXCLUDED.amount
            RETURNING transaction_id;
        """, (
            req.account_id, req.merchant_id,
            f"sim_{int(datetime.now().timestamp() * 1000)}",
            req.amount, iso_time_str, predicted_fraud, fraud_probability
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
def get_sample_transactions(
    conn = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Returns a curated set of sample transactions from PostgreSQL
    for quick selection and decision-support testing by the analyst.
    """
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
