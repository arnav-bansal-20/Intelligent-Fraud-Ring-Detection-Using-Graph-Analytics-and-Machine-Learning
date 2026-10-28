from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Dict, Set
from backend.schemas import RingExplorerResponse, RingNode, RingEdge
from backend.auth import get_current_user
from backend.database import get_pg_connection, get_mongo_db

router = APIRouter(prefix="/rings", tags=["Ring Explorer"])

@router.get("/{account_id}", response_model=RingExplorerResponse)
def get_account_ring(
    account_id: int,
    hops: int = Query(1, ge=1, le=3, description="Graph traversal depth (1 to 3 hops)"),
    current_user: dict = Depends(get_current_user)
):
    """
    Explore the coordinated fraud ring around an account.
    Returns connected accounts from MongoDB account_graph, capped to fraud-flagged accounts
    or the top 25 neighbors by shared merchants (since full average degree is ~835).
    """
    mongo = get_mongo_db()
    conn = get_pg_connection()
    cur = conn.cursor()

    # 1. Fetch known fraud accounts from PostgreSQL
    cur.execute("SELECT DISTINCT account_id FROM transaction WHERE is_fraud = true;")
    fraud_accounts = set(r["account_id"] for r in cur.fetchall())

    # 2. Fetch center account from MongoDB
    center_doc = mongo.account_graph.find_one({"account_id": account_id})
    if not center_doc:
        cur.close()
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account #{account_id} not found in graph database."
        )

    all_raw_neighbors = center_doc.get("neighbors", [])
    raw_degree = center_doc.get("degree", len(all_raw_neighbors))

    # 3. Apply Capping Rule:
    # Separate fraud-flagged peers and sort remainder by shared_merchant_count descending.
    # Cap to top fraud accounts and top shared merchant neighbors (approx 25-35 nodes total)
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

    for n in selected_1hop:
        nid = n.get("account_id")
        selected_account_ids.add(nid)
        edge_key = f"{min(account_id, nid)}_{max(account_id, nid)}"
        edge_map[edge_key] = {
            "source": f"acc_{account_id}",
            "target": f"acc_{nid}",
            "shared_merchants": n.get("shared_merchant_count", 1)
        }

    # 4. Multi-hop expansion (hops=2 or 3) if requested
    if hops >= 2:
        secondary_ids = list(selected_account_ids - {account_id})[:10]  # sample top 10 to expand
        secondary_cursor = mongo.account_graph.find({"account_id": {"$in": secondary_ids}})
        for sec_doc in secondary_cursor:
            sec_acc = sec_doc.get("account_id")
            sec_neighbors = sec_doc.get("neighbors", [])
            # Priority: fraud neighbors first
            sec_fraud = [sn for sn in sec_neighbors if sn.get("account_id") in fraud_accounts][:5]
            sec_top = sorted(sec_neighbors, key=lambda x: x.get("shared_merchant_count", 0), reverse=True)[:5]
            for sn in (sec_fraud + sec_top):
                sn_id = sn.get("account_id")
                if len(selected_account_ids) < 45:  # safe upper bound for UI responsiveness
                    selected_account_ids.add(sn_id)
                    edge_key = f"{min(sec_acc, sn_id)}_{max(sec_acc, sn_id)}"
                    if edge_key not in edge_map:
                        edge_map[edge_key] = {
                            "source": f"acc_{sec_acc}",
                            "target": f"acc_{sn_id}",
                            "shared_merchants": sn.get("shared_merchant_count", 1)
                        }

    # 5. Enrich account nodes with PostgreSQL relational data
    id_list = list(selected_account_ids)
    cur.execute("""
        SELECT
            a.account_id,
            'ACC-' || LPAD(a.account_id::text, 6, '0') AS account_number,
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
    conn.close()

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
        density_note=(
            "Dense Graph Optimization: Average node degree across 1.85M transactions is ~835. "
            "To provide immediate visual clarity for fraud analysts, this view is capped to fraud-flagged "
            "accounts and the top 25 neighbors by shared merchants."
        )
    )
