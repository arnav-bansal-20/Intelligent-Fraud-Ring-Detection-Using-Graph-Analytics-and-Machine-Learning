#!/usr/bin/env python3
"""
Step 2: MongoDB Graph & Relationship Layer Loader
- Loads the 3 Elliptic files into MongoDB collections:
  * elliptic_nodes: txId, class ('illicit', 'licit', 'unknown'), time_step, raw_class
  * elliptic_edges: txId1 (source), txId2 (target)
- Loads the banking relationship layer from PostgreSQL:
  * device_links: account_id, device_id, usage_count, first_used, last_used
  * ip_links: account_id, ip_id, usage_count, first_used, last_used
  * account_graph: account_id, linked_devices, linked_ips, linked_accounts, degree, is_flagged
"""

import os
import sys
import argparse
import logging
from collections import defaultdict
import pandas as pd
import psycopg2
from pymongo import MongoClient, ASCENDING, UpdateOne

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.db_config import (
    PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DATABASE,
    MONGO_URI, MONGO_DB_NAME, DATA_DIR
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

def load_elliptic_data(db, limit_edges: int = None, limit_features: int = None):
    """
    Ingests Elliptic transaction graph dataset into MongoDB.
    """
    classes_file = os.path.join(DATA_DIR, "elliptic_txs_classes.csv")
    edges_file = os.path.join(DATA_DIR, "elliptic_txs_edgelist.csv")
    features_file = os.path.join(DATA_DIR, "elliptic_txs_features.csv")

    logger.info("Reading Elliptic classes...")
    df_classes = pd.read_csv(classes_file)
    # Mapping class: '1' -> illicit (fraud), '2' -> licit, 'unknown' -> unknown
    class_map = {}
    for _, row in df_classes.iterrows():
        raw_c = str(row["class"]).strip()
        label = "illicit" if raw_c == "1" else ("licit" if raw_c == "2" else "unknown")
        class_map[int(row["txId"])] = (raw_c, label)

    logger.info(f"Loaded {len(class_map)} class labels.")

    # Read timesteps from features file (first 2 columns: txId, timestep)
    logger.info("Reading Elliptic timesteps from features file...")
    timestep_map = {}
    chunk_reader = pd.read_csv(features_file, header=None, usecols=[0, 1], chunksize=50000, nrows=limit_features)
    for chunk in chunk_reader:
        for _, row in chunk.iterrows():
            timestep_map[int(row[0])] = int(row[1])

    # Insert / Upsert into elliptic_nodes
    logger.info("Populating MongoDB 'elliptic_nodes' collection...")
    nodes_coll = db["elliptic_nodes"]
    nodes_coll.drop()  # fresh reload

    node_docs = []
    batch_size = 20000
    for tx_id, (raw_c, label) in class_map.items():
        node_docs.append({
            "txId": tx_id,
            "raw_class": raw_c,
            "label": label,
            "is_illicit": 1 if raw_c == "1" else 0,
            "timestep": timestep_map.get(tx_id, 1)
        })
        if len(node_docs) >= batch_size:
            nodes_coll.insert_many(node_docs, ordered=False)
            node_docs = []
    if node_docs:
        nodes_coll.insert_many(node_docs, ordered=False)

    nodes_coll.create_index([("txId", ASCENDING)], unique=True)
    nodes_coll.create_index([("label", ASCENDING)])
    nodes_coll.create_index([("is_illicit", ASCENDING)])
    logger.info(f"Loaded {nodes_coll.count_documents({})} nodes into 'elliptic_nodes'.")

    # Ingest Edges
    logger.info(f"Reading and loading Elliptic edges from {edges_file}...")
    edges_coll = db["elliptic_edges"]
    edges_coll.drop()

    df_edges = pd.read_csv(edges_file, nrows=limit_edges)
    edge_docs = []
    for _, row in df_edges.iterrows():
        edge_docs.append({
            "txId1": int(row["txId1"]),
            "txId2": int(row["txId2"]),
            "flow": "fund_transfer"
        })
        if len(edge_docs) >= batch_size:
            edges_coll.insert_many(edge_docs, ordered=False)
            edge_docs = []
    if edge_docs:
        edges_coll.insert_many(edge_docs, ordered=False)

    edges_coll.create_index([("txId1", ASCENDING)])
    edges_coll.create_index([("txId2", ASCENDING)])
    edges_coll.create_index([("txId1", ASCENDING), ("txId2", ASCENDING)])
    logger.info(f"Loaded {edges_coll.count_documents({})} edges into 'elliptic_edges'.")

def load_relational_graph_layer(db):
    """
    Extracts banking transactions from PostgreSQL and materializes the MongoDB
    graph layers: device_links, ip_links, and account_graph.
    """
    logger.info("Extracting relationship edges from PostgreSQL...")
    conn = get_pg_connection()
    cur = conn.cursor()

    # 1. Device links: account <-> device
    cur.execute("""
        SELECT
            account_id,
            device_id,
            COUNT(*) AS usage_count,
            MIN(trans_date_trans_time) AS first_used,
            MAX(trans_date_trans_time) AS last_used
        FROM transaction
        WHERE device_id IS NOT NULL
        GROUP BY account_id, device_id;
    """)
    device_links_data = cur.fetchall()

    logger.info(f"Materializing {len(device_links_data)} device_links into MongoDB...")
    dev_links_coll = db["device_links"]
    dev_links_coll.drop()
    dev_docs = [
        {
            "account_id": r[0],
            "device_id": r[1],
            "usage_count": r[2],
            "first_used": str(r[3]),
            "last_used": str(r[4])
        }
        for r in device_links_data
    ]
    if dev_docs:
        dev_links_coll.insert_many(dev_docs, ordered=False)
    dev_links_coll.create_index([("account_id", ASCENDING)])
    dev_links_coll.create_index([("device_id", ASCENDING)])
    dev_links_coll.create_index([("account_id", ASCENDING), ("device_id", ASCENDING)], unique=True)

    # 2. IP links: account <-> ip
    cur.execute("""
        SELECT
            account_id,
            ip_id,
            COUNT(*) AS usage_count,
            MIN(trans_date_trans_time) AS first_used,
            MAX(trans_date_trans_time) AS last_used
        FROM transaction
        WHERE ip_id IS NOT NULL
        GROUP BY account_id, ip_id;
    """)
    ip_links_data = cur.fetchall()

    logger.info(f"Materializing {len(ip_links_data)} ip_links into MongoDB...")
    ip_links_coll = db["ip_links"]
    ip_links_coll.drop()
    ip_docs = [
        {
            "account_id": r[0],
            "ip_id": r[1],
            "usage_count": r[2],
            "first_used": str(r[3]),
            "last_used": str(r[4])
        }
        for r in ip_links_data
    ]
    if ip_docs:
        ip_links_coll.insert_many(ip_docs, ordered=False)
    ip_links_coll.create_index([("account_id", ASCENDING)])
    ip_links_coll.create_index([("ip_id", ASCENDING)])
    ip_links_coll.create_index([("account_id", ASCENDING), ("ip_id", ASCENDING)], unique=True)

    # 3. Precompute account_graph adjacency lists
    # Discover shared-device and shared-IP connections between accounts
    logger.info("Computing account_graph adjacency lists...")
    acc_to_devices = defaultdict(set)
    device_to_accs = defaultdict(set)
    for r in device_links_data:
        acc_id, dev_id = r[0], r[1]
        acc_to_devices[acc_id].add(dev_id)
        device_to_accs[dev_id].add(acc_id)

    acc_to_ips = defaultdict(set)
    ip_to_accs = defaultdict(set)
    for r in ip_links_data:
        acc_id, ip_id = r[0], r[1]
        acc_to_ips[acc_id].add(ip_id)
        ip_to_accs[ip_id].add(acc_id)

    # Check which accounts have known fraudulent transactions
    cur.execute("""
        SELECT account_id, MAX(is_fraud) as has_fraud, COUNT(*) as tx_count
        FROM transaction
        GROUP BY account_id;
    """)
    account_stats = {r[0]: {"is_flagged": (r[1] == 1), "tx_count": r[2]} for r in cur.fetchall()}

    cur.close()
    conn.close()

    # Build graph per account
    all_accounts = set(account_stats.keys())
    account_graph_docs = []

    for acc_id in all_accounts:
        devs = acc_to_devices.get(acc_id, set())
        ips = acc_to_ips.get(acc_id, set())

        # Connected accounts via shared devices or shared IPs
        linked_accounts = set()
        for dev in devs:
            for other_acc in device_to_accs[dev]:
                if other_acc != acc_id:
                    linked_accounts.add(other_acc)

        for ip in ips:
            for other_acc in ip_to_accs[ip]:
                if other_acc != acc_id:
                    linked_accounts.add(other_acc)

        stats = account_stats.get(acc_id, {"is_flagged": False, "tx_count": 0})

        account_graph_docs.append({
            "account_id": acc_id,
            "linked_devices": list(devs),
            "linked_ips": list(ips),
            "linked_accounts": list(linked_accounts),
            "device_count": len(devs),
            "ip_count": len(ips),
            "degree": len(linked_accounts),
            "is_flagged": stats["is_flagged"],
            "tx_count": stats["tx_count"]
        })

    acc_graph_coll = db["account_graph"]
    acc_graph_coll.drop()
    if account_graph_docs:
        acc_graph_coll.insert_many(account_graph_docs, ordered=False)
    acc_graph_coll.create_index([("account_id", ASCENDING)], unique=True)
    acc_graph_coll.create_index([("degree", ASCENDING)])
    acc_graph_coll.create_index([("is_flagged", ASCENDING)])
    acc_graph_coll.create_index([("linked_accounts", ASCENDING)])

    logger.info(f"Loaded {len(account_graph_docs)} accounts into 'account_graph' collection.")

def print_summary(db):
    print("\n" + "="*50)
    print("MongoDB Graph & Relationship Collections Summary:")
    print("="*50)
    for coll_name in ["elliptic_nodes", "elliptic_edges", "device_links", "ip_links", "account_graph"]:
        cnt = db[coll_name].count_documents({})
        print(f" - {coll_name.ljust(18)}: {cnt:>8,} documents")

    illicit_cnt = db["elliptic_nodes"].count_documents({"label": "illicit"})
    print(f" - Elliptic Illicit Nodes: {illicit_cnt:>8,}")

    flagged_accs = db["account_graph"].count_documents({"is_flagged": True})
    high_degree = db["account_graph"].count_documents({"degree": {"$gt": 0}})
    print(f" - Flagged Accounts      : {flagged_accs:>8,}")
    print(f" - Shared Ring Accounts  : {high_degree:>8,} (connected to other accounts)")
    print("="*50 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load Elliptic Graph and Relationship Layer into MongoDB")
    parser.add_argument("--limit-edges", type=int, default=None, help="Limit elliptic edges (optional)")
    parser.add_argument("--summary-only", action="store_true", help="Print summary without reloading")
    args = parser.parse_args()

    db = get_mongo_db()
    if args.summary_only:
        print_summary(db)
    else:
        load_elliptic_data(db, limit_edges=args.limit_edges)
        load_relational_graph_layer(db)
        print_summary(db)

