"""
Step 1 — Elliptic Dataset Loader (MongoDB)
==========================================
Loads the Elliptic Bitcoin transaction graph into MongoDB.

Collections created:
  - elliptic_nodes: one document per transaction node
        _id (auto), txId (int), class ("illicit"|"licit"|"unlabeled"),
        time_step (int), features (list of 166 floats)
  - elliptic_edges: one document per directed edge
        _id (auto), txId1 (int), txId2 (int)

IMPORTANT: The Elliptic dataset is a STANDALONE graph. It CANNOT be joined
to the Sparkov fraud data. It is used only for a separate graph-ML
experiment (Step 6).

Class mapping (from the paper):
  1 → illicit
  2 → licit
  unknown → unlabeled
"""

import os
import sys
import time
import argparse

import pandas as pd
from pymongo import MongoClient, ASCENDING, IndexModel

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB  = os.getenv("MONGO_DB", "fraud_ring_db")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "Datasets")

CLASS_MAP = {"1": "illicit", "2": "licit"}


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------
def load_elliptic(data_dir: str, db_name: str, drop_existing: bool = True):
    client = MongoClient(MONGO_URI)
    db = client[db_name]

    classes_path  = os.path.join(data_dir, "elliptic_txs_classes.csv")
    features_path = os.path.join(data_dir, "elliptic_txs_features.csv")
    edges_path    = os.path.join(data_dir, "elliptic_txs_edgelist.csv")

    for p in [classes_path, features_path, edges_path]:
        if not os.path.isfile(p):
            print(f"[ERROR] File not found: {p}")
            sys.exit(1)

    # ── Drop existing collections if requested ────────────────────────────
    if drop_existing:
        print("[*] Dropping existing elliptic_nodes / elliptic_edges...")
        db.drop_collection("elliptic_nodes")
        db.drop_collection("elliptic_edges")

    # ── Load classes ──────────────────────────────────────────────────────
    print(f"[*] Reading classes from {classes_path}...")
    classes_df = pd.read_csv(classes_path)
    classes_df.columns = ["txId", "class"]
    class_lookup = {}
    for _, r in classes_df.iterrows():
        raw = str(r["class"]).strip()
        class_lookup[int(r["txId"])] = CLASS_MAP.get(raw, "unlabeled")

    counts = {"illicit": 0, "licit": 0, "unlabeled": 0}
    for v in class_lookup.values():
        counts[v] += 1
    print(f"[+] Classes loaded: {counts}")

    # ── Load features ─────────────────────────────────────────────────────
    print(f"[*] Reading features from {features_path}...")
    t0 = time.time()
    # The features CSV has no header; col 0 = txId, col 1 = time_step,
    # cols 2..167 = 166 features
    feat_df = pd.read_csv(features_path, header=None)
    print(f"[*] Features loaded: {len(feat_df):,} rows in {time.time() - t0:.1f}s")

    # ── Build node documents ──────────────────────────────────────────────
    print("[*] Building node documents...")
    nodes = []
    batch_size = 10000
    coll_nodes = db["elliptic_nodes"]

    for i, row in feat_df.iterrows():
        tx_id = int(row[0])
        time_step = int(row[1])
        features = [float(row[j]) for j in range(2, len(row))]
        cls = class_lookup.get(tx_id, "unlabeled")

        nodes.append({
            "txId": tx_id,
            "class": cls,
            "time_step": time_step,
            "features": features,
        })

        if len(nodes) >= batch_size:
            coll_nodes.insert_many(nodes)
            nodes = []
            if (i + 1) % 50000 < batch_size:
                print(f"    -> {i + 1:,} nodes inserted...")

    if nodes:
        coll_nodes.insert_many(nodes)
    print(f"[+] Inserted {len(feat_df):,} nodes into elliptic_nodes.")

    # ── Load edges ────────────────────────────────────────────────────────
    print(f"[*] Reading edges from {edges_path}...")
    edges_df = pd.read_csv(edges_path)
    edges_df.columns = ["txId1", "txId2"]

    print("[*] Inserting edges...")
    edges = []
    coll_edges = db["elliptic_edges"]

    for i, (_, r) in enumerate(edges_df.iterrows()):
        edges.append({"txId1": int(r["txId1"]), "txId2": int(r["txId2"])})
        if len(edges) >= batch_size:
            coll_edges.insert_many(edges)
            edges = []

    if edges:
        coll_edges.insert_many(edges)
    print(f"[+] Inserted {len(edges_df):,} edges into elliptic_edges.")

    # ── Create indexes ────────────────────────────────────────────────────
    print("[*] Creating indexes...")
    coll_nodes.create_indexes([
        IndexModel([("txId", ASCENDING)], unique=True),
        IndexModel([("class", ASCENDING)]),
        IndexModel([("time_step", ASCENDING)]),
    ])
    coll_edges.create_indexes([
        IndexModel([("txId1", ASCENDING)]),
        IndexModel([("txId2", ASCENDING)]),
    ])
    print("[+] Indexes created.")

    # ── Summary ───────────────────────────────────────────────────────────
    n_nodes = coll_nodes.count_documents({})
    n_edges = coll_edges.count_documents({})
    n_illicit = coll_nodes.count_documents({"class": "illicit"})
    n_licit   = coll_nodes.count_documents({"class": "licit"})
    n_unknown = coll_nodes.count_documents({"class": "unlabeled"})

    print(f"\n{'=' * 50}")
    print(f"  ELLIPTIC GRAPH — LOAD SUMMARY")
    print(f"{'=' * 50}")
    print(f"  Nodes:      {n_nodes:>10,}")
    print(f"    illicit:  {n_illicit:>10,}")
    print(f"    licit:    {n_licit:>10,}")
    print(f"    unlabeled:{n_unknown:>10,}")
    print(f"  Edges:      {n_edges:>10,}")
    print(f"{'=' * 50}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Load Elliptic dataset into MongoDB")
    parser.add_argument("--data-dir", default=DATA_DIR, help="Directory containing Elliptic CSVs")
    parser.add_argument("--db", default=MONGO_DB, help="MongoDB database name")
    parser.add_argument("--no-drop", action="store_true", help="Don't drop existing collections first")
    args = parser.parse_args()

    load_elliptic(args.data_dir, args.db, drop_existing=not args.no_drop)
    print("[DONE] Elliptic loader finished.")


if __name__ == "__main__":
    main()
