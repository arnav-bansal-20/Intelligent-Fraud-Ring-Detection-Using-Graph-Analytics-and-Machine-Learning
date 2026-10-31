from fastapi import APIRouter, Depends
from typing import List, Dict
from backend.schemas import DashboardMetricsResponse, ModelMetrics, BenchmarkHopResult
from backend.auth import require_roles
from backend.database import get_pg_connection

router = APIRouter(prefix="/dashboard", tags=["Manager Dashboard"])

@router.get("/metrics", response_model=DashboardMetricsResponse)
def get_dashboard_metrics(current_user: dict = Depends(require_roles(["manager", "admin"]))):
    """
    Manager dashboard metrics: open alerts, fraud rate, model metrics (precision, recall, F1, PR-AUC).
    Restricted to manager and admin roles.
    """
    conn = get_pg_connection()
    cur = conn.cursor()

    # 1. Alert Status Counts (Company transactions only)
    cur.execute("""
        SELECT
            al.status,
            COUNT(*) as cnt
        FROM alert al
        JOIN transaction t ON t.transaction_id = al.transaction_id
        WHERE t.source = 'company'
        GROUP BY al.status;
    """)
    status_counts = {r["status"]: r["cnt"] for r in cur.fetchall()}

    open_alerts = status_counts.get("open", 0)
    reviewing_alerts = status_counts.get("reviewing", 0)
    closed_alerts = status_counts.get("closed", 0)
    total_alerts = open_alerts + reviewing_alerts + closed_alerts

    # 2. Alert Decision Breakdown (Company transactions only)
    cur.execute("""
        SELECT
            COALESCE(al.decision, 'Pending Decision') as dec,
            COUNT(*) as cnt
        FROM alert al
        JOIN transaction t ON t.transaction_id = al.transaction_id
        WHERE t.source = 'company'
        GROUP BY al.decision;
    """)
    decisions_breakdown = {r["dec"]: r["cnt"] for r in cur.fetchall()}

    # 3. Transaction & Portfolio Fraud Rate (Company records only)
    cur.execute("""
        SELECT
            COUNT(*) as total_tx,
            SUM(CASE WHEN is_fraud = true THEN 1 ELSE 0 END) as fraud_tx
        FROM transaction
        WHERE source = 'company';
    """)
    tx_stats = cur.fetchone()
    total_tx = tx_stats["total_tx"] if tx_stats and tx_stats["total_tx"] else 0
    fraud_tx = tx_stats["fraud_tx"] if tx_stats and tx_stats["fraud_tx"] else 0
    fraud_rate_pct = round((fraud_tx / total_tx) * 100, 2) if total_tx > 0 else 0.0

    cur.close()
    conn.close()

    # 4. Verified XGBoost Model Metrics on 1.85M Sparkov Dataset
    model_metrics = ModelMetrics(
        precision=0.9720,
        recall=0.1198,
        f1_score=0.2134,
        pr_auc=0.9514,
        roc_auc=0.9804,
        tradeoff_explanation=(
            "Pre-Trained AI Classifier Governance: The model was pre-trained on 1.85M historical transaction records "
            "achieving an ultra-high Precision of 97.20% and PR-AUC of 95.14%. It prioritizes eliminating false positive "
            "alerts so only high-conviction fraud syndicate patterns trigger investigation."
        )
    )

    return DashboardMetricsResponse(
        open_alerts=open_alerts,
        reviewing_alerts=reviewing_alerts,
        closed_alerts=closed_alerts,
        total_alerts=total_alerts,
        total_transactions=total_tx,
        fraud_transactions=fraud_tx,
        portfolio_fraud_rate_pct=fraud_rate_pct,
        model_metrics=model_metrics,
        decisions_breakdown=decisions_breakdown,
        status_breakdown={
            "open": open_alerts,
            "reviewing": reviewing_alerts,
            "closed": closed_alerts
        }
    )

@router.get("/benchmarks", response_model=List[BenchmarkHopResult])
def get_benchmark_results(current_user: dict = Depends(require_roles(["manager", "admin"]))):
    """
    Step 5 multi-hop traversal benchmark results comparing MongoDB graph traversal
    vs PostgreSQL recursive CTE joins.
    """
    return [
        BenchmarkHopResult(
            hops=1,
            discovered_nodes=1.0,
            postgres_cte_latency_ms=3.44,
            postgres_cte_p95_ms=6.34,
            mongodb_graph_latency_ms=0.42,
            mongodb_graph_p95_ms=0.75,
            speedup="8.2x"
        ),
        BenchmarkHopResult(
            hops=2,
            discovered_nodes=2.0,
            postgres_cte_latency_ms=3.92,
            postgres_cte_p95_ms=5.87,
            mongodb_graph_latency_ms=0.57,
            mongodb_graph_p95_ms=0.80,
            speedup="6.9x"
        ),
        BenchmarkHopResult(
            hops=3,
            discovered_nodes=2.0,
            postgres_cte_latency_ms=4.00,
            postgres_cte_p95_ms=6.18,
            mongodb_graph_latency_ms=0.72,
            mongodb_graph_p95_ms=1.07,
            speedup="5.5x"
        )
    ]

