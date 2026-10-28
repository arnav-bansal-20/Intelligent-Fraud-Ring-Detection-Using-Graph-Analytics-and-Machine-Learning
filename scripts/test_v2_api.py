import urllib.request
import json

BASE_URL = "http://127.0.0.1:8005/api"

def make_req(path, method="GET", data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))

def test_all():
    print("=== Testing Intelligent Fraud Detection API v2 ===")

    # 1. Login as Analyst
    status, res = make_req("/auth/login", method="POST", data={"username": "analyst", "password": "password123"})
    assert status == 200, f"Login failed: {res}"
    analyst_token = res["access_token"]
    print("1. Analyst Login: SUCCESS -> Role:", res["user"]["role"])

    # 2. Login as Manager
    status, res = make_req("/auth/login", method="POST", data={"username": "manager", "password": "password123"})
    assert status == 200, f"Manager login failed: {res}"
    manager_token = res["access_token"]
    print("2. Manager Login: SUCCESS -> Role:", res["user"]["role"])

    # 3. RBAC Enforcement: Analyst trying to access Manager Dashboard -> Must be 403 Forbidden
    status, res = make_req("/dashboard/metrics", method="GET", token=analyst_token)
    assert status == 403, f"Expected 403 Forbidden for analyst on dashboard, got {status}"
    print("3. Role Enforcement: SUCCESS -> Analyst denied access to /dashboard/metrics (403 Forbidden)")

    # 4. Manager accessing Dashboard -> Must be 200 OK
    status, res = make_req("/dashboard/metrics", method="GET", token=manager_token)
    assert status == 200, f"Dashboard metrics failed: {res}"
    print("4. Manager Dashboard Access: SUCCESS -> Open Alerts:", res["open_alerts"], "| Precision:", res["model_metrics"]["precision"])

    # 5. Benchmarks endpoint
    status, res = make_req("/dashboard/benchmarks", method="GET", token=manager_token)
    assert status == 200
    print("5. Traversal Benchmarks: SUCCESS -> 1-Hop Speedup:", res[0]["speedup"])

    # 6. Score a transaction (POST /score)
    score_payload = {
        "account_id": 787,
        "merchant_id": 1,
        "amount": 950.00,
        "save_alert": True
    }
    status, res = make_req("/score", method="POST", data=score_payload, token=analyst_token)
    assert status == 200, f"Scoring failed: {res}"
    print("6. Transaction Scoring: SUCCESS -> Fraud Prob:", res["fraud_probability"], "| Risk Label:", res["risk_label"])
    print("   Top Reasons:")
    for r in res["top_reasons"]:
        print(f"     - [{r['contribution_level']}] {r['description']}")

    # 7. List Alerts
    status, res = make_req("/alerts?limit=5", method="GET", token=analyst_token)
    assert status == 200
    first_alert = res[0]
    print(f"7. Alerts Feed: SUCCESS -> Fetched {len(res)} alerts. First Alert #{first_alert['alert_id']}: {first_alert['customer_name']} | Status: {first_alert['status']}")

    # 8. Review Alert (PATCH /alerts/{id})
    review_payload = {
        "status": "reviewing",
        "decision": "Syndicate Investigation In Progress",
        "note": "Corroborated with multi-hop same-merchant graph. High risk confirmed."
    }
    status, res = make_req(f"/alerts/{first_alert['alert_id']}", method="PATCH", data=review_payload, token=analyst_token)
    assert status == 200
    print(f"8. Review Alert: SUCCESS -> Updated Alert #{first_alert['alert_id']} status to '{res['status']}'")

    # 9. Audit History
    status, res = make_req(f"/alerts/{first_alert['alert_id']}/audit", method="GET", token=analyst_token)
    assert status == 200
    print(f"9. Audit Trail: SUCCESS -> Found {len(res)} audit events for Alert #{first_alert['alert_id']}")

    # 10. Ring Explorer
    status, res = make_req("/rings/1?hops=2", method="GET", token=analyst_token)
    assert status == 200
    print(f"10. Ring Explorer: SUCCESS -> Center Acc #{res['center_account_id']}, Raw Degree: {res['raw_neighborhood_degree']}, Capped Nodes: {res['capped_nodes_count']}, Edges: {len(res['edges'])}")

    print("\n=== ALL 10/10 BACKEND INTEGRATION TESTS PASSED PERFECTLY ===")

if __name__ == "__main__":
    test_all()

