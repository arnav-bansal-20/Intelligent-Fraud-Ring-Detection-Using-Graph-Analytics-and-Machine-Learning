#!/usr/bin/env python3
"""
Step 4: Machine Learning Classifier (Random Forest)
Trained on transaction features + graph features.
- Strict time-based 70/15/15 split (Train / Validation / Test)
- Class-imbalance handling: class_weight='balanced'
- Comprehensive evaluation: Precision, Recall, F1, ROC-AUC, PR-AUC
- Evaluates:
  1) Baseline Model (Transaction features only: amt, hour, day_of_week)
  2) Graph-Augmented Model (Transaction + MongoDB Graph Features)
  demonstrating the decisive lift graph intelligence provides!
- Saves trained model to models/fraud_model.joblib
"""

import os
import sys
import argparse
import logging
from datetime import datetime
import numpy as np
import pandas as pd
from pymongo import MongoClient
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score,
    classification_report, confusion_matrix
)

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.db_config import MONGO_URI, MONGO_DB_NAME

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def load_dataset_from_mongo():
    logger.info("Loading extracted features from MongoDB 'fraud_features'...")
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    coll = db["fraud_features"]

    cursor = coll.find({}, {
        "trans_num": 1,
        "unix_time": 1,
        "amt": 1,
        "shared_device_count": 1,
        "shared_ip_count": 1,
        "account_degree": 1,
        "hops_to_nearest_flagged": 1,
        "flagged_neighbors_count": 1,
        "device_usage_count": 1,
        "ip_usage_count": 1,
        "is_fraud": 1
    }).sort("unix_time", 1)  # chronological order

    df = pd.DataFrame(list(cursor))
    logger.info(f"Loaded {len(df):,} transactions for ML modeling.")

    # Feature engineering: temporal features from unix_time
    df["dt"] = pd.to_datetime(df["unix_time"], unit="s")
    df["hour"] = df["dt"].dt.hour
    df["day_of_week"] = df["dt"].dt.dayofweek

    # Encode hops: -1 (unconnected) -> 99
    df["hops_clean"] = df["hops_to_nearest_flagged"].apply(lambda h: 99.0 if h == -1 else float(h))

    return df

def train_and_evaluate(df):
    feature_cols_baseline = ["amt", "hour", "day_of_week"]
    feature_cols_graph = [
        "amt", "hour", "day_of_week",
        "shared_device_count", "shared_ip_count",
        "account_degree", "hops_clean",
        "flagged_neighbors_count", "device_usage_count", "ip_usage_count"
    ]

    # Time-based 70 / 15 / 15 split
    n = len(df)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)

    train_df = df.iloc[:train_end]
    val_df = df.iloc[train_end:val_end]
    test_df = df.iloc[val_end:]

    logger.info(f"Dataset split: Train={len(train_df):,} | Val={len(val_df):,} | Test={len(test_df):,}")
    logger.info(f"Fraud rates: Train={train_df['is_fraud'].mean():.2%} | Val={val_df['is_fraud'].mean():.2%} | Test={test_df['is_fraud'].mean():.2%}")

    y_train = train_df["is_fraud"].values
    y_val = val_df["is_fraud"].values
    y_test = test_df["is_fraud"].values

    # -------------------------------------------------------------
    # 1. Baseline Model (No Graph Features)
    # -------------------------------------------------------------
    logger.info("Training Baseline Model (Transaction features only)...")
    clf_base = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )
    clf_base.fit(train_df[feature_cols_baseline], y_train)

    base_preds = clf_base.predict(test_df[feature_cols_baseline])
    base_probs = clf_base.predict_proba(test_df[feature_cols_baseline])[:, 1]

    # -------------------------------------------------------------
    # 2. Graph-Augmented Model (Transaction + Graph Features)
    # -------------------------------------------------------------
    logger.info("Training Graph-Augmented Model (Transaction + MongoDB Graph Features)...")
    clf_graph = RandomForestClassifier(
        n_estimators=100,
        max_depth=12,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )
    clf_graph.fit(train_df[feature_cols_graph], y_train)

    graph_preds = clf_graph.predict(test_df[feature_cols_graph])
    graph_probs = clf_graph.predict_proba(test_df[feature_cols_graph])[:, 1]

    # -------------------------------------------------------------
    # Model Comparison & Reporting
    # -------------------------------------------------------------
    def compute_metrics(y_true, y_pred, y_prob):
        return {
            "Precision": precision_score(y_true, y_pred, zero_division=0),
            "Recall": recall_score(y_true, y_pred, zero_division=0),
            "F1-Score": f1_score(y_true, y_pred, zero_division=0),
            "ROC-AUC": roc_auc_score(y_true, y_prob),
            "PR-AUC": average_precision_score(y_true, y_prob)
        }

    m_base = compute_metrics(y_test, base_preds, base_probs)
    m_graph = compute_metrics(y_test, graph_preds, graph_probs)

    print("\n" + "="*70)
    print("MODEL EVALUATION COMPARISON ON HELD-OUT TEST SET (15% Temporal Split)")
    print("="*70)
    print(f"{'Metric':<18} | {'Baseline (No Graph)':<22} | {'Graph-Augmented (Ours)':<22}")
    print("-"*70)
    for k in ["Precision", "Recall", "F1-Score", "ROC-AUC", "PR-AUC"]:
        print(f"{k:<18} | {m_base[k]:<22.4f} | {m_graph[k]:<22.4f}")
    print("="*70)

    print("\nConfusion Matrix (Graph Model):")
    cm = confusion_matrix(y_test, graph_preds)
    print(f"  TN: {cm[0,0]:<6} FP: {cm[0,1]:<6}")
    print(f"  FN: {cm[1,0]:<6} TP: {cm[1,1]:<6}")

    print("\nFeature Importances (Graph Model):")
    importances = clf_graph.feature_importances_
    for col, imp in sorted(zip(feature_cols_graph, importances), key=lambda x: x[1], reverse=True):
        bar = "█" * int(imp * 40)
        print(f"  {col.ljust(25)}: {imp:.4f} {bar}")
    print("="*70 + "\n")

    # Save model and feature schema
    os.makedirs("models", exist_ok=True)
    model_path = os.path.join("models", "fraud_model.joblib")
    bundle = {
        "model": clf_graph,
        "feature_cols": feature_cols_graph,
        "metrics": m_graph,
        "trained_at": datetime.now().isoformat()
    }
    joblib.dump(bundle, model_path)
    logger.info(f"Saved trained Graph-Augmented Model to {model_path}")

    # Also update risk_score in MongoDB fraud_features collection
    logger.info("Materializing risk_score predictions into MongoDB fraud_features...")
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    coll = db["fraud_features"]

    all_features = df[feature_cols_graph]
    all_scores = clf_graph.predict_proba(all_features)[:, 1]

    from pymongo import UpdateOne
    updates = []
    for trans_num, score in zip(df["trans_num"], all_scores):
        updates.append(UpdateOne(
            {"trans_num": trans_num},
            {"$set": {"risk_score": float(round(score, 4)), "model_version": "v1.0-graph-rf"}}
        ))
        if len(updates) >= 5000:
            coll.bulk_write(updates, ordered=False)
            updates = []
    if updates:
        coll.bulk_write(updates, ordered=False)

    logger.info("Updated risk_scores in MongoDB successfully.")

if __name__ == "__main__":
    df = load_dataset_from_mongo()
    train_and_evaluate(df)

