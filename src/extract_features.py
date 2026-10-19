"""
Step 3 — Feature Extraction (PostgreSQL + MongoDB → fraud_features)
===================================================================
Extracts transaction-level baseline features and network graph features
for every transaction in the database:

  Baseline Transaction Features:
    - amount, hour, day_of_week, is_weekend, month
    - category (merchant mcc_category)
    - customer_age (age in years at transaction time)
    - kyc_verified

  Graph & Network Features (derived from MongoDB relationship layer):
    - degree_centrality: normalized degree from account_graph
    - shared_merchant_count_24h: distinct other accounts sharing this merchant in prior 24h
    - hops_to_flagged: temporal BFS shortest path to nearest prior-fraud account (0..4)
    - prior_fraud_neighbors_count: number of 1-hop neighbors with prior fraud
    - trans_velocity_24h: account transaction burst count in prior 24h

Zero Data Leakage:
  All temporal graph reachability and sliding windows use strictly prior timestamps
  (t_event < t_current). Future transactions and future fraud are never observed.

Destination:
  - MongoDB collection: `fraud_features`
  - Parquet cache: `data/fraud_features.parquet` (for ultra-fast ML training in Step 4)
"""

import os
import sys
import time
import bisect
import argparse
import datetime
from collections import defaultdict

import numpy as np
import pandas as pd
import psycopg
from pymongo import MongoClient, ASCENDING, IndexModel


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DB_NAME   = os.getenv("PGDATABASE", "fraud_db")
DB_USER   = os.getenv("PGUSER", os.getenv("USER", "arnavbansal"))
DB_HOST   = os.getenv("PGHOST", "localhost")
DB_PORT   = os.getenv("PGPORT", "5432")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB  = os.getenv("MONGO_DB", "fraud_ring_db")


def get_pg_conn_str():
    return f"dbname={DB_NAME} user={DB_USER} host={DB_HOST} port={DB_PORT}"


# ---------------------------------------------------------------------------
# 1. Temporal Reachability Graph Precomputation
# ---------------------------------------------------------------------------
def compute_temporal_reachability(pg_conn, mongo_db):
    """
    Computes earliest reachability timestamps (tau_0, tau_1, tau_2, tau_3)
    from each account to any flagged fraud account.

    Zero leakage: a path (u -> v -> ... -> f) is only valid at time t
    if all edges on the path formed <= t and the target node f committed fraud < t.
    """
    print("  [1/4] Querying first fraud timestamps from PostgreSQL...")
    with pg_conn.cursor() as cur:
        cur.execute("""
            SELECT account_id, MIN(txn_timestamp)
            FROM transaction
            WHERE fraud_label = TRUE
            GROUP BY account_id;
        """)
        first_fraud = dict(cur.fetchall())
    print(f"        Found {len(first_fraud)} distinct accounts with historical fraud.")

    print("  [2/4] Loading account graph adjacency from MongoDB...")
    account_docs = list(mongo_db["account_graph"].find({}, {"_id": 1, "degree": 1, "linked_accounts": 1}))
    total_accounts = len(account_docs)
    print(f"        Loaded {total_accounts} account nodes from account_graph.")

    INF_DATE = datetime.datetime(2099, 1, 1)

    # Normalized degree centrality
    norm_denom = max(1, total_accounts - 1)
    centrality_map = {doc["_id"]: float(doc.get("degree", 0)) / norm_denom for doc in account_docs}

    # tau_0: when account itself committed fraud
    tau_0 = {doc["_id"]: first_fraud.get(doc["_id"], INF_DATE) for doc in account_docs}

    # tau_1: 1-hop reachability to a neighbor that had fraud
    tau_1 = {}
    tau_1_lists = {}
    for doc in account_docs:
        u = doc["_id"]
        taus = []
        for edge in doc.get("linked_accounts", []):
            v = edge["account_id"]
            overlap_t = edge.get("first_overlap", INF_DATE)
            fraud_t = tau_0.get(v, INF_DATE)
            t_reach = max(overlap_t, fraud_t)
            if t_reach < INF_DATE:
                taus.append(t_reach)
        taus.sort()
        tau_1_lists[u] = taus
        tau_1[u] = taus[0] if taus else INF_DATE

    # tau_2: 2-hop reachability
    tau_2 = {}
    for doc in account_docs:
        u = doc["_id"]
        best = INF_DATE
        for edge in doc.get("linked_accounts", []):
            v = edge["account_id"]
            overlap_t = edge.get("first_overlap", INF_DATE)
            v_t = tau_1.get(v, INF_DATE)
            t_reach = max(overlap_t, v_t)
            if t_reach < best:
                best = t_reach
        tau_2[u] = best

    # tau_3: 3-hop reachability
    tau_3 = {}
    for doc in account_docs:
        u = doc["_id"]
        best = INF_DATE
        for edge in doc.get("linked_accounts", []):
            v = edge["account_id"]
            overlap_t = edge.get("first_overlap", INF_DATE)
            v_t = tau_2.get(v, INF_DATE)
            t_reach = max(overlap_t, v_t)
            if t_reach < best:
                best = t_reach
        tau_3[u] = best

    print("        Temporal reachability index built successfully.")
    return centrality_map, tau_0, tau_1, tau_1_lists, tau_2, tau_3


