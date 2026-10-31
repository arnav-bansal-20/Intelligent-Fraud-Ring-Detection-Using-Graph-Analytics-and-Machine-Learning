from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Dict, Set
from backend.schemas import RingExplorerResponse, RingNode, RingEdge
from backend.auth import get_current_user
from backend.database import get_db, get_mongo_db, get_known_fraud_accounts

router = APIRouter(prefix="/rings", tags=["Ring Explorer"])

@router.get("/{account_id}", response_model=RingExplorerResponse)
def get_account_ring(
    account_id: int,
    hops: int = Query(1, ge=1, le=3, description="Graph traversal depth (1 to 3 hops)"),
    conn = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Explore the coordinated fraud ring around an account.
    Returns connected accounts from MongoDB account_graph, capped to fraud-flagged accounts
    or top neighbors by shared merchants (since average degree is about 835 across 999 accounts).
    """
    mongo = get_mongo_db()
    cur = conn.cursor()

    # 1. Fetch known fraud accounts from cached set
    fraud_accounts = get_known_fraud_accounts(cur)

    # 2. Fetch center account from MongoDB (or construct from PG if new company account)
    center_doc = mongo.account_graph.find_one({"account_id": account_id})
    if not center_doc:
        # Check if account exists in PostgreSQL
        cur.execute("""
            SELECT a.account_id, a.account_number, c.first_name, c.last_name
            FROM account a
            JOIN customer c ON c.customer_id = a.customer_id
            WHERE a.account_id = %s;
        """, (account_id,))
        acc_info = cur.fetchone()
        if not acc_info:
            cur.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Account #{account_id} not found."
            )
        # Find related merchants and neighboring accounts
        cur.execute("""
            SELECT DISTINCT merchant_id FROM transaction WHERE account_id = %s;
        """, (account_id,))
        merch_ids = [r["merchant_id"] for r in cur.fetchall()]
        neighbors = []
        if merch_ids:
            cur.execute("""
                SELECT account_id, COUNT(DISTINCT merchant_id) as shared_cnt
                FROM transaction
                WHERE merchant_id = ANY(%s) AND account_id <> %s
                GROUP BY account_id
                ORDER BY shared_cnt DESC
                LIMIT 30;
            """, (merch_ids, account_id))
            neighbors = [{"account_id": r["account_id"], "shared_merchant_count": r["shared_cnt"]} for r in cur.fetchall()]
        center_doc = {
            "account_id": account_id,
            "degree": len(neighbors),
            "neighbors": neighbors
        }

    all_raw_neighbors = center_doc.get("neighbors", [])
    raw_degree = center_doc.get("degree", len(all_raw_neighbors))

    # 3. Apply Capping Rule for Hop 1:
    # Separate fraud-flagged peers and sort remainder by shared_merchant_count descending.
    fraud_peers_all = [n for n in all_raw_neighbors if n.get("account_id") in fraud_accounts]
    sorted_fraud = sorted(fraud_peers_all, key=lambda x: x.get("shared_merchant_count", 0), reverse=True)
    fraud_peers = sorted_fraud[:20]

    sorted_by_merchants = sorted(
        [n for n in all_raw_neighbors if n.get("account_id") not in fraud_accounts],
        key=lambda x: x.get("shared_merchant_count", 0),
        reverse=True
    )
    top_merchant_peers = sorted_by_merchants[:10]

    # Combine: Top fraud peers + top non-fraud merchant peers
    selected_1hop = fraud_peers + top_merchant_peers
    selected_account_ids: Set[int] = {account_id}
    edge_map: Dict[str, dict] = {}

    hop1_ids = set()
    for n in selected_1hop:
        nid = n.get("account_id")
        selected_account_ids.add(nid)
        hop1_ids.add(nid)
        edge_key = f"{min(account_id, nid)}_{max(account_id, nid)}"
        edge_map[edge_key] = {
            "source": f"acc_{account_id}",
            "target": f"acc_{nid}",
            "shared_merchants": n.get("shared_merchant_count", 1)
        }

    # 4. Multi-hop expansion: Hop 2
    hop2_ids = set()
    if hops >= 2:
        sec_sample = list(hop1_ids)[:10]  # sample up to 10 from hop 1
        secondary_cursor = mongo.account_graph.find({"account_id": {"$in": sec_sample}})
        for sec_doc in secondary_cursor:
            sec_acc = sec_doc.get("account_id")
            sec_neighbors = sec_doc.get("neighbors", [])
            sec_fraud = [sn for sn in sec_neighbors if sn.get("account_id") in fraud_accounts][:5]
            sec_top = sorted(sec_neighbors, key=lambda x: x.get("shared_merchant_count", 0), reverse=True)[:5]
            for sn in (sec_fraud + sec_top):
                sn_id = sn.get("account_id")
                if len(selected_account_ids) < 45:
                    selected_account_ids.add(sn_id)
                    hop2_ids.add(sn_id)
                    edge_key = f"{min(sec_acc, sn_id)}_{max(sec_acc, sn_id)}"
                    if edge_key not in edge_map:
                        edge_map[edge_key] = {
                            "source": f"acc_{sec_acc}",
                            "target": f"acc_{sn_id}",
                            "shared_merchants": sn.get("shared_merchant_count", 1)
                        }

    # Multi-hop expansion: Hop 3
    if hops >= 3 and hop2_ids:
        tert_sample = list(hop2_ids - hop1_ids - {account_id})[:8]
        tertiary_cursor = mongo.account_graph.find({"account_id": {"$in": tert_sample}})
        for tert_doc in tertiary_cursor:
            tert_acc = tert_doc.get("account_id")
            tert_neighbors = tert_doc.get("neighbors", [])
            tert_fraud = [tn for tn in tert_neighbors if tn.get("account_id") in fraud_accounts][:4]
            tert_top = sorted(tert_neighbors, key=lambda x: x.get("shared_merchant_count", 0), reverse=True)[:4]
            for tn in (tert_fraud + tert_top):
                tn_id = tn.get("account_id")
                if len(selected_account_ids) < 45:
                    selected_account_ids.add(tn_id)
                    edge_key = f"{min(tert_acc, tn_id)}_{max(tert_acc, tn_id)}"
                    if edge_key not in edge_map:
                        edge_map[edge_key] = {
                            "source": f"acc_{tert_acc}",
                            "target": f"acc_{tn_id}",
                            "shared_merchants": tn.get("shared_merchant_count", 1)
                        }

    # 5. Enrich account nodes with PostgreSQL relational data using real account_number
    id_list = list(selected_account_ids)
    cur.execute("""
        SELECT
            a.account_id,
            COALESCE(a.account_number, 'ACC-' || LPAD(a.account_id::text, 6, '0')) AS account_number,
            c.first_name || ' ' || c.last_name AS customer_name,
            c.city || ', ' || c.state AS city_state
        FROM account a
        JOIN customer c ON c.customer_id = a.customer_id
        WHERE a.account_id = ANY(%s);
    """, (id_list,))
    customer_rows = {r["account_id"]: r for r in cur.fetchall()}

    # Also fetch degree from MongoDB for all selected nodes
    degrees_cursor = mongo.account_graph.find(
        {"account_id": {"$in": id_list}},
        {"account_id": 1, "degree": 1}
    )
    degree_lookup = {d["account_id"]: d.get("degree", 0) for d in degrees_cursor}

    # Shared merchant count map with center
    shared_with_center = {n.get("account_id"): n.get("shared_merchant_count", 0) for n in all_raw_neighbors}

    cur.close()

    # 6. Build Cytoscape-compatible Node and Edge payloads
    nodes: List[RingNode] = []
    for aid in selected_account_ids:
        cust = customer_rows.get(aid, {})
        is_fraud = aid in fraud_accounts
        is_center = (aid == account_id)

        if is_center:
            risk_level = "Investigated Account"
        elif is_fraud:
            risk_level = "Confirmed Fraud Syndicate"
        else:
            risk_level = "High-Traffic Merchant Peer"

        nodes.append(RingNode(
            id=f"acc_{aid}",
            account_id=aid,
            label=f"Acc #{aid}: {cust.get('customer_name', 'Customer')}",
            customer_name=cust.get("customer_name"),
            account_number=cust.get("account_number"),
            is_center=is_center,
            is_fraud=is_fraud,
            degree=degree_lookup.get(aid, 0),
            shared_merchants_with_center=shared_with_center.get(aid, 0),
            risk_level=risk_level
        ))

    edges: List[RingEdge] = []
    for edge_id, edge in edge_map.items():
        edges.append(RingEdge(
            id=f"edge_{edge_id}",
            source=edge["source"],
            target=edge["target"],
            shared_merchant_count=edge["shared_merchants"],
            label=f"{edge['shared_merchants']} shared merchants"
        ))

    return RingExplorerResponse(
        center_account_id=account_id,
        hops=hops,
        raw_neighborhood_degree=raw_degree,
        capped_nodes_count=len(nodes),
        nodes=nodes,
        edges=edges,
        density_note="Dense Graph Optimization: average degree about 835 across 999 accounts. To provide visual clarity for fraud analysts, this view is capped to fraud-flagged accounts and top neighbors by shared merchants."
    )
