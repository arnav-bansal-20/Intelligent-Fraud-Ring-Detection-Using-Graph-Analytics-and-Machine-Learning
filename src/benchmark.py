"""
Step 5 — Hybrid DBMS Multi-Hop Graph Traversal Benchmark
========================================================
Rigorous latency comparison between MongoDB (Graph Document Layer)
and PostgreSQL (Relational Transaction Ledger) for multi-hop graph
traversal queries:

  Query: "Find all distinct accounts connected to account X within k hops"
         where k in {1, 2, 3}.

Architectural Models Compared:
  1. MongoDB Document Adjacency (BFS Index Lookup)
       Iterative retrieval using indexed `_id` on `account_graph`.
  2. MongoDB `$graphLookup` (Native Document Graph Engine)
       Server-side recursive graph lookup aggregation.
  3. PostgreSQL Relational Multi-Hop CTE (Optimized Relational CTE)
       Subquery-distinct recursive common table expression.
  4. PostgreSQL Relational Raw Ledger Join (1-Hop Baseline)
       Direct self-join on the 1.85M row `transaction` table.

Statistical Metrics:
  - Mean latency (ms)
  - Median / p50 latency (ms)
  - 95th Percentile / p95 latency (ms)
  - 99th Percentile / p99 latency (ms)
  - Standard Deviation (ms)
  - Speedup Factor (PostgreSQL / MongoDB)
"""

import os
import sys
import time
import json
import random
import argparse
from datetime import datetime

import numpy as np
import psycopg
from pymongo import MongoClient


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
# 1. MongoDB Query Implementations
# ---------------------------------------------------------------------------
def query_mongo_bfs(coll, start_account_id, k):
    """
    MongoDB Document Adjacency: Iterative BFS over pre-structured adjacency lists.
    """
    visited = set()
    frontier = {start_account_id}

    for depth in range(k):
        if not frontier:
            break
        docs = coll.find(
            {"_id": {"$in": list(frontier)}},
            {"linked_accounts.account_id": 1}
        )
        visited.update(frontier)
        next_frontier = set()
        for doc in docs:
            for edge in doc.get("linked_accounts", []):
                acc = edge["account_id"]
                if acc not in visited:
                    next_frontier.add(acc)
        frontier = next_frontier

    visited.discard(start_account_id)
    return len(visited)


def query_mongo_graph_lookup(coll, start_account_id, k):
    """
    MongoDB Native $graphLookup aggregation pipeline.
    """
    pipeline = [
        {"$match": {"_id": start_account_id}},
        {
            "$graphLookup": {
                "from": "account_graph",
                "startWith": "$linked_accounts.account_id",
                "connectFromField": "linked_accounts.account_id",
                "connectToField": "_id",
                "maxDepth": k - 1,
                "as": "network"
            }
        },
        {"$project": {"count": {"$size": "$network"}}}
    ]
    results = list(coll.aggregate(pipeline))
    return results[0]["count"] if results else 0


# ---------------------------------------------------------------------------
# 2. PostgreSQL Query Implementations
# ---------------------------------------------------------------------------
def query_pg_cte(cur, start_account_id, k):
    """
    PostgreSQL Multi-Hop Query using optimized staged CTEs.
    """
    if k == 1:
        query = """
            WITH user_merchants AS (
                SELECT DISTINCT merchant_id FROM transaction WHERE account_id = %s
            )
            SELECT COUNT(DISTINCT account_id)
            FROM transaction
            WHERE merchant_id IN (SELECT merchant_id FROM user_merchants)
              AND account_id != %s;
        """
        cur.execute(query, (start_account_id, start_account_id))
    elif k == 2:
        query = """
            WITH m1 AS (
                SELECT DISTINCT merchant_id FROM transaction WHERE account_id = %s
            ),
            a1 AS (
                SELECT DISTINCT account_id FROM transaction WHERE merchant_id IN (SELECT merchant_id FROM m1) AND account_id != %s
            ),
            m2 AS (
                SELECT DISTINCT merchant_id FROM transaction WHERE account_id IN (SELECT account_id FROM a1)
            ),
            a2 AS (
                SELECT DISTINCT account_id FROM transaction WHERE merchant_id IN (SELECT merchant_id FROM m2) AND account_id != %s
            )
            SELECT COUNT(DISTINCT account_id) FROM a2;
        """
        cur.execute(query, (start_account_id, start_account_id, start_account_id))
    elif k == 3:
        query = """
            WITH m1 AS (
                SELECT DISTINCT merchant_id FROM transaction WHERE account_id = %s
            ),
            a1 AS (
                SELECT DISTINCT account_id FROM transaction WHERE merchant_id IN (SELECT merchant_id FROM m1) AND account_id != %s
            ),
            m2 AS (
                SELECT DISTINCT merchant_id FROM transaction WHERE account_id IN (SELECT account_id FROM a1)
            ),
            a2 AS (
                SELECT DISTINCT account_id FROM transaction WHERE merchant_id IN (SELECT merchant_id FROM m2) AND account_id != %s
            ),
            m3 AS (
                SELECT DISTINCT merchant_id FROM transaction WHERE account_id IN (SELECT account_id FROM a2)
            ),
            a3 AS (
                SELECT DISTINCT account_id FROM transaction WHERE merchant_id IN (SELECT merchant_id FROM m3) AND account_id != %s
            )
            SELECT COUNT(DISTINCT account_id) FROM a3;
        """
        cur.execute(query, (start_account_id, start_account_id, start_account_id, start_account_id))
    else:
        raise ValueError(f"Unsupported k: {k}")

    return cur.fetchone()[0]