# ---------------------------------------------------------------------------
# 2. Main Feature Extraction Pipeline
# ---------------------------------------------------------------------------
def extract_all_features(limit=None, output_parquet="data/fraud_features.parquet",
                         batch_size=25000, skip_mongo=False, drop_coll=True):
    t_start = time.time()
    print("=" * 70)
    print("Step 3 — Extracting Fraud & Graph Features")
    print("=" * 70)

    # Connect to PostgreSQL and MongoDB
    pg_conn = psycopg.connect(get_pg_conn_str())
    mongo_client = MongoClient(MONGO_URI)
    mongo_db = mongo_client[MONGO_DB]
    features_coll = mongo_db["fraud_features"]

    if drop_coll and not skip_mongo:
        print("Dropping existing `fraud_features` collection...")
        features_coll.drop()

    # Step 1: Precompute Temporal Reachability
    centrality_map, tau_0, tau_1, tau_1_lists, tau_2, tau_3 = compute_temporal_reachability(pg_conn, mongo_db)

    # Step 2: Fetch transactions joined with merchant and customer attributes
    print("\n  [3/4] Streaming all transactions from PostgreSQL...")
    limit_clause = f"LIMIT {int(limit)}" if limit else ""
    query = f"""
        SELECT t.transaction_id,
               t.account_id,
               t.merchant_id,
               t.amount,
               t.txn_timestamp,
               t.fraud_label,
               m.mcc_category,
               c.date_of_birth,
               c.kyc_verified
        FROM transaction t
        JOIN merchant m ON t.merchant_id = m.merchant_id
        JOIN account a ON t.account_id = a.account_id
        JOIN customer c ON a.customer_id = c.customer_id
        ORDER BY t.txn_timestamp ASC
        {limit_clause};
    """

    t_fetch_start = time.time()
    with pg_conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
    t_fetch = time.time() - t_fetch_start
    total_txns = len(rows)
    print(f"        Loaded {total_txns:,} transactions in {t_fetch:.2f}s.")

    df = pd.DataFrame(rows, columns=colnames)
    del rows  # Free raw tuple memory

    # Ensure correct data types
    df["amount"] = df["amount"].astype(float)
    df["fraud_label"] = df["fraud_label"].astype(int)
    df["kyc_verified"] = df["kyc_verified"].fillna(False).astype(int)
    timestamps = pd.to_datetime(df["txn_timestamp"])

    # Compute baseline transaction-level features
    print("\n  [4/4] Computing baseline & graph features...")
    df["hour"] = timestamps.dt.hour.astype(np.int8)
    df["day_of_week"] = timestamps.dt.dayofweek.astype(np.int8)
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(np.int8)
    df["month"] = timestamps.dt.month.astype(np.int8)

    # Customer age at transaction time
    dob = pd.to_datetime(df["date_of_birth"])
    df["customer_age"] = ((timestamps - dob).dt.days / 365.25).fillna(40).clip(18, 100).astype(np.int8)

    # Map degree centrality
    account_ids = df["account_id"].values
    df["degree_centrality"] = [centrality_map.get(acc, 0.0) for acc in account_ids]

    # Pre-convert timestamps to UNIX timestamps (seconds) for ultra-fast sliding windows
    ts_seconds = (timestamps.astype("int64") // 10**9).values
    merchant_ids = df["merchant_id"].values
    WINDOW_24H_SEC = 24 * 3600

    # -----------------------------------------------------------------------
    # Sliding Window 1: shared_merchant_count_24h
    # Distinct other accounts transacting at this merchant in prior 24h [t - 24h, t)
    # -----------------------------------------------------------------------
    print("        Computing shared_merchant_count_24h (sliding window)...")
    merchant_indices = defaultdict(list)
    for idx, m in enumerate(merchant_ids):
        merchant_indices[m].append(idx)

    shared_counts = np.zeros(total_txns, dtype=np.int32)
    for m, indices in merchant_indices.items():
        left = 0
        acc_counts = defaultdict(int)
        for right in range(len(indices)):
            idx_r = indices[right]
            t_r = ts_seconds[idx_r]
            acc_r = account_ids[idx_r]

            # Slide left pointer
            while left < right and (t_r - ts_seconds[indices[left]]) > WINDOW_24H_SEC:
                acc_l = account_ids[indices[left]]
                acc_counts[acc_l] -= 1
                if acc_counts[acc_l] == 0:
                    del acc_counts[acc_l]
                left += 1

            # Count distinct other accounts
            other_distinct = len(acc_counts) - (1 if acc_r in acc_counts else 0)
            shared_counts[idx_r] = other_distinct
            acc_counts[acc_r] += 1

    df["shared_merchant_count_24h"] = shared_counts

    # -----------------------------------------------------------------------
    # Sliding Window 2: trans_velocity_24h
    # Number of prior transactions by this account in prior 24h [t - 24h, t)
    # -----------------------------------------------------------------------
    print("        Computing trans_velocity_24h (account burst window)...")
    account_indices = defaultdict(list)
    for idx, acc in enumerate(account_ids):
        account_indices[acc].append(idx)

    trans_velocity = np.zeros(total_txns, dtype=np.int32)
    for acc, indices in account_indices.items():
        left = 0
        for right in range(len(indices)):
            idx_r = indices[right]
            t_r = ts_seconds[idx_r]
            while left < right and (t_r - ts_seconds[indices[left]]) > WINDOW_24H_SEC:
                left += 1
            trans_velocity[idx_r] = right - left

    df["trans_velocity_24h"] = trans_velocity

    # -----------------------------------------------------------------------
    # Graph Feature 3 & 4: hops_to_flagged and prior_fraud_neighbors_count
    # -----------------------------------------------------------------------
    print("        Computing hops_to_flagged & prior_fraud_neighbors_count...")
    ts_datetimes = df["txn_timestamp"].tolist()
    hops_array = np.full(total_txns, 4, dtype=np.int8)
    fraud_neighbors = np.zeros(total_txns, dtype=np.int32)

    for i in range(total_txns):
        acc = account_ids[i]
        t = ts_datetimes[i]

        # 0 hops: account had prior fraud before this transaction
        if t > tau_0.get(acc, datetime.datetime.max):
            hops_array[i] = 0
        elif t > tau_1.get(acc, datetime.datetime.max):
            hops_array[i] = 1
        elif t > tau_2.get(acc, datetime.datetime.max):
            hops_array[i] = 2
        elif t > tau_3.get(acc, datetime.datetime.max):
            hops_array[i] = 3
        else:
            hops_array[i] = 4

        # Number of 1-hop neighbors who had fraud prior to t
        taus = tau_1_lists.get(acc, [])
        if taus:
            fraud_neighbors[i] = bisect.bisect_right(taus, t)

    df["hops_to_flagged"] = hops_array
    df["prior_fraud_neighbors_count"] = fraud_neighbors

    # Save to Parquet cache
    if output_parquet:
        os.makedirs(os.path.dirname(output_parquet), exist_ok=True)
        print(f"\nSaving features to Parquet: {output_parquet}...")
        df.to_parquet(output_parquet, index=False, engine="pyarrow", compression="snappy")
        file_size_mb = os.path.getsize(output_parquet) / (1024 * 1024)
        print(f"Parquet saved successfully ({file_size_mb:.1f} MB).")

    # Insert into MongoDB collection: fraud_features
    if not skip_mongo:
        print(f"\nInserting {total_txns:,} documents into MongoDB `fraud_features`...")
        t_mongo_start = time.time()

        # Convert to dictionary records for MongoDB insertion
        cols_for_mongo = [
            "transaction_id", "account_id", "merchant_id", "amount", "txn_timestamp",
            "fraud_label", "mcc_category", "hour", "day_of_week", "is_weekend",
            "month", "customer_age", "kyc_verified", "degree_centrality",
            "shared_merchant_count_24h", "trans_velocity_24h", "hops_to_flagged",
            "prior_fraud_neighbors_count"
        ]
        mongo_df = df[cols_for_mongo].copy()

        # Insert in chunks of batch_size
        num_batches = (total_txns + batch_size - 1) // batch_size
        for b_idx in range(num_batches):
            chunk = mongo_df.iloc[b_idx * batch_size : (b_idx + 1) * batch_size]
            docs = chunk.to_dict(orient="records")
            features_coll.insert_many(docs, ordered=False)
            if (b_idx + 1) % 10 == 0 or (b_idx + 1) == num_batches:
                pct = ((b_idx + 1) / num_batches) * 100
                print(f"        Inserted batch {b_idx + 1}/{num_batches} ({pct:.0f}%)...")

        t_mongo = time.time() - t_mongo_start
        print(f"MongoDB write completed in {t_mongo:.2f}s ({(total_txns/t_mongo):.0f} docs/sec).")

        # Create indexes
        print("Creating MongoDB indexes on `fraud_features`...")
        features_coll.create_indexes([
            IndexModel([("transaction_id", ASCENDING)], unique=True),
            IndexModel([("account_id", ASCENDING)]),
            IndexModel([("txn_timestamp", ASCENDING)]),
            IndexModel([("fraud_label", ASCENDING)])
        ])
        print("Indexes created.")

    # Print summary statistics
    t_total = time.time() - t_start
    print("\n" + "=" * 70)
    print("STEP 3 FEATURE EXTRACTION COMPLETE")
    print("=" * 70)
    print(f"Total Transactions Processed: {total_txns:,}")
    print(f"Fraud Transactions:           {(df['fraud_label'] == 1).sum():,} ({df['fraud_label'].mean() * 100:.2f}%)")
    print(f"Legitimate Transactions:      {(df['fraud_label'] == 0).sum():,} ({(1 - df['fraud_label'].mean()) * 100:.2f}%)")
    print(f"Hops Distribution:            {dict(df['hops_to_flagged'].value_counts().sort_index())}")
    print(f"Avg Shared Merchants (24h):   {df['shared_merchant_count_24h'].mean():.2f} (max: {df['shared_merchant_count_24h'].max()})")
    print(f"Avg Degree Centrality:        {df['degree_centrality'].mean():.4f}")
    print(f"Total Pipeline Runtime:       {t_total:.2f}s")
    print("=" * 70)

    pg_conn.close()
    mongo_client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract features for fraud ring detection.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of transactions (for testing)")
    parser.add_argument("--batch-size", type=int, default=25000, help="MongoDB batch insert size")
    parser.add_argument("--output-parquet", type=str, default="data/fraud_features.parquet", help="Parquet output path")
    parser.add_argument("--skip-mongo", action="store_true", help="Skip inserting into MongoDB")
    parser.add_argument("--no-drop", action="store_true", help="Do not drop existing fraud_features collection")
    args = parser.parse_args()

    extract_all_features(
        limit=args.limit,
        output_parquet=args.output_parquet,
        batch_size=args.batch_size,
        skip_mongo=args.skip_mongo,
        drop_coll=not args.no_drop
    )
