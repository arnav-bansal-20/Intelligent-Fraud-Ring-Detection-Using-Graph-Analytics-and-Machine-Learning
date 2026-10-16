"""
Step 2 — SQL-Derived Graph Build (PostgreSQL → MongoDB)
=======================================================
Reads the transaction table from PostgreSQL and builds the graph layer
in MongoDB:

  - merchant_links: account ↔ merchant edges
        { account_id, merchant_id, first_used, last_used, usage_count }

  - account_graph: one document per account
        { _id: account_id,
          linked_merchants: [merchant_id, ...],
          linked_accounts:  [{ account_id, shared_merchants, first_overlap }],
          degree: int,
          last_updated: datetime }

    Two accounts are "linked" if they transacted at the SAME merchant within
    a configurable time window (default 24 hours). This is a PROXY for a
    shared-device/shared-IP signal, since the Sparkov dataset has no real
    device or IP data.

KNOWN LIMITATION: The shared-merchant-within-24h proxy is weaker than a
true shared-device signal, so graph features derived from it may provide
only a modest lift. We report the real numbers.
"""

import os
import sys
import time
import argparse
from datetime import datetime, timedelta
from collections import defaultdict

import psycopg
from pymongo import MongoClient, ASCENDING, IndexModel, UpdateOne

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DB_NAME  = os.getenv("PGDATABASE", "fraud_db")
DB_USER  = os.getenv("PGUSER", os.getenv("USER", "arnavbansal"))
DB_HOST  = os.getenv("PGHOST", "localhost")
DB_PORT  = os.getenv("PGPORT", "5432")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB  = os.getenv("MONGO_DB", "fraud_ring_db")

DEFAULT_WINDOW_HOURS = 24


def get_pg_conn_str():
    return f"dbname={DB_NAME} user={DB_USER} host={DB_HOST} port={DB_PORT}"


# ---------------------------------------------------------------------------
# Step 2a — Build merchant_links
# ---------------------------------------------------------------------------
def build_merchant_links(pg_conn, mongo_db, batch_size=5000):
    """
    For each (account_id, merchant_id) pair, compute first_used, last_used,
    and usage_count from the transaction table. Write to merchant_links.
    """
    print("\n[Step 2a] Building merchant_links...")
    t0 = time.time()

    coll = mongo_db["merchant_links"]
    coll.drop()

    with pg_conn.cursor() as cur:
        cur.execute("""
            SELECT account_id, merchant_id,
                   MIN(txn_timestamp) AS first_used,
                   MAX(txn_timestamp) AS last_used,
                   COUNT(*)           AS usage_count
            FROM transaction
            GROUP BY account_id, merchant_id
            ORDER BY account_id, merchant_id;
        """)

        docs = []
        total = 0
        for account_id, merchant_id, first_used, last_used, usage_count in cur:
            docs.append({
                "account_id":  account_id,
                "merchant_id": merchant_id,
                "first_used":  first_used,
                "last_used":   last_used,
                "usage_count": usage_count,
            })
            if len(docs) >= batch_size:
                coll.insert_many(docs)
                total += len(docs)
                docs = []
                if total % 50000 < batch_size:
                    print(f"    -> {total:,} merchant_links inserted...")

        if docs:
            coll.insert_many(docs)
            total += len(docs)

    # Indexes
    coll.create_indexes([
        IndexModel([("account_id", ASCENDING)]),
        IndexModel([("merchant_id", ASCENDING)]),
        IndexModel([("account_id", ASCENDING), ("merchant_id", ASCENDING)], unique=True),
    ])

    elapsed = time.time() - t0
    print(f"[+] merchant_links: {total:,} documents inserted in {elapsed:.1f}s")
    return total


