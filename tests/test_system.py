import os
import json
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

# 1. Schemas Import Test
def test_schemas_import():
    """Verify that backend.schemas imports cleanly without NameError or forward-reference errors."""
    import backend.schemas as schemas
    assert hasattr(schemas, "FeatureReason")
    assert hasattr(schemas, "CompanyTransactionItem")
    assert hasattr(schemas, "DashboardMetricsResponse")
    assert hasattr(schemas, "ModelMetrics")

    # Instantiate to verify model validation
    reason = schemas.FeatureReason(
        feature="hops_to_flagged",
        description="Direct link",
        value=1.0,
        contribution_level="Critical"
    )
    assert reason.feature == "hops_to_flagged"

    tx_item = schemas.CompanyTransactionItem(
        transaction_id=1,
        trans_num="tx_123",
        account_id=10,
        customer_name="Test Customer",
        merchant_id=5,
        merchant_name="Test Store",
        amount=100.0,
        txn_timestamp="2026-10-31 12:00:00",
        fraud_probability=0.05,
        risk_label="Low",
        is_fraud=False,
        top_reasons=[reason],
        created_at="2026-10-31 12:00:00"
    )
    assert tx_item.amount == 100.0


# 2. Role Enforcement Test
def test_role_enforcement():
    """Verify 403 Forbidden for analyst on manager dashboard and on clear company transactions."""
    from backend.main import app
    from backend.auth import create_access_token

    client = TestClient(app)
    analyst_token = create_access_token({"sub": "analyst", "analyst_id": 1, "role": "analyst"})

    # Dashboard metrics: manager/admin only -> 403 for analyst
    resp_dash = client.get(
        "/api/dashboard/metrics",
        headers={"Authorization": f"Bearer {analyst_token}"}
    )
    assert resp_dash.status_code == 403, f"Expected 403 for analyst on dashboard, got {resp_dash.status_code}"

    # Clear transactions: admin only -> 403 for analyst
    resp_clear = client.delete(
        "/api/transactions/clear",
        headers={"Authorization": f"Bearer {analyst_token}"}
    )
    assert resp_clear.status_code == 403, f"Expected 403 for analyst on /clear, got {resp_clear.status_code}"


# 3. Feature Function Test
def test_feature_function():
    """Verify feature construction logic, documentation, and valid bounds."""
    from backend.features import compute_transaction_features
    from backend.database import get_pg_connection, get_mongo_db, get_known_fraud_accounts

    conn = get_pg_connection()
    cur = conn.cursor()
    mongo = get_mongo_db()

    fraud_accounts = get_known_fraud_accounts(cur)
    dt = datetime(2020, 10, 15, 14, 30, 0, tzinfo=timezone.utc)

    features = compute_transaction_features(
        account_id=1,
        merchant_id=1,
        amount=250.0,
        dt=dt,
        cur=cur,
        mongo=mongo,
        fraud_accounts=fraud_accounts,
        total_accounts=1004
    )

    cur.close()
    conn.close()

    expected_keys = [
        "amount", "hour", "day_of_week", "hops_to_flagged",
        "degree_centrality", "shared_merchant_count_24h",
        "trans_velocity_24h", "prior_fraud_neighbors_count"
    ]
    for key in expected_keys:
        assert key in features, f"Missing key {key} in feature dict"

    assert features["amount"] == 250.0
    assert features["hour"] == 14
    assert 0.0 <= features["hops_to_flagged"] <= 3.0
    assert 0.0 <= features["degree_centrality"] <= 1.0


