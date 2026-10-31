"""
Shared Feature Construction Module for Training and Serving.
Guarantees identical feature semantics across offline evaluation and online API inference:
- hops_to_flagged: 0 (account itself is flagged for confirmed fraud),
                   1 (adjacent to a confirmed fraud node),
                   2 (two hops away from a confirmed fraud node),
                   3 (3 or more hops, or disconnected from confirmed fraud nodes).
- degree_centrality: degree / (total_accounts - 1), normalized by real account count.
- shared_merchant_count_24h: distinct other accounts trading at the same merchant in past 24h.
- trans_velocity_24h: transaction count by the account in past 24h.
- prior_fraud_neighbors_count: 1-hop neighbors confirmed for fraud.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Set, Tuple, Optional
import numpy as np

# Cache for total account count to avoid re-querying on every request
_cached_account_count: Optional[int] = None

def get_total_account_count(cur=None, mongo=None) -> int:
    """Returns the total number of accounts in the network."""
    global _cached_account_count
    if _cached_account_count is not None and _cached_account_count > 0:
        return _cached_account_count

    if cur is not None:
        try:
            cur.execute("SELECT COUNT(*) as cnt FROM account;")
            row = cur.fetchone()
            if row and row["cnt"]:
                _cached_account_count = int(row["cnt"])
                return _cached_account_count
        except Exception:
            pass

    if mongo is not None:
        try:
            cnt = mongo.account_graph.count_documents({})
            if cnt > 0:
                _cached_account_count = cnt
                return _cached_account_count
        except Exception:
            pass

    return 1000  # Fallback default if DB not ready


def compute_transaction_features(
    account_id: int,
    merchant_id: int,
    amount: float,
    dt: datetime,
    cur,
    mongo,
    fraud_accounts: Set[int],
    total_accounts: Optional[int] = None
) -> Dict[str, float]:
    """
    Constructs the exact feature dictionary for online scoring and offline evaluation.
    Documentation:
      hops_to_flagged = 3 indicates "3 or more hops away, or disconnected".
      degree_centrality uses the real total account count in the network.
    """
    if total_accounts is None:
        total_accounts = get_total_account_count(cur, mongo)

    hour = dt.hour
    day_of_week = dt.weekday()

    # 1. MongoDB Account Graph lookup
    acc_doc = mongo.account_graph.find_one({"account_id": account_id})
    neighbors = acc_doc.get("neighbors", []) if acc_doc else []
    degree = acc_doc.get("degree", len(neighbors)) if acc_doc else 0

    norm_denominator = max(float(total_accounts - 1), 1.0)
    degree_centrality = float(degree) / norm_denominator

    # 2. Prior fraud neighbors (1-hop)
    prior_fraud_neighbors_count = sum(1 for n in neighbors if n.get("account_id") in fraud_accounts)

    # 3. Shortest hops to flagged confirmed fraud accounts
    # 0 = self flagged, 1 = 1-hop neighbor flagged, 2 = 2-hop neighbor flagged, 3 = 3+ hops or unconnected
    if account_id in fraud_accounts:
        hops_to_flagged = 0.0
    elif prior_fraud_neighbors_count > 0:
        hops_to_flagged = 1.0
    else:
        # Check 2-hop neighbors (capped to 50 for low latency)
        neighbor_ids = [n.get("account_id") for n in neighbors[:50]]
        two_hop_flagged = mongo.account_graph.count_documents({
            "account_id": {"$in": neighbor_ids},
            "neighbors.account_id": {"$in": list(fraud_accounts)}
        }) if neighbor_ids else 0
        hops_to_flagged = 2.0 if two_hop_flagged > 0 else 3.0

    # 4. Account velocity in past 24h from PostgreSQL
    iso_time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        SELECT COUNT(*) as velocity
        FROM transaction
        WHERE account_id = %s
          AND txn_timestamp BETWEEN (%s::timestamp - interval '24 hours') AND %s::timestamp;
    """, (account_id, iso_time_str, iso_time_str))
    vel_row = cur.fetchone()
    trans_velocity_24h = float(vel_row["velocity"]) if vel_row and vel_row["velocity"] else 0.0

    # 5. Shared merchant distinct other accounts in past 24h
    cur.execute("""
        SELECT COUNT(DISTINCT account_id) as shared_cnt
        FROM transaction
        WHERE merchant_id = %s
          AND txn_timestamp BETWEEN (%s::timestamp - interval '24 hours') AND %s::timestamp
          AND account_id <> %s;
    """, (merchant_id, iso_time_str, iso_time_str, account_id))
    merch_row = cur.fetchone()
    shared_merchant_count_24h = float(merch_row["shared_cnt"]) if merch_row and merch_row["shared_cnt"] else 0.0

    return {
        "amount": float(amount),
        "hour": int(hour),
        "day_of_week": int(day_of_week),
        "hops_to_flagged": float(hops_to_flagged),
        "degree_centrality": float(degree_centrality),
        "shared_merchant_count_24h": float(shared_merchant_count_24h),
        "trans_velocity_24h": float(trans_velocity_24h),
        "prior_fraud_neighbors_count": float(prior_fraud_neighbors_count)
    }