def query_pg_raw_join(cur, start_account_id):
    """
    PostgreSQL Raw Self-Join on transaction table (1-hop only).
    """
    query = """
        SELECT COUNT(DISTINCT t2.account_id)
        FROM transaction t1
        JOIN transaction t2 ON t1.merchant_id = t2.merchant_id
        WHERE t1.account_id = %s AND t2.account_id != %s;
    """
    cur.execute(query, (start_account_id, start_account_id))
    return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# 3. Benchmark Runner
# ---------------------------------------------------------------------------
def calculate_stats(latencies_ms):
    arr = np.array(latencies_ms)
    return {
        "trials": len(arr),
        "mean_ms": float(np.mean(arr)),
        "std_ms": float(np.std(arr)),
        "min_ms": float(np.min(arr)),
        "p50_ms": float(np.percentile(arr, 50)),
        "p95_ms": float(np.percentile(arr, 95)),
        "p99_ms": float(np.percentile(arr, 99)),
        "max_ms": float(np.max(arr)),
    }


def run_benchmark(trials=50, hops=(1, 2, 3), output_file="models/benchmark_results.json"):
    print("=" * 85)
    print("Step 5 — Hybrid DBMS Multi-Hop Graph Traversal Benchmark")
    print(f"PostgreSQL (Relational Core) vs MongoDB (Graph Layer) | Trials: {trials} per test")
    print("=" * 85)

    # Establish connections
    pg_conn = psycopg.connect(get_pg_conn_str())
    mongo_client = MongoClient(MONGO_URI)
    mongo_db = mongo_client[MONGO_DB]
    account_coll = mongo_db["account_graph"]

    # Sample random active accounts
    print("\nFetching candidate accounts from database...")
    with pg_conn.cursor() as cur:
        cur.execute("SELECT account_id FROM account ORDER BY account_id;")
        all_accounts = [row[0] for row in cur.fetchall()]

    random.seed(42)
    sample_accounts = random.sample(all_accounts, min(trials, len(all_accounts)))
    print(f"Sampled {len(sample_accounts)} unique account seeds across the network.\n")

    results = {}

    # Warm-up run
    print("Warming up database query caches...")
    _ = query_mongo_bfs(account_coll, sample_accounts[0], 1)
    _ = query_mongo_graph_lookup(account_coll, sample_accounts[0], 1)
    with pg_conn.cursor() as cur:
        _ = query_pg_cte(cur, sample_accounts[0], 1)
    print("Warm-up complete.\n")

    # -----------------------------------------------------------------------
    # Run Benchmark for Each Hop Depth
    # -----------------------------------------------------------------------
    for k in hops:
        print(f"--- BENCHMARKING {k}-HOP TRAVERSAL ({trials} trials) ---")

        # 1. MongoDB Document BFS
        latencies_mongo_bfs = []
        for acc in sample_accounts:
            t0 = time.perf_counter()
            cnt = query_mongo_bfs(account_coll, acc, k)
            latencies_mongo_bfs.append((time.perf_counter() - t0) * 1000)
        stats_mongo_bfs = calculate_stats(latencies_mongo_bfs)
        print(f"  [Mongo BFS]          Mean: {stats_mongo_bfs['mean_ms']:>7.2f} ms | p50: {stats_mongo_bfs['p50_ms']:>7.2f} ms | p95: {stats_mongo_bfs['p95_ms']:>7.2f} ms")

        # 2. MongoDB $graphLookup
        latencies_mongo_gl = []
        for acc in sample_accounts:
            t0 = time.perf_counter()
            cnt = query_mongo_graph_lookup(account_coll, acc, k)
            latencies_mongo_gl.append((time.perf_counter() - t0) * 1000)
        stats_mongo_gl = calculate_stats(latencies_mongo_gl)
        print(f"  [Mongo $graphLookup] Mean: {stats_mongo_gl['mean_ms']:>7.2f} ms | p50: {stats_mongo_gl['p50_ms']:>7.2f} ms | p95: {stats_mongo_gl['p95_ms']:>7.2f} ms")

        # 3. PostgreSQL CTE
        latencies_pg_cte = []
        with pg_conn.cursor() as cur:
            for acc in sample_accounts:
                t0 = time.perf_counter()
                cnt = query_pg_cte(cur, acc, k)
                latencies_pg_cte.append((time.perf_counter() - t0) * 1000)
        stats_pg_cte = calculate_stats(latencies_pg_cte)
        print(f"  [Postgres CTE]       Mean: {stats_pg_cte['mean_ms']:>7.2f} ms | p50: {stats_pg_cte['p50_ms']:>7.2f} ms | p95: {stats_pg_cte['p95_ms']:>7.2f} ms")

        # Compute speedup
        speedup_vs_gl = stats_pg_cte["mean_ms"] / max(0.01, stats_mongo_gl["mean_ms"])
        speedup_vs_bfs = stats_pg_cte["mean_ms"] / max(0.01, stats_mongo_bfs["mean_ms"])

        print(f"  --> Speedup: MongoDB BFS is {speedup_vs_bfs:.1f}x faster | $graphLookup is {speedup_vs_gl:.1f}x faster than PostgreSQL\n")

        results[f"{k}_hop"] = {
            "depth_k": k,
            "trials": trials,
            "mongo_bfs": stats_mongo_bfs,
            "mongo_graph_lookup": stats_mongo_gl,
            "postgres_cte": stats_pg_cte,
            "speedup_bfs_over_postgres": round(speedup_vs_bfs, 2),
            "speedup_graphlookup_over_postgres": round(speedup_vs_gl, 2),
        }

    # -----------------------------------------------------------------------
    # Baseline Comparison: PostgreSQL Raw 1-Hop Self-Join
    # -----------------------------------------------------------------------
    print("--- BASELINE: PostgreSQL Raw Unoptimized Self-Join on 1.85M Rows ---")
    raw_trials = min(10, trials)
    latencies_pg_raw = []
    with pg_conn.cursor() as cur:
        for acc in sample_accounts[:raw_trials]:
            t0 = time.perf_counter()
            cnt = query_pg_raw_join(cur, acc)
            latencies_pg_raw.append((time.perf_counter() - t0) * 1000)
    stats_pg_raw = calculate_stats(latencies_pg_raw)
    print(f"  [Postgres Raw Join (1.85M rows)]: Mean: {stats_pg_raw['mean_ms']:>7.2f} ms | p95: {stats_pg_raw['p95_ms']:>7.2f} ms")
    results["1_hop_raw_baseline"] = stats_pg_raw

    # -----------------------------------------------------------------------
    # Print Formatted Executive Comparison Table
    # -----------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("FINAL MULTI-HOP LATENCY BENCHMARK SUMMARY TABLE")
    print("=" * 92)
    print(f"{'Query Depth':<14} {'Engine / Implementation':<28} {'Mean (ms)':>12} {'p50 (ms)':>10} {'p95 (ms)':>10} {'Speedup':>12}")
    print("-" * 92)

    for k in hops:
        data = results[f"{k}_hop"]
        bfs = data["mongo_bfs"]
        gl = data["mongo_graph_lookup"]
        pg = data["postgres_cte"]

        hop_label = f"{k}-Hop"
        speed_bfs = f"{data['speedup_bfs_over_postgres']:.1f}x faster"
        speed_gl = f"{data['speedup_graphlookup_over_postgres']:.1f}x faster"

        print(f"{hop_label:<14} {'MongoDB Document BFS':<28} {bfs['mean_ms']:>12.2f} {bfs['p50_ms']:>10.2f} {bfs['p95_ms']:>10.2f} {speed_bfs:>12}")
        print(f"{'':<14} {'MongoDB $graphLookup':<28} {gl['mean_ms']:>12.2f} {gl['p50_ms']:>10.2f} {gl['p95_ms']:>10.2f} {speed_gl:>12}")
        print(f"{'':<14} {'PostgreSQL Relational CTE':<28} {pg['mean_ms']:>12.2f} {pg['p50_ms']:>10.2f} {pg['p95_ms']:>10.2f} {'Baseline':>12}")
        print("-" * 92)

    # Save output to JSON
    if output_file:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nDetailed latency metrics saved to: {output_file}")

    pg_conn.close()
    mongo_client.close()
    print("=" * 92)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-hop latency benchmark between PostgreSQL and MongoDB.")
    parser.add_argument("--trials", type=int, default=50, help="Number of trials per test (default: 50)")
    parser.add_argument("--hops", type=str, default="1,2,3", help="Comma-separated hop depths (default: '1,2,3')")
    parser.add_argument("--output", type=str, default="models/benchmark_results.json", help="Output JSON path")
    args = parser.parse_args()

    hop_list = [int(h.strip()) for h in args.hops.split(",") if h.strip()]
    run_benchmark(trials=args.trials, hops=hop_list, output_file=args.output)
