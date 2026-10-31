import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import {
  BarChart3,
  ShieldCheck,
  TrendingUp,
  Zap,
  Info,
  Layers,
  Database,
  CheckCircle2,
  AlertCircle,
  PlusCircle
} from 'lucide-react';

const COLORS = ['#dc2626', '#d97706', '#059669', '#2563eb'];

export default function ManagerDashboard() {
  const [metrics, setMetrics] = useState(null);
  const [benchmarks, setBenchmarks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([
      api.getDashboardMetrics(),
      api.getBenchmarks()
    ])
      .then(([m, b]) => {
        setMetrics(m);
        setBenchmarks(b);
      })
      .catch(err => setError(err.message || 'Failed to load manager dashboard data'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={{ minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
        Loading Manager Analytics & Benchmarks...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ maxWidth: '800px', margin: '40px auto', padding: '24px' }}>
        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', padding: '16px', borderRadius: '8px' }}>
          {error}
        </div>
      </div>
    );
  }

  // Format data for Recharts Benchmark comparison
  const benchmarkChartData = benchmarks.map(b => ({
    name: `${b.hops} Hop${b.hops > 1 ? 's' : ''}`,
    postgres: b.postgres_cte_latency_ms,
    mongodb: b.mongodb_graph_latency_ms,
    speedup: b.speedup
  }));

  // Format Alert Status Breakdown for PieChart
  const statusPieData = [
    { name: 'Open (Pending Review)', value: metrics?.open_alerts || 0 },
    { name: 'In Review (Investigating)', value: metrics?.reviewing_alerts || 0 },
    { name: 'Closed (Resolved)', value: metrics?.closed_alerts || 0 }
  ];

  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '24px' }}>
      {/* Header */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="badge badge-purple" style={{ textTransform: 'uppercase' }}>Executive View</span>
          <span className="badge badge-success">Production Model v2 (XGBoost)</span>
        </div>
        <h1 style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-main)', marginTop: '6px' }}>
          Manager Dashboard: Company Fraud Governance & Latency
        </h1>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
          Operational analytics for company transaction records, alert determinations, and hybrid database query latency profiling.
        </p>
      </div>

      {/* Onboarding Banner if no company transactions yet */}
      {metrics?.total_transactions === 0 && (
        <div style={{
          background: '#eff6ff',
          border: '1px solid #bfdbfe',
          borderRadius: '8px',
          padding: '16px 20px',
          marginBottom: '24px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px'
        }}>
          <div>
            <div style={{ fontWeight: 700, color: '#1d4ed8', fontSize: '0.95rem' }}>
              No Company Transactions Analyzed Yet
            </div>
            <div style={{ fontSize: '0.82rem', color: '#1e40af', marginTop: '2px' }}>
              Historical training datasets are isolated for AI model governance. Input or batch-import your company's transaction records to generate live operational metrics.
            </div>
          </div>
          <button
            onClick={() => navigate('/score')}
            className="btn btn-primary"
            style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.82rem', padding: '8px 14px' }}
          >
            <PlusCircle size={15} />
            Add & Analyze Transactions
          </button>
        </div>
      )}

      {/* Top Operational KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <div className="card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Company Open Alerts</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#dc2626', margin: '4px 0' }}>
            {metrics?.open_alerts?.toLocaleString()}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
            Pending analyst review
          </div>
        </div>

        <div className="card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>In Investigation</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#d97706', margin: '4px 0' }}>
            {metrics?.reviewing_alerts?.toLocaleString()}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
            Active analyst review
          </div>
        </div>

        <div className="card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Resolved Alerts</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#059669', margin: '4px 0' }}>
            {metrics?.closed_alerts?.toLocaleString()}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
            Determinations recorded
          </div>
        </div>

        <div className="card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Company Fraud Rate</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#2563eb', margin: '4px 0' }}>
            {metrics?.portfolio_fraud_rate_pct}%
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
            {metrics?.fraud_transactions?.toLocaleString()} of {metrics?.total_transactions?.toLocaleString()} company transactions
          </div>
        </div>
      </div>

      {/* Model Performance & Precision-Recall Scorecard */}
      <div className="card" style={{ padding: '24px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px', marginBottom: '18px' }}>
          <div>
            <h2 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <TrendingUp size={20} color="#2563eb" />
              Pre-Trained AI Classifier Governance (Trained on 1.85M Historical Dataset)
            </h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Benchmark metrics evaluated on historical Sparkov dataset. Operates as the decision engine for screening company transactions.
            </p>
          </div>
          <span className="badge badge-blue">Evaluated on Precision / Recall / PR-AUC</span>
        </div>

        {/* 5 Headline Metrics */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px', marginBottom: '18px' }}>
          <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 600 }}>Precision</span>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#059669', margin: '4px 0' }}>
              {(metrics?.model_metrics?.precision * 100).toFixed(2)}%
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Low false positive rate</span>
          </div>

          <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 600 }}>Recall</span>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#d97706', margin: '4px 0' }}>
              {(metrics?.model_metrics?.recall * 100).toFixed(2)}%
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Focused syndicate coverage</span>
          </div>

          <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 600 }}>F1-Score</span>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#2563eb', margin: '4px 0' }}>
              {(metrics?.model_metrics?.f1_score * 100).toFixed(2)}%
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Harmonic balance</span>
          </div>

          <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 600 }}>PR-AUC</span>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#7c3aed', margin: '4px 0' }}>
              {(metrics?.model_metrics?.pr_auc * 100).toFixed(2)}%
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Area under Precision-Recall</span>
          </div>

          <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 600 }}>ROC-AUC</span>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#0284c7', margin: '4px 0' }}>
              {(metrics?.model_metrics?.roc_auc * 100).toFixed(2)}%
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>High discrimination power</span>
          </div>
        </div>

        {/* Honest Trade-off Box */}
        <div style={{
          background: '#fffbeb',
          border: '1px solid #fde68a',
          borderRadius: '8px',
          padding: '14px 18px',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '12px',
          fontSize: '0.82rem',
          color: '#92400e'
        }}>
          <Info size={20} style={{ flexShrink: 0, marginTop: '2px', color: '#d97706' }} />
          <div>
            <strong>Operational Engineering Trade-Off:</strong> {metrics?.model_metrics?.tradeoff_explanation}
            <div style={{ marginTop: '4px', color: '#b45309' }}>
              * Note: The underlying graph model operates on a same-merchant 24-hour fund-flow proxy derived from Sparkov dataset attributes without fabricating arbitrary device or IP records.
            </div>
          </div>
        </div>
      </div>

      {/* Traversal Benchmarks & Alert Distribution */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: '24px' }}>
        {/* Step 5 Traversal Latency Benchmark (Recharts Bar Chart) */}
        <div className="card" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Zap size={18} color="#059669" />
                Multi-Hop Graph Latency (MongoDB vs PostgreSQL CTE)
              </h3>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                Evaluated over 1 to 3 hops (Step 5 Benchmark)
              </p>
            </div>
            <span className="badge badge-success">Up to 8.2x Speedup</span>
          </div>

          <div style={{ height: '320px', width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={benchmarkChartData} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" stroke="#64748b" tick={{ fill: '#64748b', fontSize: '0.78rem' }} />
                <YAxis stroke="#64748b" tick={{ fill: '#64748b', fontSize: '0.78rem' }} label={{ value: 'Latency (ms)', angle: -90, position: 'insideLeft', fill: '#64748b', fontSize: '0.78rem' }} />
                <Tooltip
                  contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '8px', color: '#0f172a', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}
                  formatter={(value, name) => [`${value} ms`, name === 'mongodb' ? 'MongoDB Graph' : 'PostgreSQL Recursive CTE']}
                />
                <Legend wrapperStyle={{ fontSize: '0.8rem', color: '#475569' }} />
                <Bar dataKey="postgres" name="PostgreSQL Recursive CTE" fill="#ef4444" radius={[4, 4, 0, 0]} />
                <Bar dataKey="mongodb" name="MongoDB $graphLookup" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div style={{ marginTop: '12px', display: 'flex', justifyContent: 'space-around', fontSize: '0.78rem', borderTop: '1px solid var(--border-color)', paddingTop: '12px' }}>
            {benchmarks.map(b => (
              <div key={b.hops} style={{ textAlign: 'center' }}>
                <span style={{ color: 'var(--text-dim)', display: 'block' }}>{b.hops} Hop Traversal:</span>
                <strong style={{ color: '#059669', fontSize: '0.9rem' }}>{b.speedup} Faster</strong>
                <div style={{ color: 'var(--text-dim)', fontSize: '0.7rem' }}>
                  {b.mongodb_graph_latency_ms}ms vs {b.postgres_cte_latency_ms}ms
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Alert Queue Status Distribution */}
        <div className="card" style={{ padding: '24px' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '4px' }}>
            Alert Queue Resolution Status
          </h3>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '16px' }}>
            Current operational triage progress
          </p>

          <div style={{ height: '260px', width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={statusPieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {statusPieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '8px', color: '#0f172a', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.78rem' }}>
            {statusPieData.map((item, idx) => (
              <div key={item.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: COLORS[idx % COLORS.length] }} />
                  <span style={{ color: 'var(--text-muted)' }}>{item.name}</span>
                </div>
                <strong style={{ color: 'var(--text-main)' }}>{item.value}</strong>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
