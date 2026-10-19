#!/usr/bin/env python3
"""
Intelligent Fraud Ring Detection — System State Explorer
========================================================
Inspects and verifies the full pipeline across:
  - Step 0: PostgreSQL relational database (tables, counts, fraud stats)
  - Step 1: MongoDB Elliptic Bitcoin network graph
  - Step 2: MongoDB account_graph & merchant_links (shared-merchant edges)
  - Step 3: MongoDB fraud_features & Parquet cache
"""

import os
import psycopg
from pymongo import MongoClient

# Database connection config
DB_NAME   = os.getenv("PGDATABASE", "fraud_db")
DB_USER   = os.getenv("PGUSER", os.getenv("USER", "arnavbansal"))
DB_HOST   = os.getenv("PGHOST", "localhost")
DB_PORT   = os.getenv("PGPORT", "5432")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB  = os.getenv("MONGO_DB", "fraud_ring_db")


def print_header(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def main():
    pg_conn_str = f"dbname={DB_NAME} user={DB_USER} host={DB_HOST} port={DB_PORT}"

    # -----------------------------------------------------------------------
    # Step 0: PostgreSQL Relational Database
    # -----------------------------------------------------------------------
    print_header("1. POSTGRESQL [fraud_db] — RELATIONAL TABLES (Step 0)")
    with psycopg.connect(pg_conn_str) as conn:
        with conn.cursor() as cur:
            tables = [
                "customer", "account", "card", "merchant",
                "device", "ip_address", "transaction", "alert", "analyst"
            ]
            print(f"{'TABLE NAME':<25} {'ROW COUNT':>15}  STATUS / NOTES")
            print("-" * 75)
            for tbl in tables:
                cur.execute(f"SELECT COUNT(*) FROM {tbl};")
                cnt = cur.fetchone()[0]
                if tbl in ["device", "ip_address"]:
                    note = "Intentionally empty (no fake data)"
                elif tbl in ["alert", "analyst"]:
                    note = "Populated during API/Alerting (Step 7)"
                elif tbl == "transaction":
                    cur.execute("SELECT COUNT(*) FROM transaction WHERE fraud_label = TRUE;")
                    fraud_cnt = cur.fetchone()[0]
                    note = f"Includes {fraud_cnt:,} fraudulent txns ({fraud_cnt/cnt*100:.2f}%)"
                else:
                    note = "Loaded & verified"
                print(f"{tbl:<25} {cnt:>15,}  {note}")

    # -----------------------------------------------------------------------
    # Step 1 & 2: MongoDB Graph Layer
    # -----------------------------------------------------------------------
    print_header("2. MONGODB [fraud_ring_db] — GRAPH & RELATIONSHIP LAYER (Steps 1 & 2)")
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client[MONGO_DB]
    collections = db.list_collection_names()

    print(f"{'COLLECTION':<25} {'DOCUMENT COUNT':>15}  DESCRIPTION")
    print("-" * 75)
    descriptions = {
        "elliptic_nodes": "Step 1: Bitcoin transaction nodes (illicit/licit)",
        "elliptic_edges": "Step 1: Bitcoin transaction directed edges",
        "merchant_links": "Step 2: Account <-> Merchant interaction edges",
        "account_graph":  "Step 2: Shared-merchant 24h adjacency & degrees",
        "fraud_features": "Step 3: Combined transaction + graph feature store"
    }
    for coll_name in sorted(descriptions.keys()):
        cnt = db[coll_name].count_documents({}) if coll_name in collections else 0
        desc = descriptions.get(coll_name, "")
        print(f"{coll_name:<25} {cnt:>15,}  {desc}")

    # Inspect account_graph metrics
    if "account_graph" in collections:
        sample_acc = db["account_graph"].find_one()
        degrees = [doc.get("degree", 0) for doc in db["account_graph"].find({}, {"degree": 1})]
        if degrees:
            avg_deg = sum(degrees) / len(degrees)
            max_deg = max(degrees)
            min_deg = min(degrees)
            print(f"\n  [Account Graph Summary]:")
            print(f"    - Total Account Nodes:   {len(degrees):,}")
            print(f"    - Average Degree:        {avg_deg:.2f} / 998")
            print(f"    - Min / Max Degree:      {min_deg} / {max_deg}")
            print(f"    - Sample Account ID:     {sample_acc.get('_id')}")
            print(f"    - Sample Linked Accounts:{len(sample_acc.get('linked_accounts', []))}")

    # -----------------------------------------------------------------------
    # Step 3: Extracted Features (MongoDB + Parquet)
    # -----------------------------------------------------------------------
    print_header("3. EXTRACTED FEATURES & ML READINESS (Step 3)")
    pq_path = "data/fraud_features.parquet"
    if os.path.exists(pq_path):
        pq_size_mb = os.path.getsize(pq_path) / (1024 * 1024)
        print(f"  Parquet Cache:  {pq_path} ({pq_size_mb:.1f} MB)")
    else:
        print(f"  Parquet Cache:  Not found")

    if "fraud_features" in collections:
        feat_cnt = db["fraud_features"].count_documents({})
        fraud_cnt = db["fraud_features"].count_documents({"fraud_label": 1})
        print(f"  MongoDB Store:  {feat_cnt:,} records in `fraud_features`")
        print(f"  Class Balance:  {fraud_cnt:,} fraud ({fraud_cnt/feat_cnt*100:.2f}%) / {feat_cnt - fraud_cnt:,} clean")

        print("\n  SAMPLE FEATURE VECTOR (from MongoDB):")
        sample_feat = db["fraud_features"].find_one({"fraud_label": 1}) or db["fraud_features"].find_one()
        if sample_feat:
            print(f"    Transaction ID:               {sample_feat.get('transaction_id')}")
            print(f"    Account ID / Merchant ID:     {sample_feat.get('account_id')} / {sample_feat.get('merchant_id')}")
            print(f"    Amount / MCC Category:        ${sample_feat.get('amount'):.2f} / {sample_feat.get('mcc_category')}")
            print(f"    Timestamp:                    {sample_feat.get('txn_timestamp')}")
            print(f"    Customer Age / KYC:           {sample_feat.get('customer_age')} yrs / {bool(sample_feat.get('kyc_verified'))}")
            print(f"    -- Graph Features --")
            print(f"    Degree Centrality:            {sample_feat.get('degree_centrality'):.4f}")
            print(f"    Shared Merchants (24h):       {sample_feat.get('shared_merchant_count_24h')}")
            print(f"    Account Burst Velocity (24h): {sample_feat.get('trans_velocity_24h')}")
            print(f"    Hops to Prior Fraud:          {sample_feat.get('hops_to_flagged')}")
            print(f"    Prior Fraud Neighbors (1-hop):{sample_feat.get('prior_fraud_neighbors_count')}")
            print(f"    Ground Truth Fraud Label:     {sample_feat.get('fraud_label')}")

    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
