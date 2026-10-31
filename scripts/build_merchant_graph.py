#!/usr/bin/env python3
"""
Same-Merchant-Within-24h Graph Builder
Constructs the co-merchant banking relationship graph from PostgreSQL transactions
and materializes it into the MongoDB 'account_graph' collection.

Node schema:
  - account_id: int
  - degree: int (number of connected accounts sharing merchants in 24h)
  - is_flagged: bool (analyst-confirmed fraud or dataset ground-truth label)
  - neighbors: list of { "account_id": int, "shared_merchant_count": int }
"""

import os
import sys
import time
import logging
from datetime import datetime, timezone
from collections import defaultdict, deque
from pymongo import MongoClient, ASCENDING

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database import get_pg_connection, get_mongo_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def build_same_merchant_graph():
    logger.info("Extracting transactions from PostgreSQL for same-merchant graph construction...")
    t0 = time.time()
    conn = get_pg_connection()
    cur = conn.cursor()

    # Query all transactions
    cur.execute("""
        SELECT account_id, merchant_id, EXTRACT(EPOCH FROM txn_timestamp)::bigint as ts, is_fraud
        FROM transaction
        ORDER BY merchant_id, txn_timestamp;
    """)
    rows = cur.fetchall()
    logger.info(f"Loaded {len(rows):,} transactions in {time.time() - t0:.2f}s.")

    # Distinct accounts and confirmed fraud accounts
    all_accounts = set()
    cur.execute("SELECT account_id FROM account;")
    for r in cur.fetchall():
        all_accounts.add(r["account_id"])

    cur.execute("SELECT DISTINCT account_id FROM transaction WHERE is_fraud = true;")
    fraud_accounts = set(r["account_id"] for r in cur.fetchall())
    logger.info(f"Total accounts in PostgreSQL: {len(all_accounts)}, Confirmed Fraud Accounts: {len(fraud_accounts)}")

    cur.close()
    conn.close()

    # Group transactions by merchant
    t1 = time.time()
    merch_txs = defaultdict(list)
    for r in rows:
        aid = r["account_id"]
        all_accounts.add(aid)
        merch_txs[r["merchant_id"]].append((r["ts"], aid))

    # Compute 24-hour same-merchant co-occurrence
    logger.info(f"Computing 24-hour temporal co-occurrence across {len(merch_txs)} merchants...")
    # account_neighbors[a][b] = count of distinct merchant co-occurrences
    account_neighbors = defaultdict(lambda: defaultdict(int))

    for mid, tx_list in merch_txs.items():
        q = deque()
        seen_in_window = defaultdict(int)
        distinct_window_accounts = set()

        for ts, aid in tx_list:
            t_cutoff = ts - 86400  # 24 hours in seconds
            while q and q[0][0] < t_cutoff:
                old_ts, old_aid = q.popleft()
                seen_in_window[old_aid] -= 1
                if seen_in_window[old_aid] == 0:
                    distinct_window_accounts.discard(old_aid)

            for other_aid in distinct_window_accounts:
                if other_aid != aid:
                    account_neighbors[aid][other_aid] += 1
                    account_neighbors[other_aid][aid] += 1

            q.append((ts, aid))
            seen_in_window[aid] += 1
            distinct_window_accounts.add(aid)

    logger.info(f"Graph construction completed in {time.time() - t1:.2f}s.")

    # Prepare MongoDB documents
    mongo = get_mongo_db()
    acc_graph_coll = mongo["account_graph"]

    logger.info(f"Materializing {len(all_accounts)} account documents into MongoDB 'account_graph'...")
    t2 = time.time()
    docs = []

    for aid in all_accounts:
        nbrs_dict = account_neighbors.get(aid, {})
        # Sort neighbors by shared_merchant_count descending
        sorted_nbrs = [
            {"account_id": other_id, "shared_merchant_count": count}
            for other_id, count in sorted(nbrs_dict.items(), key=lambda x: x[1], reverse=True)
        ]
        docs.append({
            "account_id": aid,
            "degree": len(sorted_nbrs),
            "is_flagged": bool(aid in fraud_accounts),
            "neighbors": sorted_nbrs,
            "updated_at": datetime.now(timezone.utc).isoformat()
        })

    # Drop old collection and insert new documents
    acc_graph_coll.drop()
    if docs:
        acc_graph_coll.insert_many(docs, ordered=False)

    acc_graph_coll.create_index([("account_id", ASCENDING)], unique=True)
    acc_graph_coll.create_index([("neighbors.account_id", ASCENDING)])
    acc_graph_coll.create_index([("is_flagged", ASCENDING)])
    acc_graph_coll.create_index([("degree", ASCENDING)])

    logger.info(f"Successfully loaded {len(docs)} documents into MongoDB 'account_graph' in {time.time() - t2:.2f}s.")

    # Sample verification
    sample_doc = acc_graph_coll.find_one({"degree": {"$gt": 0}})
    if sample_doc:
        logger.info(f"Sample verified: Account #{sample_doc['account_id']} | Degree: {sample_doc['degree']} | is_flagged: {sample_doc['is_flagged']} | First neighbor: {sample_doc['neighbors'][0]}")


if __name__ == "__main__":
    build_same_merchant_graph()

