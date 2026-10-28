#!/usr/bin/env python3
"""
Step 5: Multi-Hop Traversal Benchmark
Compares the performance of finding all accounts connected within k hops
(via shared devices and shared IPs) using:
  1) MongoDB Graph Traversal ($graphLookup / Adjacency List)
  2) PostgreSQL Recursive Common Table Expression (CTE) Multi-Table Join
Measures latencies across k=1, 2, 3 hops over multiple trials.
"""

import os
import sys
import time
import argparse
import logging
import statistics
import psycopg2
from pymongo import MongoClient

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

def query_postgres_recursive_cte(cur, start_account_id: int, k_hops: int):
    """
    Find accounts connected within k hops using PostgreSQL Recursive CTE.
    Traverses shared device and IP connections between accounts.
    """
    sql = """
    WITH RECURSIVE account_traversal AS (
        -- Anchor member: starting account at depth 0
        SELECT %s::int AS account_id, 0 AS depth
        UNION
        -- Recursive member: traverse via shared device or IP
        SELECT DISTINCT t_other.account_id, at.depth + 1
        FROM account_traversal at
        JOIN transaction t_curr ON t_curr.account_id = at.account_id
        JOIN transaction t_other ON (
            (t_other.device_id = t_curr.device_id AND t_curr.device_id IS NOT NULL)
            OR
            (t_other.ip_id = t_curr.ip_id AND t_curr.ip_id IS NOT NULL)
        )
        WHERE at.depth < %s
          AND t_other.account_id <> at.account_id
    )
    SELECT DISTINCT account_id, MIN(depth) as min_depth
    FROM account_traversal
    WHERE depth > 0
    GROUP BY account_id;
    """
    cur.execute(sql, (start_account_id, k_hops))
    rows = cur.fetchall()
    return set(r[0] for r in rows)

def query_mongodb_graph_lookup(db, start_account_id: int, k_hops: int):
    """
    Find accounts connected within k hops using MongoDB $graphLookup aggregation.
    """
    pipeline = [
        {"$match": {"account_id": start_account_id}},
        {
            "$graphLookup": {
                "from": "account_graph",
                "startWith": "$linked_accounts",
                "connectFromField": "linked_accounts",
                "connectToField": "account_id",
                "as": "connected_network",
                "maxDepth": k_hops - 1,
                "depthField": "hops"
            }
        },
        {
            "$project": {
                "connected_accounts": "$connected_network.account_id"
            }
        }
    ]
    res = list(db["account_graph"].aggregate(pipeline))
    if res and "connected_accounts" in res[0]:
        return set(res[0]["connected_accounts"])
    return set()

def run_benchmark(trials: int = 15, test_accounts = None):
    db = get_mongo_db()
    conn = get_pg_connection()
    cur = conn.cursor()

    # If test accounts not provided, select accounts that have connected rings
    if not test_accounts:
        connected_docs = list(db["account_graph"].find({"degree": {"$gt": 0}}).limit(10))
        test_accounts = [d["account_id"] for d in connected_docs]
        if not test_accounts:
            test_accounts = [1, 2, 3]

    print("\n" + "="*80)
    print("BENCHMARK: MongoDB Graph Traversal vs PostgreSQL Recursive CTE Join")
    print(f"Sample test accounts: {test_accounts} | Iterations per test: {trials}")
    print("="*80)

    results = []

    for k in [1, 2, 3]:
        pg_times = []
        mongo_times = []
        discovered_counts = []

        # Warm-up run
        for acc in test_accounts[:2]:
            _ = query_postgres_recursive_cte(cur, acc, k)
            _ = query_mongodb_graph_lookup(db, acc, k)

        for acc in test_accounts:
            for _ in range(trials):
                # Benchmark PostgreSQL
                t0 = time.perf_counter()
                pg_accounts = query_postgres_recursive_cte(cur, acc, k)
                t1 = time.perf_counter()
                pg_times.append((t1 - t0) * 1000)  # ms

                # Benchmark MongoDB
                t0 = time.perf_counter()
                mongo_accounts = query_mongodb_graph_lookup(db, acc, k)
                t1 = time.perf_counter()
                mongo_times.append((t1 - t0) * 1000)  # ms

                discovered_counts.append(len(mongo_accounts))

        mean_pg = statistics.mean(pg_times)
        median_pg = statistics.median(pg_times)
        p95_pg = sorted(pg_times)[int(len(pg_times) * 0.95)]

        mean_mongo = statistics.mean(mongo_times)
        median_mongo = statistics.median(mongo_times)
        p95_mongo = sorted(mongo_times)[int(len(mongo_times) * 0.95)]

        speedup = mean_pg / mean_mongo if mean_mongo > 0 else 1.0

        results.append({
            "hops": k,
            "avg_discovered": statistics.mean(discovered_counts),
            "pg_mean": mean_pg,
            "pg_p95": p95_pg,
            "mongo_mean": mean_mongo,
            "mongo_p95": p95_mongo,
            "speedup": speedup
        })

    print(f"{'Hops (k)':<10} | {'Discovered Nodes':<18} | {'PostgreSQL CTE (ms)':<22} | {'MongoDB $graph (ms)':<22} | {'Speedup':<10}")
    print("-"*90)
    for r in results:
        pg_str = f"{r['pg_mean']:.2f} ms (p95: {r['pg_p95']:.2f})"
        mg_str = f"{r['mongo_mean']:.2f} ms (p95: {r['mongo_p95']:.2f})"
        sp_str = f"{r['speedup']:.1f}x"
        print(f"{r['hops']:<10} | {r['avg_discovered']:<18.1f} | {pg_str:<22} | {mg_str:<22} | {sp_str:<10}")
    print("="*90)

    cur.close()
    conn.close()
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Graph Traversal Benchmark")
    parser.add_argument("--trials", type=int, default=10, help="Number of trials per test account")
    args = parser.parse_args()

    run_benchmark(trials=args.trials)

