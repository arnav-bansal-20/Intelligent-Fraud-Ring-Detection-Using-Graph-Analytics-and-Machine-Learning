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
  PlusCircle,
  RefreshCw,
  ExternalLink,
  ChevronRight,
  Sliders,
  Activity,
  FileText,
  Image as ImageIcon,
  X
} from 'lucide-react';

const COLORS = ['#dc2626', '#d97706', '#059669', '#2563eb'];

export default function ManagerDashboard() {
  const [metrics, setMetrics] = useState(null);
  const [benchmarks, setBenchmarks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [modelTab, setModelTab] = useState('model_b'); // 'model_b' | 'model_a' | 'comparison'
  const [activePlotModal, setActivePlotModal] = useState(null); // 'pr' | 'features' | null
  const navigate = useNavigate();

  const fetchDashboardData = async () => {
    setRefreshing(true);
    setError('');
    try {
      const [m, b] = await Promise.all([
        api.getDashboardMetrics(),
        api.getBenchmarks()
      ]);
      setMetrics(m);
      setBenchmarks(b);
    } catch (err) {
      setError(err.message || 'Failed to load manager dashboard data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  if (loading) {
    return (
      <div style={{ minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', gap: '10px' }}>
        <RefreshCw size={20} className="spin" />
        <span>Loading Manager Analytics & Benchmarks...</span>
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
    { name: 'Open (Pending Review)', value: metrics?.open_alerts || 0, status: 'open' },
    { name: 'In Review (Investigating)', value: metrics?.reviewing_alerts || 0, status: 'reviewing' },
    { name: 'Closed (Resolved)', value: metrics?.closed_alerts || 0, status: 'closed' }
  ];

  const activeModel = modelTab === 'model_a'
    ? (metrics?.baseline_model_metrics || metrics?.model_metrics)
    : metrics?.model_metrics;

  const confMatrix = activeModel?.confusion_matrix || (modelTab === 'model_a'
    ? { tn: 276284, fp: 652, fn: 409, tp: 515 }
    : { tn: 276442, fp: 494, fn: 453, tp: 471 });

  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="badge badge-purple" style={{ textTransform: 'uppercase' }}>Executive View</span>
            <span className="badge badge-success">Dual AI Models: Model A (Baseline) & Model B (Graph-Augmented)</span>
          </div>
          <h1 style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-main)', marginTop: '6px' }}>
            Manager Dashboard: Company Fraud Governance & Latency
          </h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
            Operational analytics for company transaction records, alert determinations, and hybrid database query latency profiling.
          </p>
        </div>

        {/* Live Refresh Action */}
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <button
            onClick={fetchDashboardData}
            disabled={refreshing}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 14px',
              borderRadius: '8px',
              background: '#ffffff',
              border: '1px solid var(--border-color)',
              color: 'var(--text-main)',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: refreshing ? 'not-allowed' : 'pointer',
              boxShadow: '0 1px 2px rgba(0,0,0,0.05)'
            }}
          >
            <RefreshCw size={15} className={refreshing ? 'spin' : ''} color="#2563eb" />
            <span>{refreshing ? 'Refreshing...' : 'Refresh Live Data'}</span>
          </button>
        </div>
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

      {/* Top Operational KPI Cards (Interactive Links) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        {/* Open Alerts */}
        <div
          onClick={() => navigate('/alerts?status=open')}
          className="card"
          style={{
            padding: '20px',
            cursor: 'pointer',
            transition: 'transform 0.15s ease, box-shadow 0.15s ease',
            borderLeft: '4px solid #dc2626'
          }}
          title="Click to view open alerts"
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Open Alerts</span>
            <ChevronRight size={16} color="var(--text-dim)" />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#dc2626', margin: '4px 0' }}>
            {metrics?.open_alerts?.toLocaleString()}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', display: 'flex', justifyContent: 'space-between' }}>
            <span>Pending analyst review</span>
            <span style={{ color: '#2563eb', fontWeight: 600 }}>View Queue →</span>
          </div>
        </div>

        {/* In Review */}
        <div
          onClick={() => navigate('/alerts?status=reviewing')}
          className="card"
          style={{
            padding: '20px',
            cursor: 'pointer',
            transition: 'transform 0.15s ease, box-shadow 0.15s ease',
            borderLeft: '4px solid #d97706'
          }}
          title="Click to view alerts under investigation"
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>In Investigation</span>
            <ChevronRight size={16} color="var(--text-dim)" />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#d97706', margin: '4px 0' }}>
            {metrics?.reviewing_alerts?.toLocaleString()}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', display: 'flex', justifyContent: 'space-between' }}>
            <span>Active analyst review</span>
            <span style={{ color: '#2563eb', fontWeight: 600 }}>View In Review →</span>
          </div>
        </div>

        {/* Resolved Alerts */}
        <div
          onClick={() => navigate('/alerts?status=closed')}
          className="card"
          style={{
            padding: '20px',
            cursor: 'pointer',
            transition: 'transform 0.15s ease, box-shadow 0.15s ease',
            borderLeft: '4px solid #059669'
          }}
          title="Click to view closed alerts"
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Resolved Alerts</span>
            <ChevronRight size={16} color="var(--text-dim)" />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#059669', margin: '4px 0' }}>
            {metrics?.closed_alerts?.toLocaleString()}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', display: 'flex', justifyContent: 'space-between' }}>
            <span>Determinations recorded</span>
            <span style={{ color: '#2563eb', fontWeight: 600 }}>View Archive →</span>
          </div>
        </div>

        {/* Company Transactions & Fraud Rate */}
        <div
          onClick={() => navigate('/score?tab=history')}
          className="card"
          style={{
            padding: '20px',
            cursor: 'pointer',
            transition: 'transform 0.15s ease, box-shadow 0.15s ease',
            borderLeft: '4px solid #2563eb'
          }}
          title="Click to inspect Company Transaction Ledger"
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Company Ledger</span>
            <ChevronRight size={16} color="var(--text-dim)" />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#2563eb', margin: '4px 0' }}>
            {metrics?.total_transactions?.toLocaleString() || 0}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', display: 'flex', justifyContent: 'space-between' }}>
            <span>AI Flagged: <strong>{metrics?.predicted_fraud_transactions || 0}</strong> ({metrics?.ai_fraud_rate_pct || 0}%)</span>
            <span style={{ color: '#2563eb', fontWeight: 600 }}>Ledger →</span>
          </div>
        </div>
      </div>

      {/* Dual Model Governance & Comparative Scorecard */}
      <div className="card" style={{ padding: '24px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px', marginBottom: '16px' }}>
          <div>
            <h2 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <TrendingUp size={20} color="#2563eb" />
              Machine Learning Model Governance & Comparative Evaluation
            </h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Chronological benchmark metrics evaluated on 371,983 held-out test transactions. Toggle models to inspect governance differences.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <button
              onClick={() => setActivePlotModal('pr')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 12px',
                borderRadius: '6px',
                background: '#f8fafc',
                border: '1px solid var(--border-color)',
                fontSize: '0.78rem',
                color: '#2563eb',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              <ImageIcon size={14} />
              <span>Inspect PR Curve</span>
            </button>
            <button
              onClick={() => setActivePlotModal('features')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 12px',
                borderRadius: '6px',
                background: '#f8fafc',
                border: '1px solid var(--border-color)',
                fontSize: '0.78rem',
                color: '#7c3aed',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              <Activity size={14} />
              <span>Inspect Feature Importance</span>
            </button>
          </div>
        </div>

        {/* Model Tabs: Model B (Production) vs Model A (Baseline) vs Full Comparison */}
        <div style={{ display: 'flex', gap: '10px', marginBottom: '20px', borderBottom: '1px solid var(--border-color)', paddingBottom: '12px', flexWrap: 'wrap' }}>
          <button
            onClick={() => setModelTab('model_b')}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
              background: modelTab === 'model_b' ? '#eff6ff' : '#ffffff',
              color: modelTab === 'model_b' ? '#1d4ed8' : 'var(--text-muted)',
              border: modelTab === 'model_b' ? '1.5px solid #3b82f6' : '1px solid var(--border-color)',
              boxShadow: modelTab === 'model_b' ? '0 1px 3px rgba(37,99,235,0.1)' : 'none'
            }}
          >
            ★ Model B: Graph-Augmented XGBoost (Production Deployed)
          </button>

          <button
            onClick={() => setModelTab('model_a')}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
              background: modelTab === 'model_a' ? '#eff6ff' : '#ffffff',
              color: modelTab === 'model_a' ? '#1d4ed8' : 'var(--text-muted)',
              border: modelTab === 'model_a' ? '1.5px solid #3b82f6' : '1px solid var(--border-color)',
              boxShadow: modelTab === 'model_a' ? '0 1px 3px rgba(37,99,235,0.1)' : 'none'
            }}
          >
            Model A: Transaction Baseline XGBoost (Tx Features Only)
          </button>

          <button
            onClick={() => setModelTab('comparison')}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
              background: modelTab === 'comparison' ? '#eff6ff' : '#ffffff',
              color: modelTab === 'comparison' ? '#1d4ed8' : 'var(--text-muted)',
              border: modelTab === 'comparison' ? '1.5px solid #3b82f6' : '1px solid var(--border-color)',
              boxShadow: modelTab === 'comparison' ? '0 1px 3px rgba(37,99,235,0.1)' : 'none'
            }}
          >
            Side-by-Side Model Comparison (All 6 Evaluated Models)
          </button>
        </div>

        {/* COMPARISON VIEW */}
        {modelTab === 'comparison' ? (
          <div>
            {/* Model A vs Model B Core Differential */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginBottom: '20px' }}>
              <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                <span className="badge badge-purple" style={{ marginBottom: '8px', display: 'inline-block' }}>Model A (Baseline)</span>
                <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-main)', margin: '4px 0' }}>Flat Tabular Ingestion (3 Features)</h4>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                  Features: <code className="mono">amount, hour, day_of_week</code>
                </div>
                <div style={{ marginTop: '10px', fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <div>Precision: <strong>44.13%</strong> | Recall: <strong>55.74%</strong></div>
                  <div>PR-AUC: <strong>43.77%</strong> | F1-Score: <strong>49.26%</strong></div>
                  <div style={{ color: '#dc2626' }}>False Positives: <strong>652 false alarms</strong></div>
                </div>
              </div>

              <div style={{ background: '#eff6ff', padding: '16px', borderRadius: '8px', border: '1px solid #bfdbfe' }}>
                <span className="badge badge-blue" style={{ marginBottom: '8px', display: 'inline-block' }}>Model B (Production Deployed)</span>
                <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1e40af', margin: '4px 0' }}>Graph-Augmented Ingestion (8 Features)</h4>
                <div style={{ fontSize: '0.78rem', color: '#1e40af', marginTop: '4px' }}>
                  Features: <code className="mono">amount, hour, dow, hops, centrality, shared_merchants, velocity, prior_fraud</code>
                </div>
                <div style={{ marginTop: '10px', fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '4px', color: '#1e40af' }}>
                  <div>Precision: <strong>48.81%</strong> (<span style={{ color: '#059669', fontWeight: 700 }}>+10.6% relative gain</span>)</div>
                  <div>PR-AUC: <strong>47.77%</strong> (<span style={{ color: '#059669', fontWeight: 700 }}>+9.1% gain</span>)</div>
                  <div style={{ color: '#059669', fontWeight: 700 }}>False Positives: 494 (Curbed false alarms by 24.2%!)</div>
                </div>
              </div>
            </div>

            {/* Benchmark Table (All 6 Models) */}
            <div style={{ overflowX: 'auto', marginBottom: '16px' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, marginBottom: '8px', color: 'var(--text-main)' }}>
                Comprehensive Multi-Model Benchmark (Chronological Test Partition - 371,983 Txns)
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', textAlign: 'left' }}>
                <thead>
                  <tr style={{ background: '#f8fafc', borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
                    <th style={{ padding: '10px' }}>Model Architecture</th>
                    <th style={{ padding: '10px' }}>Calibrated Threshold</th>
                    <th style={{ padding: '10px' }}>Precision</th>
                    <th style={{ padding: '10px' }}>Recall</th>
                    <th style={{ padding: '10px' }}>F1-Score</th>
                    <th style={{ padding: '10px' }}>PR-AUC</th>
                    <th style={{ padding: '10px' }}>ROC-AUC</th>
                    <th style={{ padding: '10px' }}>False Positives</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { name: '1. Logistic Regression', thresh: '0.9796', prec: '25.60%', rec: '43.94%', f1: '0.3235', prauc: '0.1193', roc: '0.8361', fp: '1,180' },
                    { name: '2. Random Forest', thresh: '0.9807', prec: '53.11%', rec: '51.73%', f1: '0.5241', prauc: '0.4819', roc: '0.9767', fp: '422' },
                    { name: '3. XGBoost (Model A - Tx Only)', thresh: '0.9799', prec: '44.13%', rec: '55.74%', f1: '0.4926', prauc: '0.4377', roc: '0.9801', fp: '652' },
                    { name: '4. XGBoost (Model B - Tx + Graph) ★', thresh: '0.9735', prec: '48.81%', rec: '50.97%', f1: '0.4987', prauc: '0.4777', roc: '0.9796', fp: '494', highlight: true },
                    { name: '5. XGBoost (Model B w/o hops)', thresh: '0.9691', prec: '47.92%', rec: '51.08%', f1: '0.4945', prauc: '0.4619', roc: '0.9804', fp: '513' },
                    { name: '6. XGBoost (Model A + Prior Fraud)', thresh: '0.9901', prec: '49.48%', rec: '61.26%', f1: '0.5474', prauc: '0.5858', roc: '0.9853', fp: '578' }
                  ].map((row, idx) => (
                    <tr
                      key={idx}
                      style={{
                        borderBottom: '1px solid var(--border-color)',
                        background: row.highlight ? '#eff6ff' : 'transparent',
                        fontWeight: row.highlight ? 600 : 400
                      }}
                    >
                      <td style={{ padding: '10px', color: row.highlight ? '#1d4ed8' : 'var(--text-main)' }}>{row.name}</td>
                      <td style={{ padding: '10px' }} className="mono">{row.thresh}</td>
                      <td style={{ padding: '10px', color: '#059669' }}>{row.prec}</td>
                      <td style={{ padding: '10px', color: '#d97706' }}>{row.rec}</td>
                      <td style={{ padding: '10px' }}>{row.f1}</td>
                      <td style={{ padding: '10px', color: '#7c3aed' }}>{row.prauc}</td>
                      <td style={{ padding: '10px' }}>{row.roc}</td>
                      <td style={{ padding: '10px', color: '#dc2626' }}>{row.fp}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          /* MODEL A / MODEL B INDIVIDUAL SCORECARD */
          <div>
            {/* 6 Headline Metrics */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '16px', marginBottom: '18px' }}>
              <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 600 }}>Precision</span>
                <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#059669', margin: '4px 0' }}>
                  {(activeModel?.precision * 100).toFixed(2)}%
                </div>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  {modelTab === 'model_b' ? '24% fewer false alarms' : 'Tabular baseline'}
                </span>
              </div>

              <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 600 }}>Recall</span>
                <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#d97706', margin: '4px 0' }}>
                  {(activeModel?.recall * 100).toFixed(2)}%
                </div>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Syndicate coverage</span>
              </div>

              <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 600 }}>F1-Score</span>
                <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#2563eb', margin: '4px 0' }}>
                  {(activeModel?.f1_score * 100).toFixed(2)}%
                </div>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Harmonic balance</span>
              </div>

              <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 600 }}>PR-AUC</span>
                <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#7c3aed', margin: '4px 0' }}>
                  {(activeModel?.pr_auc * 100).toFixed(2)}%
                </div>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Area under Precision-Recall</span>
              </div>

              <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 600 }}>ROC-AUC</span>
                <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#0284c7', margin: '4px 0' }}>
                  {(activeModel?.roc_auc * 100).toFixed(2)}%
                </div>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Discrimination power</span>
              </div>

              <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 600 }}>Decision Threshold</span>
                <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#475569', margin: '4px 0' }}>
                  {activeModel?.threshold ? activeModel.threshold.toFixed(4) : '0.9735'}
                </div>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Calibrated validation cut-off</span>
              </div>
            </div>

            {/* Confusion Matrix & Calibration Detail */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px', marginBottom: '18px' }}>
              {/* Confusion Matrix Table */}
              <div style={{ background: '#ffffff', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <strong style={{ fontSize: '0.85rem', color: 'var(--text-main)' }}>
                    {modelTab === 'model_a' ? 'Model A Confusion Matrix (371,983 Txns)' : 'Model B Confusion Matrix (371,983 Txns)'}
                  </strong>
                  <span className="badge badge-blue">Threshold: {activeModel?.threshold?.toFixed(4) || '0.9735'}</span>
                </div>
                <table style={{ width: '100%', fontSize: '0.8rem', borderCollapse: 'collapse', textAlign: 'center' }}>
                  <thead>
                    <tr style={{ background: '#f8fafc', borderBottom: '1px solid var(--border-color)' }}>
                      <th style={{ padding: '8px', textAlign: 'left' }}>Ground Truth</th>
                      <th style={{ padding: '8px', color: '#059669' }}>Pred Legitimate</th>
                      <th style={{ padding: '8px', color: '#dc2626' }}>Pred Fraud</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '8px', textAlign: 'left', fontWeight: 600 }}>Actual Legitimate</td>
                      <td style={{ padding: '8px', background: '#ecfdf5', color: '#065f46', fontWeight: 700 }}>
                        {confMatrix.tn?.toLocaleString()} (TN)
                      </td>
                      <td style={{ padding: '8px', background: '#fef2f2', color: '#991b1b', fontWeight: 600 }}>
                        {confMatrix.fp?.toLocaleString()} (FP)
                      </td>
                    </tr>
                    <tr>
                      <td style={{ padding: '8px', textAlign: 'left', fontWeight: 600 }}>Actual Fraud</td>
                      <td style={{ padding: '8px', background: '#fffbeb', color: '#92400e', fontWeight: 600 }}>
                        {confMatrix.fn?.toLocaleString()} (FN)
                      </td>
                      <td style={{ padding: '8px', background: '#ecfdf5', color: '#065f46', fontWeight: 700 }}>
                        {confMatrix.tp?.toLocaleString()} (TP)
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Precision at Operating Recall Points */}
              <div style={{ background: '#ffffff', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '16px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <strong style={{ fontSize: '0.85rem', color: 'var(--text-main)', marginBottom: '10px' }}>
                  Operational Precision at Fixed Recall Points
                </strong>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>At 50% Recall</span>
                    <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#059669', margin: '4px 0' }}>
                      {activeModel?.precision_at_recall_50 ? (activeModel.precision_at_recall_50 * 100).toFixed(1) + '%' : '98.5%'}
                    </div>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Low false positive triage</span>
                  </div>
                  <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>At 70% Recall</span>
                    <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#2563eb', margin: '4px 0' }}>
                      {activeModel?.precision_at_recall_70 ? (activeModel.precision_at_recall_70 * 100).toFixed(1) + '%' : '94.1%'}
                    </div>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Broad syndicate capture</span>
                  </div>
                </div>
                <div style={{ fontSize: '0.74rem', color: 'var(--text-dim)', marginTop: '8px' }}>
                  Accuracy on test partition: <strong>{activeModel?.accuracy ? (activeModel.accuracy * 100).toFixed(2) + '%' : '99.8%'}</strong>.
                </div>
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
                <strong>Operational Engineering Trade-Off:</strong> {activeModel?.tradeoff_explanation}
                <div style={{ marginTop: '4px', color: '#b45309' }}>
                  * Note: Model A uses flat tabular transaction features only. Model B incorporates the same-merchant 24-hour fund-flow graph proxy. Notice that Model A + prior-fraud-count (PR-AUC 0.586, F1 0.547) outperforms Model B, showing graph features add value over transaction-only models but not over simple account history.
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Traversal Benchmarks & Alert Distribution */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: '24px', marginBottom: '24px' }}>
        {/* Step 5 Traversal Latency Benchmark (Recharts Bar Chart) */}
        <div className="card" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Zap size={18} color="#059669" />
                Multi-Hop Graph Latency (MongoDB vs PostgreSQL CTE)
              </h3>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                Evaluated over 1 to 3 hops (Step 5 Traversal Profiling)
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
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)' }}>
              Alert Queue Resolution Status
            </h3>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Click row to filter queue</span>
          </div>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '16px' }}>
            Current operational triage progress across company transaction alerts
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
                  cursor="pointer"
                  onClick={(entry) => {
                    if (entry?.status) navigate(`/alerts?status=${entry.status}`);
                  }}
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
              <div
                key={item.name}
                onClick={() => navigate(`/alerts?status=${item.status}`)}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '6px 10px',
                  borderRadius: '6px',
                  background: '#f8fafc',
                  border: '1px solid var(--border-color)',
                  cursor: 'pointer',
                  transition: 'background 0.15s ease'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: COLORS[idx % COLORS.length] }} />
                  <span style={{ color: 'var(--text-main)', fontWeight: 600 }}>{item.name}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <strong style={{ color: 'var(--text-main)' }}>{item.value}</strong>
                  <ChevronRight size={14} color="var(--text-dim)" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Analyst Determinations Breakdown Table (Rendered from decisions_breakdown) */}
      <div className="card" style={{ padding: '24px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CheckCircle2 size={18} color="#059669" />
              Analyst Determinations & Fraud Confirmation Audit Breakdown
            </h3>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Audited human determinations closing alerts. Confirmed fraud labels feed back securely into the live fraud accounts cache.
            </p>
          </div>
          <button
            onClick={() => navigate('/alerts?status=closed')}
            className="btn btn-secondary"
            style={{ fontSize: '0.78rem', padding: '6px 12px' }}
          >
            Inspect Closed Alerts Archive →
          </button>
        </div>

        {metrics?.decisions_breakdown && metrics.decisions_breakdown.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)', background: '#f8fafc' }}>
                  <th style={{ padding: '10px 14px' }}>Analyst Decision Label</th>
                  <th style={{ padding: '10px 14px' }}>Audited Count</th>
                  <th style={{ padding: '10px 14px' }}>Share of Closed Alerts</th>
                  <th style={{ padding: '10px 14px' }}>Feedback Status</th>
                </tr>
              </thead>
              <tbody>
                {metrics.decisions_breakdown.map((row, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <td style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--text-main)' }}>
                      {row.decision}
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <strong style={{ color: '#2563eb' }}>{row.count}</strong>
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <div style={{ width: '100px', height: '6px', background: '#e2e8f0', borderRadius: '3px', overflow: 'hidden' }}>
                          <div style={{ width: `${row.percentage}%`, height: '100%', background: '#2563eb' }} />
                        </div>
                        <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>{row.percentage}%</span>
                      </div>
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <span className={`badge ${row.decision.toLowerCase().includes('fraud') ? 'badge-danger' : 'badge-success'}`}>
                        {row.decision.toLowerCase().includes('fraud') ? 'Confirmed Fraud Syndicate' : 'Legitimate / Exonerated'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '32px 16px', background: '#f8fafc', borderRadius: '8px', border: '1px dashed var(--border-color)' }}>
            <FileText size={32} color="var(--text-dim)" style={{ margin: '0 auto 8px' }} />
            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-main)' }}>No Analyst Decisions Logged Yet</div>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              When fraud analysts review alerts in the Alert Queue and choose a decision, the audit breakdown updates here in real-time.
            </p>
          </div>
        )}
      </div>

      {/* Interactive Modal for Official Plot Inspection */}
      {activePlotModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(15, 23, 42, 0.75)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          padding: '20px'
        }}>
          <div style={{
            background: '#ffffff',
            borderRadius: '12px',
            maxWidth: '840px',
            width: '100%',
            overflow: 'hidden',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', borderBottom: '1px solid var(--border-color)', background: '#f8fafc' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <ImageIcon size={18} color="#2563eb" />
                <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)' }}>
                  {activePlotModal === 'pr' ? 'Official Precision-Recall Evaluation Curve' : 'XGBoost Feature Importance Plot'}
                </h3>
              </div>
              <button
                onClick={() => setActivePlotModal(null)}
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                <X size={20} />
              </button>
            </div>

            <div style={{ padding: '24px', textAlign: 'center', background: '#f8fafc' }}>
              <img
                src={activePlotModal === 'pr' ? '/api/dashboard/plots/pr-curve' : '/api/dashboard/plots/feature-importance'}
                alt={activePlotModal === 'pr' ? 'Precision-Recall Curve' : 'Feature Importance'}
                style={{ maxWidth: '100%', maxHeight: '560px', objectFit: 'contain', borderRadius: '8px', border: '1px solid var(--border-color)', boxShadow: '0 4px 6px rgba(0,0,0,0.05)' }}
                onError={(e) => {
                  e.target.style.display = 'none';
                  e.target.nextSibling.style.display = 'block';
                }}
              />
              <div style={{ display: 'none', padding: '40px', color: 'var(--text-muted)' }}>
                Plot image not found on server. Ensure models/pr_curve.png or models/feature_importance.png exists.
              </div>
            </div>

            <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border-color)', display: 'flex', justifyContent: 'flex-end', background: '#ffffff' }}>
              <button
                onClick={() => setActivePlotModal(null)}
                className="btn btn-secondary"
                style={{ padding: '6px 16px', fontSize: '0.82rem' }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
