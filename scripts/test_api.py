#!/usr/bin/env python3
"""
Integration test script for FastAPI backend.
"""

import urllib.request
import json
import time

BASE_URL = "http://127.0.0.1:8005"

def test_api():
    print(f"Testing API at {BASE_URL}...")

    # 1. Health
    req = urllib.request.urlopen(f"{BASE_URL}/api/health")
    data = json.loads(req.read().decode())
    print("1. Health Check:", json.dumps(data, indent=2))
    assert data["status"] == "healthy"

    # 2. Stats
    req = urllib.request.urlopen(f"{BASE_URL}/api/stats")
    stats = json.loads(req.read().decode())
    print("\n2. System Stats:", json.dumps(stats, indent=2))
    assert stats["total_transactions"] >= 50000

    # 3. Alerts
    req = urllib.request.urlopen(f"{BASE_URL}/api/alerts?limit=3")
    alerts = json.loads(req.read().decode())
    print(f"\n3. Alerts Feed (Found {len(alerts)} alerts):")
    for a in alerts:
        print(f"   - Alert #{a['alert_id']}: Score={a['risk_score']} | Customer={a['customer_name']} | Amt=${a['amt']}")

    # 4. Lookup score of first alert transaction
    first_trans_num = alerts[0]["trans_num"]
    req = urllib.request.urlopen(f"{BASE_URL}/api/transactions/{first_trans_num}/score")
    score_data = json.loads(req.read().decode())
    print(f"\n4. Fraud Score Lookup ({first_trans_num}):")
    print(f"   Risk Score: {score_data['risk_score']} | Hops to Flagged: {score_data['hops_to_nearest_flagged']} | Shared Devs: {score_data['shared_device_count']}")

    # 5. Graph ring exploration
    center_acc = alerts[0]["account_id"]
    req = urllib.request.urlopen(f"{BASE_URL}/api/graph/ring/{center_acc}?hops=2")
    graph_data = json.loads(req.read().decode())
    print(f"\n5. Graph Ring for Account #{center_acc}:")
    print(f"   Ring Size: {graph_data['ring_size']} accounts | Total Nodes: {graph_data['total_nodes']} | Total Edges: {graph_data['total_edges']}")

    # 6. Test Ingesting a new transaction
    payload = {
        "trans_num": f"test_trans_{int(time.time())}",
        "account_id": center_acc,
        "merchant_id": 1,
        "amt": 850.50,
        "device_fingerprint": "DEV-test-device-fingerprint-001",
        "ip_str": "10.45.67.89",
        "unix_time": int(time.time())
    }
    req = urllib.request.Request(
        f"{BASE_URL}/api/transactions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    res = urllib.request.urlopen(req)
    ingest_res = json.loads(res.read().decode())
    print("\n6. Real-Time Transaction Ingestion Test:")
    print(f"   Status: {ingest_res['status']} | Trans ID: {ingest_res['transaction_id']} | Risk Score: {ingest_res['risk_score']} | Alert: {ingest_res['alert_triggered']}")

    print("\n" + "="*50)
    print("ALL API INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("="*50)

if __name__ == "__main__":
    test_api()

