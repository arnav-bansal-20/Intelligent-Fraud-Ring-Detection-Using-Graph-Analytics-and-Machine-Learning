from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# ------------------------------------------------------------------------------
# Authentication
# ------------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str = Field(..., description="Analyst username")
    password: str = Field(..., description="Plain password")

class UserInfo(BaseModel):
    analyst_id: int
    username: str
    role: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo

# ------------------------------------------------------------------------------
# Scoring
# ------------------------------------------------------------------------------
class TransactionScoreRequest(BaseModel):
    account_id: int = Field(..., ge=1, le=999, description="Target bank account ID")
    merchant_id: int = Field(1, ge=1, description="Merchant ID")
    amount: float = Field(..., gt=0, description="Transaction amount in USD")
    txn_timestamp: Optional[str] = Field(None, description="ISO timestamp (defaults to current time)")
    save_alert: Optional[bool] = Field(True, description="Whether to create an alert if risk is High")

class FeatureReason(BaseModel):
    feature: str
    description: str
    value: float
    contribution_level: str  # "Critical", "High", "Moderate", "Baseline"

class TransactionScoreResponse(BaseModel):
    account_id: int
    merchant_id: int
    amount: float
    fraud_probability: float
    risk_label: str  # "Low", "Medium", "High"
    top_reasons: List[FeatureReason]
    graph_features: Dict[str, Any]
    alert_created: bool = False
    alert_id: Optional[int] = None
    evaluated_at: str

class SampleTransactionOption(BaseModel):
    transaction_id: int
    trans_num: str
    account_id: int
    customer_name: str
    merchant_id: int
    merchant_name: str
    amount: float
    txn_timestamp: str
    is_fraud: bool

# ------------------------------------------------------------------------------
# Alert Queue
# ------------------------------------------------------------------------------
class AlertListItem(BaseModel):
    alert_id: int
    transaction_id: int
    account_id: int
    customer_name: str
    merchant_name: str
    amount: float
    txn_timestamp: str
    fraud_probability: float
    risk_label: str
    status: str
    decision: Optional[str] = None
    note: Optional[str] = None
    analyst_name: Optional[str] = None
    created_at: str
    updated_at: str

class AlertReviewRequest(BaseModel):
    status: str = Field(..., pattern="^(open|reviewing|closed)$", description="Alert review status")
    decision: str = Field(..., min_length=2, max_length=100, description="Analyst fraud determination")
    note: str = Field(..., min_length=3, description="Analyst investigation notes")

class AlertAuditItem(BaseModel):
    audit_id: int
    alert_id: int
    changed_by_name: Optional[str]
    old_status: Optional[str]
    new_status: Optional[str]
    old_decision: Optional[str]
    new_decision: Optional[str]
    changed_at: str

# ------------------------------------------------------------------------------
# Ring Explorer
# ------------------------------------------------------------------------------
class RingNode(BaseModel):
    id: str
    account_id: int
    label: str
    customer_name: Optional[str] = None
    account_number: Optional[str] = None
    is_center: bool
    is_fraud: bool
    degree: int
    shared_merchants_with_center: int = 0
    risk_level: str

class RingEdge(BaseModel):
    id: str
    source: str
    target: str
    shared_merchant_count: int
    label: str

class RingExplorerResponse(BaseModel):
    center_account_id: int
    hops: int
    raw_neighborhood_degree: int
    capped_nodes_count: int
    nodes: List[RingNode]
    edges: List[RingEdge]
    density_note: str

# ------------------------------------------------------------------------------
# Dashboard & Benchmarks
# ------------------------------------------------------------------------------
class ModelMetrics(BaseModel):
    precision: float
    recall: float
    f1_score: float
    pr_auc: float
    roc_auc: float
    tradeoff_explanation: str

class DashboardMetricsResponse(BaseModel):
    open_alerts: int
    reviewing_alerts: int
    closed_alerts: int
    total_alerts: int
    total_transactions: int
    fraud_transactions: int
    portfolio_fraud_rate_pct: float
    model_metrics: ModelMetrics
    decisions_breakdown: Dict[str, int]
    status_breakdown: Dict[str, int]

class BenchmarkHopResult(BaseModel):
    hops: int
    discovered_nodes: float
    postgres_cte_latency_ms: float
    postgres_cte_p95_ms: float
    mongodb_graph_latency_ms: float
    mongodb_graph_p95_ms: float
    speedup: str