# ---------------------------------------------------------------------------
# Step 2b — Build account_graph
# ---------------------------------------------------------------------------
def build_account_graph(pg_conn, mongo_db, window_hours=DEFAULT_WINDOW_HOURS,
                         batch_size=5000):
    """
    For each account, find other accounts that transacted at the same
    merchant within `window_hours` of each other. Build the account_graph
    adjacency collection.

    Strategy (memory-efficient, batched):
      1. Fetch all transactions ordered by (merchant_id, txn_timestamp).
      2. Sliding-window within each merchant to find co-occurring accounts.
      3. Accumulate adjacency per-account, then bulk-write to MongoDB.
    """
    print(f"\n[Step 2b] Building account_graph (window = {window_hours}h)...")
    t0 = time.time()
    window = timedelta(hours=window_hours)

    coll = mongo_db["account_graph"]
    coll.drop()

    # ── 1. Fetch transactions sorted by merchant, timestamp ───────────────
    print("[*] Fetching transactions from PostgreSQL...")
    with pg_conn.cursor() as cur:
        cur.execute("""
            SELECT account_id, merchant_id, txn_timestamp
            FROM transaction
            ORDER BY merchant_id, txn_timestamp;
        """)
        rows = cur.fetchall()
    print(f"[*] Fetched {len(rows):,} transactions.")

    # ── 2. Sliding window per merchant ────────────────────────────────────
    print("[*] Computing shared-merchant account links...")

    # Adjacency: account_id -> { linked_account_id: { shared_merchants: set, first_overlap: datetime } }
    adjacency = defaultdict(lambda: defaultdict(lambda: {"shared_merchants": set(), "first_overlap": None}))
    # Per-account merchant set
    account_merchants = defaultdict(set)

    # Group by merchant
    current_merchant = None
    merchant_window = []  # list of (account_id, timestamp)

    def process_merchant_window(merch_window, merch_id):
        """Within a single merchant's transactions, find account pairs within the time window."""
        n = len(merch_window)
        # merch_window is sorted by timestamp
        j = 0
        for i in range(n):
            aid_i, ts_i = merch_window[i]
            account_merchants[aid_i].add(merch_id)
            # Advance j to keep only entries within the window
            while j < i and (ts_i - merch_window[j][1]) > window:
                j += 1
            # All entries from j to i-1 are within the window of entry i
            for k in range(j, i):
                aid_k, ts_k = merch_window[k]
                if aid_k == aid_i:
                    continue
                # Ensure both directions
                overlap_time = ts_k  # the earlier timestamp
                for a, b in [(aid_i, aid_k), (aid_k, aid_i)]:
                    entry = adjacency[a][b]
                    entry["shared_merchants"].add(merch_id)
                    if entry["first_overlap"] is None or overlap_time < entry["first_overlap"]:
                        entry["first_overlap"] = overlap_time

    for account_id, merchant_id, ts in rows:
        if merchant_id != current_merchant:
            if merchant_window:
                process_merchant_window(merchant_window, current_merchant)
            current_merchant = merchant_id
            merchant_window = []
        merchant_window.append((account_id, ts))

    # Process last merchant
    if merchant_window:
        process_merchant_window(merchant_window, current_merchant)

    print(f"[*] Found {len(adjacency):,} accounts with at least one link.")

    # ── 3. Also capture accounts with NO links (they still need a node) ───
    all_accounts = set(account_merchants.keys())
    linked_accounts = set(adjacency.keys())
    isolated_accounts = all_accounts - linked_accounts

    # ── 4. Bulk-write to MongoDB ──────────────────────────────────────────
    print("[*] Writing account_graph documents to MongoDB...")
    now = datetime.utcnow()
    docs = []
    total = 0

    for acct_id in all_accounts:
        links = []
        for linked_id, info in adjacency.get(acct_id, {}).items():
            links.append({
                "account_id": linked_id,
                "shared_merchants": len(info["shared_merchants"]),
                "first_overlap": info["first_overlap"],
            })

        docs.append({
            "_id": acct_id,
            "linked_merchants": sorted(account_merchants.get(acct_id, set())),
            "linked_accounts": links,
            "degree": len(links),
            "last_updated": now,
        })

        if len(docs) >= batch_size:
            coll.insert_many(docs)
            total += len(docs)
            docs = []
            if total % 10000 < batch_size:
                print(f"    -> {total:,} account_graph documents written...")

    if docs:
        coll.insert_many(docs)
        total += len(docs)

    # Indexes
    coll.create_indexes([
        IndexModel([("degree", ASCENDING)]),
        IndexModel([("linked_accounts.account_id", ASCENDING)]),
    ])

    elapsed = time.time() - t0
    print(f"[+] account_graph: {total:,} documents in {elapsed:.1f}s")

    # ── Summary stats ─────────────────────────────────────────────────────
    n_with_links = coll.count_documents({"degree": {"$gt": 0}})
    pipeline = [{"$group": {"_id": None, "avg_degree": {"$avg": "$degree"}, "max_degree": {"$max": "$degree"}}}]
    stats = list(coll.aggregate(pipeline))
    avg_deg = stats[0]["avg_degree"] if stats else 0
    max_deg = stats[0]["max_degree"] if stats else 0

    print(f"\n{'=' * 55}")
    print(f"  ACCOUNT GRAPH — SUMMARY")
    print(f"{'=' * 55}")
    print(f"  Total accounts:          {total:>10,}")
    print(f"  Accounts with links:     {n_with_links:>10,}")
    print(f"  Isolated accounts:       {total - n_with_links:>10,}")
    print(f"  Avg degree:              {avg_deg:>10.2f}")
    print(f"  Max degree:              {max_deg:>10,}")
    print(f"  Time window:             {window_hours:>10}h")
    print(f"{'=' * 55}\n")

    return total


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Step 2: Build graph layer in MongoDB from PostgreSQL transactions"
    )
    parser.add_argument(
        "--window", type=int, default=DEFAULT_WINDOW_HOURS,
        help=f"Co-usage time window in hours (default: {DEFAULT_WINDOW_HOURS})",
    )
    parser.add_argument(
        "--db", default=MONGO_DB,
        help="MongoDB database name",
    )
    args = parser.parse_args()

    print(f"[*] Connecting to PostgreSQL...")
    pg_conn = psycopg.connect(get_pg_conn_str())

    print(f"[*] Connecting to MongoDB ({MONGO_URI})...")
    mongo_client = MongoClient(MONGO_URI)
    mongo_db = mongo_client[args.db]

    try:
        n_links = build_merchant_links(pg_conn, mongo_db)
        n_graph = build_account_graph(pg_conn, mongo_db, window_hours=args.window)

        # Final collection summary
        print(f"\n{'=' * 55}")
        print(f"  MONGODB COLLECTIONS — fraud_ring_db")
        print(f"{'=' * 55}")
        for cname in ["merchant_links", "account_graph", "elliptic_nodes", "elliptic_edges"]:
            cnt = mongo_db[cname].count_documents({})
            print(f"  {cname:25s} {cnt:>10,}")
        print(f"{'=' * 55}\n")

    finally:
        pg_conn.close()
        mongo_client.close()

    print("[DONE] Graph build finished.")


if __name__ == "__main__":
    main()
