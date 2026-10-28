#!/usr/bin/env python3
"""
Step 3: Graph Feature Extraction Pipeline
Queries MongoDB for graph-derived features per transaction and writes them
to the MongoDB 'fraud_features' collection.
Features computed:
 - shared_device_count: count of distinct other accounts sharing this device
 - shared_ip_count: count of distinct other accounts sharing this IP
 - account_degree: degree centrality (# connected accounts in account_graph)
 - hops_to_nearest_flagged: shortest path distance (BFS) to a flagged fraud account
 - flagged_neighbors_count: number of directly adjacent accounts flagged for fraud
 - device_usage_count: usage velocity of the device
 - ip_usage_count: usage velocity of the IP
"""

import os
import sys
import argparse
import logging
from collections import deque
from datetime import datetime
import psycopg2
from pymongo import MongoClient, ASCENDING, UpdateOne

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.db_config import (
    PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DATABASE,
    MONGO_URI, MONGO_DB_NAME
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def get_mongo_db():
    client = MongoClient(MONGO_URI)
    return client[MONGO_DB_NAME]

def get_pg_connection():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        dbname=PG_DATABASE
    )

def build_graph_lookups(db):
    """
    Builds in-memory lookup structures from MongoDB collections for fast batch feature extraction.
    """
    logger.info("Loading account_graph, device_links, and ip_links from MongoDB...")
    acc_graph_coll = db["account_graph"]
    dev_links_coll = db["device_links"]
    ip_links_coll = db["ip_links"]

    # Map device_id -> set of account_ids, and device_id -> total usage
    device_to_accounts = {}
    device_velocity = {}
    for doc in dev_links_coll.find({}, {"device_id": 1, "account_id": 1, "usage_count": 1}):
        d_id = doc["device_id"]
        if d_id not in device_to_accounts:
            device_to_accounts[d_id] = set()
            device_velocity[d_id] = 0
        device_to_accounts[d_id].add(doc["account_id"])
        device_velocity[d_id] += doc.get("usage_count", 1)

    # Map ip_id -> set of account_ids, and ip_id -> total usage
    ip_to_accounts = {}
    ip_velocity = {}
    for doc in ip_links_coll.find({}, {"ip_id": 1, "account_id": 1, "usage_count": 1}):
        i_id = doc["ip_id"]
        if i_id not in ip_to_accounts:
            ip_to_accounts[i_id] = set()
            ip_velocity[i_id] = 0
        ip_to_accounts[i_id].add(doc["account_id"])
        ip_velocity[i_id] += doc.get("usage_count", 1)

    # Adjacency list: account_id -> set of linked accounts, and set of flagged accounts
    adjacency = {}
    flagged_accounts = set()
    account_degree_map = {}

    for doc in acc_graph_coll.find({}, {"account_id": 1, "linked_accounts": 1, "degree": 1, "is_flagged": 1}):
        a_id = doc["account_id"]
        adjacency[a_id] = set(doc.get("linked_accounts", []))
        account_degree_map[a_id] = doc.get("degree", 0)
        if doc.get("is_flagged", False):
            flagged_accounts.add(a_id)

    logger.info(f"Loaded {len(adjacency)} accounts into graph memory ({len(flagged_accounts)} flagged).")
    return {
        "device_to_accounts": device_to_accounts,
        "device_velocity": device_velocity,
        "ip_to_accounts": ip_to_accounts,
        "ip_velocity": ip_velocity,
        "adjacency": adjacency,
        "flagged_accounts": flagged_accounts,
        "account_degree_map": account_degree_map
    }

def compute_shortest_hops_to_flagged(account_id: int, adjacency: dict, flagged_accounts: set, max_hops: int = 4) -> int:
    """
    Breadth-First Search (BFS) to compute shortest distance (hops) to any flagged fraud account.
    Returns:
      0 if account itself is flagged
      k if connected within k hops (1..max_hops)
      -1 if disconnected or > max_hops
    """
    if account_id in flagged_accounts:
        return 0

    visited = {account_id}
    queue = deque([(account_id, 0)])

    while queue:
        curr, dist = queue.popleft()
        if dist >= max_hops:
            continue

        for neighbor in adjacency.get(curr, []):
            if neighbor in flagged_accounts:
                return dist + 1
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, dist + 1))

    return -1

