from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from backend.schemas import AlertListItem, AlertReviewRequest, AlertAuditItem
from backend.auth import get_current_user, require_roles
from backend.database import get_pg_connection

router = APIRouter(prefix="/alerts", tags=["Alert Queue"])

@router.get("", response_model=List[AlertListItem])
def get_alerts(
    status_filter: Optional[str] = Query(None, alias="status", pattern="^(open|reviewing|closed)$"),
    risk_label: Optional[str] = Query(None, pattern="^(Low|Medium|High)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """
    List alerts ordered by fraud probability and creation timestamp.
    Supports filtering by status (open, reviewing, closed) and risk label.
    Parameterised queries only.
    """
    conn = get_pg_connection()
    cur = conn.cursor()

    sql = """
        SELECT
            al.alert_id,
            al.transaction_id,
            t.account_id,
            c.first_name || ' ' || c.last_name AS customer_name,
            m.merchant_name,
            t.amount,
            t.txn_timestamp::text AS txn_timestamp,
            al.fraud_probability::float AS fraud_probability,
            al.risk_label,
            al.status,
            al.decision,
            al.note,
            an.username AS analyst_name,
            al.created_at::text AS created_at,
            al.updated_at::text AS updated_at
        FROM alert al
        JOIN transaction t ON t.transaction_id = al.transaction_id
        JOIN account a ON a.account_id = t.account_id
        JOIN customer c ON c.customer_id = a.customer_id
        JOIN merchant m ON m.merchant_id = t.merchant_id
        LEFT JOIN analyst an ON an.analyst_id = al.analyst_id
        WHERE 1=1
    """
    params = []
    if status_filter:
        sql += " AND al.status = %s"
        params.append(status_filter)
    if risk_label:
        sql += " AND al.risk_label = %s"
        params.append(risk_label)

    sql += " ORDER BY al.fraud_probability DESC, al.created_at DESC LIMIT %s OFFSET %s;"
    params.extend([limit, offset])

    cur.execute(sql, tuple(params))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [
        AlertListItem(
            alert_id=r["alert_id"],
            transaction_id=r["transaction_id"],
            account_id=r["account_id"],
            customer_name=r["customer_name"],
            merchant_name=r["merchant_name"],
            amount=float(r["amount"]),
            txn_timestamp=r["txn_timestamp"],
            fraud_probability=float(r["fraud_probability"]),
            risk_label=r["risk_label"],
            status=r["status"],
            decision=r["decision"],
            note=r["note"],
            analyst_name=r["analyst_name"],
            created_at=r["created_at"],
            updated_at=r["updated_at"]
        )
        for r in rows
    ]

@router.get("/{alert_id}", response_model=AlertListItem)
def get_alert_detail(alert_id: int, current_user: dict = Depends(get_current_user)):
    """Fetch detail for a single alert."""
    conn = get_pg_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            al.alert_id,
            al.transaction_id,
            t.account_id,
            c.first_name || ' ' || c.last_name AS customer_name,
            m.merchant_name,
            t.amount,
            t.txn_timestamp::text AS txn_timestamp,
            al.fraud_probability::float AS fraud_probability,
            al.risk_label,
            al.status,
            al.decision,
            al.note,
            an.username AS analyst_name,
            al.created_at::text AS created_at,
            al.updated_at::text AS updated_at
        FROM alert al
        JOIN transaction t ON t.transaction_id = al.transaction_id
        JOIN account a ON a.account_id = t.account_id
        JOIN customer c ON c.customer_id = a.customer_id
        JOIN merchant m ON m.merchant_id = t.merchant_id
        LEFT JOIN analyst an ON an.analyst_id = al.analyst_id
        WHERE al.alert_id = %s;
    """, (alert_id,))
    r = cur.fetchone()
    cur.close()
    conn.close()

    if not r:
        raise HTTPException(status_code=404, detail="Alert not found")

    return AlertListItem(
        alert_id=r["alert_id"],
        transaction_id=r["transaction_id"],
        account_id=r["account_id"],
        customer_name=r["customer_name"],
        merchant_name=r["merchant_name"],
        amount=float(r["amount"]),
        txn_timestamp=r["txn_timestamp"],
        fraud_probability=float(r["fraud_probability"]),
        risk_label=r["risk_label"],
        status=r["status"],
        decision=r["decision"],
        note=r["note"],
        analyst_name=r["analyst_name"],
        created_at=r["created_at"],
        updated_at=r["updated_at"]
    )

@router.patch("/{alert_id}", response_model=AlertListItem)
def review_alert(
    alert_id: int,
    body: AlertReviewRequest,
    current_user: dict = Depends(require_roles(["analyst", "manager", "admin"]))
):
    """
    Review an alert, record the analyst's decision and notes, and update status.
    Uses parameterized SQL and logs an entry in audit_log.
    The database trigger also maintains alert_audit.
    """
    conn = get_pg_connection()
    cur = conn.cursor()

    # 1. Fetch current alert state
    cur.execute("SELECT alert_id, status, decision, note FROM alert WHERE alert_id = %s;", (alert_id,))
    existing = cur.fetchone()
    if not existing:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Alert not found")

    # 2. Update alert in PostgreSQL
    cur.execute("""
        UPDATE alert
        SET status = %s,
            decision = %s,
            note = %s,
            analyst_id = %s,
            updated_at = NOW()
        WHERE alert_id = %s;
    """, (body.status, body.decision, body.note, current_user["analyst_id"], alert_id))

    # 3. Explicitly insert audit log entry
    cur.execute("""
        INSERT INTO audit_log (analyst_id, action, target_type, target_id, details)
        VALUES (%s, %s, %s, %s, %s);
    """, (
        current_user["analyst_id"],
        f"REVIEW_ALERT_{body.status.upper()}",
        "alert",
        alert_id,
        f"Status changed from '{existing['status']}' to '{body.status}'. Decision: '{body.decision}'. Note: '{body.note}'"
    ))
    conn.commit()

    # 4. Fetch updated row
    cur.execute("""
        SELECT
            al.alert_id,
            al.transaction_id,
            t.account_id,
            c.first_name || ' ' || c.last_name AS customer_name,
            m.merchant_name,
            t.amount,
            t.txn_timestamp::text AS txn_timestamp,
            al.fraud_probability::float AS fraud_probability,
            al.risk_label,
            al.status,
            al.decision,
            al.note,
            an.username AS analyst_name,
            al.created_at::text AS created_at,
            al.updated_at::text AS updated_at
        FROM alert al
        JOIN transaction t ON t.transaction_id = al.transaction_id
        JOIN account a ON a.account_id = t.account_id
        JOIN customer c ON c.customer_id = a.customer_id
        JOIN merchant m ON m.merchant_id = t.merchant_id
        LEFT JOIN analyst an ON an.analyst_id = al.analyst_id
        WHERE al.alert_id = %s;
    """, (alert_id,))
    r = cur.fetchone()
    cur.close()
    conn.close()

    return AlertListItem(
        alert_id=r["alert_id"],
        transaction_id=r["transaction_id"],
        account_id=r["account_id"],
        customer_name=r["customer_name"],
        merchant_name=r["merchant_name"],
        amount=float(r["amount"]),
        txn_timestamp=r["txn_timestamp"],
        fraud_probability=float(r["fraud_probability"]),
        risk_label=r["risk_label"],
        status=r["status"],
        decision=r["decision"],
        note=r["note"],
        analyst_name=r["analyst_name"],
        created_at=r["created_at"],
        updated_at=r["updated_at"]
    )

@router.get("/{alert_id}/audit", response_model=List[AlertAuditItem])
def get_alert_audit_history(alert_id: int, current_user: dict = Depends(get_current_user)):
    """Fetch audit history for an alert from PostgreSQL alert_audit table."""
    conn = get_pg_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            aa.audit_id,
            aa.alert_id,
            an.username AS changed_by_name,
            aa.old_status,
            aa.new_status,
            aa.old_decision,
            aa.new_decision,
            aa.changed_at::text AS changed_at
        FROM alert_audit aa
        LEFT JOIN analyst an ON an.analyst_id = aa.changed_by
        WHERE aa.alert_id = %s
        ORDER BY aa.changed_at DESC;
    """, (alert_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [
        AlertAuditItem(
            audit_id=r["audit_id"],
            alert_id=r["alert_id"],
            changed_by_name=r["changed_by_name"],
            old_status=r["old_status"],
            new_status=r["new_status"],
            old_decision=r["old_decision"],
            new_decision=r["new_decision"],
            changed_at=r["changed_at"]
        )
        for r in rows
    ]