# 4. Alert Review Writing Exactly One Audit Record Test
def test_alert_review_audit_record():
    """Verify alert review writes exactly one audit record via trigger."""
    from backend.main import app
    from backend.auth import create_access_token
    from backend.database import get_pg_connection

    client = TestClient(app)
    analyst_token = create_access_token({"sub": "analyst", "analyst_id": 1, "role": "analyst"})

    conn = get_pg_connection()
    cur = conn.cursor()

    # Find or create an open alert
    cur.execute("SELECT alert_id FROM alert WHERE status = 'open' LIMIT 1;")
    row = cur.fetchone()
    if not row:
        # Create a test alert
        cur.execute("SELECT transaction_id FROM transaction LIMIT 1;")
        tx_id = cur.fetchone()["transaction_id"]
        cur.execute("""
            INSERT INTO alert (transaction_id, analyst_id, fraud_probability, risk_label, status, note)
            VALUES (%s, 1, 0.98, 'High', 'open', 'Test alert')
            ON CONFLICT (transaction_id) DO UPDATE SET status = 'open'
            RETURNING alert_id;
        """, (tx_id,))
        alert_id = cur.fetchone()["alert_id"]
        conn.commit()
    else:
        alert_id = row["alert_id"]

    # Count audit records before
    cur.execute("SELECT COUNT(*) as cnt FROM alert_audit WHERE alert_id = %s;", (alert_id,))
    count_before = cur.fetchone()["cnt"]

    # Perform review PATCH
    patch_res = client.patch(
        f"/api/alerts/{alert_id}",
        json={
            "status": "reviewing",
            "decision": "Investigating syndicate pattern",
            "note": f"Audited note update at {datetime.now().isoformat()}"
        },
        headers={"Authorization": f"Bearer {analyst_token}"}
    )
    assert patch_res.status_code == 200, f"Review failed: {patch_res.text}"

    # Count audit records after
    cur.execute("SELECT COUNT(*) as cnt FROM alert_audit WHERE alert_id = %s;", (alert_id,))
    count_after = cur.fetchone()["cnt"]

    cur.close()
    conn.close()

    assert count_after == count_before + 1, f"Expected exactly 1 audit record written, got {count_after - count_before}"


# 5. Dashboard Values Equalling metrics.json Test
def test_dashboard_metrics_match_json():
    """Verify /api/dashboard/metrics numbers equal models/metrics.json for deployed Model B."""
    from backend.main import app
    from backend.auth import create_access_token

    client = TestClient(app)
    manager_token = create_access_token({"sub": "manager", "analyst_id": 2, "role": "manager"})

    resp = client.get(
        "/api/dashboard/metrics",
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert resp.status_code == 200, f"Dashboard metrics call failed: {resp.text}"
    api_model = resp.json()["model_metrics"]

    metrics_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "metrics.json"))
    with open(metrics_path, "r") as f:
        metrics_json = json.load(f)
    target = metrics_json["Model B"]

    assert api_model["precision"] == target["precision"]
    assert api_model["recall"] == target["recall"]
    assert api_model["f1_score"] == target["f1"]
    assert api_model["pr_auc"] == target["pr_auc"]
    assert api_model["roc_auc"] == target["roc_auc"]
    assert api_model["threshold"] == target["threshold"]


# 6. CSV File Upload Test
def test_csv_upload_endpoint():
    """Verify that uploading a CSV file to /api/transactions/upload-csv parses and scores records."""
    from backend.main import app
    from backend.auth import create_access_token

    client = TestClient(app)
    analyst_token = create_access_token({"sub": "analyst", "analyst_id": 1, "role": "analyst"})

    csv_data = (
        "account_number,customer_name,merchant_name,amount,timestamp,notes\n"
        "ACC-CSV-TEST-1,Alpha Corp,SuperMart,125.00,2026-10-31T12:00:00,Supply purchase\n"
        "ACC-CSV-TEST-2,Beta LLC,TechHub,1800.00,2026-10-31T12:05:00,Hardware buy\n"
    )

    resp = client.post(
        "/api/transactions/upload-csv",
        files={"file": ("test_run.csv", csv_data.encode("utf-8"), "text/csv")},
        headers={"Authorization": f"Bearer {analyst_token}"}
    )
    assert resp.status_code == 200, f"CSV upload failed: {resp.text}"
    data = resp.json()
    assert data["total_ingested"] == 2
    assert len(data["results"]) == 2
    assert data["results"][0]["account_number"] == "ACC-CSV-TEST-1"
    assert data["results"][1]["account_number"] == "ACC-CSV-TEST-2"


