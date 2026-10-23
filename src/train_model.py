"""
Step 4 — Machine Learning Model Training & Graph Ablation Study
==============================================================
Trains and evaluates fraud detection models using an 85% Train / 15% Test
chronological split (preventing lookahead bias):

  - Model A (Baseline): Transaction-level features only
      amount, hour, day_of_week, is_weekend, month,
      customer_age, kyc_verified, mcc_category

  - Model B (Hybrid): Transaction features + Graph features
      All Model A features plus:
      degree_centrality, shared_merchant_count_24h,
      trans_velocity_24h, hops_to_flagged, prior_fraud_neighbors_count

Evaluation Metrics (on the 15% holdout test set):
  - Accuracy (requested by user)
  - Precision, Recall, F1-Score (fraud class)
  - ROC-AUC & PR-AUC (Precision-Recall Area Under Curve)
  - Confusion Matrix (TN, FP, FN, TP)
  - Graph Ablation Lift analysis

Artifacts Saved:
  - models/model_baseline.joblib
  - models/model_hybrid.joblib
  - models/fraud_model.joblib (best model for API deployment)
  - models/metrics.json
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    confusion_matrix,
)
from pymongo import MongoClient


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB  = os.getenv("MONGO_DB", "fraud_ring_db")
DEFAULT_PARQUET_PATH = "data/fraud_features.parquet"
MODELS_DIR = "models"

BASELINE_FEATURES = [
    "amount",
    "hour",
    "day_of_week",
    "is_weekend",
    "month",
    "customer_age",
    "kyc_verified",
    "mcc_category",
]

GRAPH_FEATURES = [
    "degree_centrality",
    "shared_merchant_count_24h",
    "trans_velocity_24h",
    "hops_to_flagged",
    "prior_fraud_neighbors_count",
]

HYBRID_FEATURES = BASELINE_FEATURES + GRAPH_FEATURES


# ---------------------------------------------------------------------------
# 1. Data Ingestion
# ---------------------------------------------------------------------------
def load_feature_data(parquet_path=DEFAULT_PARQUET_PATH):
    """
    Loads features from Parquet cache or falls back to MongoDB `fraud_features`.
    """
    if os.path.exists(parquet_path):
        print(f"Loading features from fast Parquet cache: {parquet_path}...")
        df = pd.read_parquet(parquet_path)
    else:
        print(f"Parquet not found at {parquet_path}. Streaming from MongoDB `fraud_features`...")
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        cursor = db["fraud_features"].find({}, {"_id": 0})
        df = pd.DataFrame(list(cursor))
        client.close()

    print(f"Loaded {len(df):,} total records. Sorting chronologically by txn_timestamp...")
    df["txn_timestamp"] = pd.to_datetime(df["txn_timestamp"])
    df = df.sort_values("txn_timestamp").reset_index(drop=True)

    # Ensure category dtype for XGBoost native categorical support
    df["mcc_category"] = df["mcc_category"].astype("category")
    return df


# ---------------------------------------------------------------------------
# 2. Evaluation Helper
# ---------------------------------------------------------------------------
def evaluate_model(name, model, X_test, y_test, threshold=0.5):
    """
    Evaluates model probabilities and predictions on test data.
    """
    probs = model.predict_proba(X_test)[:, 1]
    preds = (probs >= threshold).astype(int)

    acc = float(accuracy_score(y_test, preds))
    prec = float(precision_score(y_test, preds, zero_division=0))
    rec = float(recall_score(y_test, preds, zero_division=0))
    f1 = float(f1_score(y_test, preds, zero_division=0))
    roc_auc = float(roc_auc_score(y_test, probs))
    pr_auc = float(average_precision_score(y_test, probs))
    cm = confusion_matrix(y_test, preds)

    tn, fp, fn, tp = [int(v) for v in cm.ravel()]

    metrics = {
        "name": name,
        "threshold": threshold,
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1_score": f1,
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "confusion_matrix": {
            "true_negatives": tn,
            "false_positives": fp,
            "false_negatives": fn,
            "true_positives": tp,
        },
    }
    return metrics, probs


# ---------------------------------------------------------------------------
# 3. Main Training & Ablation Pipeline
# ---------------------------------------------------------------------------
def run_training_pipeline(split_ratio=0.85, n_estimators=120, max_depth=6, lr=0.1):
    t_start = time.time()
    os.makedirs(MODELS_DIR, exist_ok=True)

    print("=" * 80)
    print("Step 4 — Machine Learning Model Training & Graph Ablation Study")
    print("=" * 80)

    # 1. Load Data
    df = load_feature_data()
    n_total = len(df)
    n_train = int(n_total * split_ratio)
    n_test = n_total - n_train

    train_df = df.iloc[:n_train]
    test_df = df.iloc[n_train:]

    y_train = train_df["fraud_label"].values
    y_test = test_df["fraud_label"].values

    print("\n" + "-" * 80)
    print("Dataset Splitting Strategy (Chronological 85% Train / 15% Holdout Test):")
    print(f"  Total Transactions:     {n_total:,}")
    print(f"  Train Set (85.0%):      {n_train:,} rows ({train_df['txn_timestamp'].min()} -> {train_df['txn_timestamp'].max()})")
    print(f"    Train Fraud Cases:    {y_train.sum():,} ({y_train.mean()*100:.3f}%)")
    print(f"  Test Set (15.0%):       {n_test:,} rows ({test_df['txn_timestamp'].min()} -> {test_df['txn_timestamp'].max()})")
    print(f"    Test Fraud Cases:     {y_test.sum():,} ({y_test.mean()*100:.3f}%)")
    print("-" * 80)

    # -----------------------------------------------------------------------
    # Train Model A (Baseline: Transaction Features Only)
    # -----------------------------------------------------------------------
    print("\n[1/2] Training Model A (Baseline: Transaction Features Only)...")
    X_train_a = train_df[BASELINE_FEATURES]
    X_test_a = test_df[BASELINE_FEATURES]

    model_a = xgb.XGBClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=lr,
        tree_method="hist",
        enable_categorical=True,
        random_state=42,
        n_jobs=-1,
    )
    t0_a = time.time()
    model_a.fit(X_train_a, y_train)
    t_train_a = time.time() - t0_a
    print(f"      Model A trained in {t_train_a:.2f}s.")

    metrics_a, probs_a = evaluate_model("Model A (Baseline - Transaction Only)", model_a, X_test_a, y_test)

    # -----------------------------------------------------------------------
    # Train Model B (Hybrid: Transaction + Graph Features)
    # -----------------------------------------------------------------------
    print("\n[2/2] Training Model B (Hybrid: Transaction + Graph Features)...")
    X_train_b = train_df[HYBRID_FEATURES]
    X_test_b = test_df[HYBRID_FEATURES]

    model_b = xgb.XGBClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=lr,
        tree_method="hist",
        enable_categorical=True,
        random_state=42,
        n_jobs=-1,
    )
    t0_b = time.time()
    model_b.fit(X_train_b, y_train)
    t_train_b = time.time() - t0_b
    print(f"      Model B trained in {t_train_b:.2f}s.")

    metrics_b, probs_b = evaluate_model("Model B (Hybrid - Transaction + Graph)", model_b, X_test_b, y_test)

    # -----------------------------------------------------------------------
    # Feature Importances Analysis
    # -----------------------------------------------------------------------
    importances = pd.Series(model_b.feature_importances_, index=HYBRID_FEATURES).sort_values(ascending=False)
    graph_importance_sum = float(importances[GRAPH_FEATURES].sum())
    txn_importance_sum = float(importances[BASELINE_FEATURES].sum())

    # -----------------------------------------------------------------------
    # Ablation Lift Comparison
    # -----------------------------------------------------------------------
    lift_summary = {
        "accuracy_delta": float(metrics_b["accuracy"] - metrics_a["accuracy"]),
        "precision_delta": float(metrics_b["precision"] - metrics_a["precision"]),
        "recall_delta": float(metrics_b["recall"] - metrics_a["recall"]),
        "f1_delta": float(metrics_b["f1_score"] - metrics_a["f1_score"]),
        "roc_auc_delta": float(metrics_b["roc_auc"] - metrics_a["roc_auc"]),
        "pr_auc_delta": float(metrics_b["pr_auc"] - metrics_a["pr_auc"]),
        "false_positive_reduction": int(
            metrics_a["confusion_matrix"]["false_positives"] - metrics_b["confusion_matrix"]["false_positives"]
        ),
        "false_positive_pct_reduction": float(
            (metrics_a["confusion_matrix"]["false_positives"] - metrics_b["confusion_matrix"]["false_positives"])
            / max(1, metrics_a["confusion_matrix"]["false_positives"])
            * 100
        ),
    }

    # -----------------------------------------------------------------------
    # Save Artifacts
    # -----------------------------------------------------------------------
    print("\nSaving trained models and evaluation artifacts...")
    path_a = os.path.join(MODELS_DIR, "model_baseline.joblib")
    path_b = os.path.join(MODELS_DIR, "model_hybrid.joblib")
    path_prod = os.path.join(MODELS_DIR, "fraud_model.joblib")
    metrics_path = os.path.join(MODELS_DIR, "metrics.json")

    joblib.dump(model_a, path_a)
    joblib.dump(model_b, path_b)
    # Save Model B as the production model package with feature metadata
    prod_package = {
        "model": model_b,
        "features": HYBRID_FEATURES,
        "baseline_features": BASELINE_FEATURES,
        "graph_features": GRAPH_FEATURES,
        "mcc_categories": list(df["mcc_category"].cat.categories),
        "trained_at": datetime.now().isoformat(),
        "training_size": n_train,
        "test_size": n_test,
        "test_accuracy": metrics_b["accuracy"],
        "test_pr_auc": metrics_b["pr_auc"],
    }
    joblib.dump(prod_package, path_prod)

    full_results = {
        "dataset_split": {
            "total_transactions": n_total,
            "train_transactions_85pct": n_train,
            "test_transactions_15pct": n_test,
            "train_fraud_count": int(y_train.sum()),
            "test_fraud_count": int(y_test.sum()),
            "train_fraud_rate": float(y_train.mean()),
            "test_fraud_rate": float(y_test.mean()),
            "split_type": "chronological (no future leakage)",
        },
        "model_a_baseline": metrics_a,
        "model_b_hybrid": metrics_b,
        "graph_ablation_lift": lift_summary,
        "feature_importances": {k: float(v) for k, v in importances.items()},
        "feature_importance_groups": {
            "graph_features_total_importance": graph_importance_sum,
            "transaction_features_total_importance": txn_importance_sum,
        },
    }

    with open(metrics_path, "w") as f:
        json.dump(full_results, f, indent=2)

    # -----------------------------------------------------------------------
    # Print Executive Summary Table
    # -----------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("STEP 4 — MODEL ABLATION RESULTS (Evaluated on 15% Holdout Test Set)")
    print("=" * 80)
    print(f"{'Metric':<22} {'Model A (Txn Only)':<22} {'Model B (Hybrid)':<22} {'Delta / Lift':<18}")
    print("-" * 80)
    print(f"{'Overall Accuracy':<22} {metrics_a['accuracy']*100:>20.3f}% {metrics_b['accuracy']*100:>20.3f}% {lift_summary['accuracy_delta']*100:>+16.3f}%")
    print(f"{'Precision (Fraud)':<22} {metrics_a['precision']*100:>20.2f}% {metrics_b['precision']*100:>20.2f}% {lift_summary['precision_delta']*100:>+16.2f}%")
    print(f"{'Recall (Fraud)':<22} {metrics_a['recall']*100:>20.2f}% {metrics_b['recall']*100:>20.2f}% {lift_summary['recall_delta']*100:>+16.2f}%")
    print(f"{'F1-Score':<22} {metrics_a['f1_score']:>21.4f} {metrics_b['f1_score']:>21.4f} {lift_summary['f1_delta']:>+17.4f}")
    print(f"{'PR-AUC (Avg Precision)':<22} {metrics_a['pr_auc']:>21.4f} {metrics_b['pr_auc']:>21.4f} {lift_summary['pr_auc_delta']:>+17.4f}")
    print(f"{'ROC-AUC':<22} {metrics_a['roc_auc']:>21.4f} {metrics_b['roc_auc']:>21.4f} {lift_summary['roc_auc_delta']:>+17.4f}")
    print("-" * 80)
    print(f"{'False Positives':<22} {metrics_a['confusion_matrix']['false_positives']:>21,} {metrics_b['confusion_matrix']['false_positives']:>21,} {lift_summary['false_positive_reduction']:>+17,} (reduced by {lift_summary['false_positive_pct_reduction']:.1f}%)")
    print(f"{'True Positives':<22} {metrics_a['confusion_matrix']['true_positives']:>21,} {metrics_b['confusion_matrix']['true_positives']:>21,}")
    print(f"{'False Negatives':<22} {metrics_a['confusion_matrix']['false_negatives']:>21,} {metrics_b['confusion_matrix']['false_negatives']:>21,}")
    print("=" * 80)

    print("\nFeature Importances (Top 5 in Hybrid Model):")
    for feat, val in importances.head(5).items():
        tag = "[GRAPH]" if feat in GRAPH_FEATURES else "[TXN]  "
        print(f"  {tag} {feat:<30} {val*100:>6.2f}%")
    print(f"  --> Graph Features Total Contribution: {graph_importance_sum*100:.2f}% of predictive power")

    print(f"\nArtifacts successfully written to `{MODELS_DIR}/`:")
    print(f"  - Baseline Model: {path_a}")
    print(f"  - Hybrid Model:   {path_b}")
    print(f"  - Production Pkg: {path_prod}")
    print(f"  - Metrics JSON:   {metrics_path}")
    print(f"Total Pipeline Runtime: {time.time() - t_start:.2f}s")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train ML models and perform graph ablation.")
    parser.add_argument("--split", type=float, default=0.85, help="Train split ratio (default: 0.85)")
    parser.add_argument("--n-estimators", type=int, default=120, help="Number of trees")
    parser.add_argument("--max-depth", type=int, default=6, help="Max tree depth")
    parser.add_argument("--lr", type=float, default=0.1, help="Learning rate")
    args = parser.parse_args()

    run_training_pipeline(
        split_ratio=args.split,
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        lr=args.lr,
    )