def extract_and_write_features(db, batch_size: int = 5000, limit: int = None):
    lookups = build_graph_lookups(db)
    adjacency = lookups["adjacency"]
    flagged_accounts = lookups["flagged_accounts"]
    device_to_accounts = lookups["device_to_accounts"]
    device_velocity = lookups["device_velocity"]
    ip_to_accounts = lookups["ip_to_accounts"]
    ip_velocity = lookups["ip_velocity"]
    account_degree_map = lookups["account_degree_map"]

    # Precompute hops for all accounts to optimize lookup
    logger.info("Precomputing shortest hops to flagged accounts for all network nodes...")
    account_hops_cache = {}
    for acc_id in adjacency.keys():
        account_hops_cache[acc_id] = compute_shortest_hops_to_flagged(acc_id, adjacency, flagged_accounts)

    logger.info("Querying transactions from PostgreSQL...")
    conn = get_pg_connection()
    cur = conn.cursor()

    query = """
        SELECT trans_num, account_id, device_id, ip_id, amt, unix_time, is_fraud
        FROM transaction
        ORDER BY unix_time ASC
    """
    if limit:
        query += f" LIMIT {limit}"
    query += ";"

    cur.execute(query)

    fraud_features_coll = db["fraud_features"]
    fraud_features_coll.drop()  # fresh write

    total_extracted = 0
    feature_docs = []

    for row in cur:
        trans_num, acc_id, dev_id, ip_id, amt, unix_time, is_fraud = row

        # Shared device count: other accounts using this device
        other_device_accs = device_to_accounts.get(dev_id, set()) - {acc_id} if dev_id else set()
        shared_dev_count = len(other_device_accs)

        # Shared IP count: other accounts using this IP
        other_ip_accs = ip_to_accounts.get(ip_id, set()) - {acc_id} if ip_id else set()
        shared_ip_count = len(other_ip_accs)

        # Degree
        deg = account_degree_map.get(acc_id, 0)

        # Hops to nearest flagged
        hops = account_hops_cache.get(acc_id, -1)

        # Flagged neighbors
        neighbors = adjacency.get(acc_id, set())
        flagged_neighbors = len(neighbors.intersection(flagged_accounts))

        # Device & IP usage counts
        dev_usage = device_velocity.get(dev_id, 1)
        ip_usage = ip_velocity.get(ip_id, 1)

        doc = {
            "trans_num": trans_num,
            "account_id": acc_id,
            "device_id": dev_id,
            "ip_id": ip_id,
            "amt": float(amt),
            "unix_time": unix_time,
            "shared_device_count": shared_dev_count,
            "shared_ip_count": shared_ip_count,
            "account_degree": deg,
            "hops_to_nearest_flagged": hops,
            "flagged_neighbors_count": flagged_neighbors,
            "device_usage_count": dev_usage,
            "ip_usage_count": ip_usage,
            "is_fraud": is_fraud,
            "model_version": "v1.0-graph",
            "extracted_at": datetime.utcnow().isoformat()
        }
        feature_docs.append(doc)

        if len(feature_docs) >= batch_size:
            fraud_features_coll.insert_many(feature_docs, ordered=False)
            total_extracted += len(feature_docs)
            feature_docs = []
            logger.info(f"Extracted features for {total_extracted:,} transactions...")

    if feature_docs:
        fraud_features_coll.insert_many(feature_docs, ordered=False)
        total_extracted += len(feature_docs)

    # Indices on fraud_features
    fraud_features_coll.create_index([("trans_num", ASCENDING)], unique=True)
    fraud_features_coll.create_index([("account_id", ASCENDING)])
    fraud_features_coll.create_index([("unix_time", ASCENDING)])
    fraud_features_coll.create_index([("is_fraud", ASCENDING)])
    fraud_features_coll.create_index([("hops_to_nearest_flagged", ASCENDING)])

    cur.close()
    conn.close()

    logger.info(f"Successfully populated 'fraud_features' collection with {total_extracted:,} records.")

def print_summary(db):
    coll = db["fraud_features"]
    cnt = coll.count_documents({})
    hops_0 = coll.count_documents({"hops_to_nearest_flagged": 0})
    hops_1 = coll.count_documents({"hops_to_nearest_flagged": 1})
    shared_dev = coll.count_documents({"shared_device_count": {"$gt": 0}})

    print("\n" + "="*50)
    print("MongoDB fraud_features Summary:")
    print("="*50)
    print(f" - Total Feature Records    : {cnt:>8,}")
    print(f" - With Shared Devices      : {shared_dev:>8,}")
    print(f" - Self Flagged (Hops = 0)  : {hops_0:>8,}")
    print(f" - 1-Hop to Flagged Account : {hops_1:>8,}")
    sample = coll.find_one()
    if sample:
        print("\nSample Document:")
        for k, v in sample.items():
            if k != "_id":
                print(f"   {k.ljust(25)}: {v}")
    print("="*50 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract graph-derived features into MongoDB fraud_features collection")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of transactions (default: all)")
    args = parser.parse_args()

    db = get_mongo_db()
    extract_and_write_features(db, limit=args.limit)
    print_summary(db)

