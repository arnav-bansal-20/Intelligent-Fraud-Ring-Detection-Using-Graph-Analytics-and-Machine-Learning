import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import {
  SlidersHorizontal,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  Network,
  Zap,
  Info,
  ArrowRight,
  Sparkles
} from 'lucide-react';

export default function ScoreTransaction() {
  const [formData, setFormData] = useState({
    account_id: 787,
    amount: 850.00,
    merchant_id: 1,
    txn_timestamp: new Date().toISOString()
  });

  const [samples, setSamples] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    // Load sample transactions for quick selection
    api.getSampleTransactions()
      .then(data => setSamples(data))
      .catch(err => console.error('Failed to load sample transactions:', err));
  }, []);

  const handleScore = async (e) => {
    if (e) e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const data = await api.scoreTransaction({
        account_id: parseInt(formData.account_id),
        amount: parseFloat(formData.amount),
        merchant_id: parseInt(formData.merchant_id),
        txn_timestamp: formData.txn_timestamp
      });
      setResult(data);
    } catch (err) {
      setError(err.message || 'Scoring failed');
    } finally {
      setLoading(false);
    }
  };

  const selectSample = (sample) => {
    setFormData({
      account_id: sample.account_id,
      amount: sample.amount,
      merchant_id: sample.merchant_id,
      txn_timestamp: sample.txn_timestamp
    });
    setResult(null);
  };

  return (
    <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '24px' }}>
      {/* Page Header */}
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '1.4rem', fontWeight: 800, color: '#fff', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <SlidersHorizontal size={24} color="#3b82f6" />
          Real-Time Transaction Decision Support
        </h1>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '4px' }}>
          Evaluate single transactions against the historical merchant graph. Computes multi-hop proximity, velocity, and XGBoost fraud probability.
        </p>
      </div>

      {error && (
        <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#fca5a5', padding: '12px', borderRadius: '8px', marginBottom: '20px' }}>
          {error}
        </div>
      )}

      {/* Quick Sample Selector */}
      {samples.length > 0 && (
        <div className="card" style={{ padding: '16px 20px', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-main)' }}>
            <Sparkles size={16} color="#f59e0b" />
            <span>Select a Pre-loaded Transaction to Test (Analyst Benchmark Set):</span>
          </div>
          <div style={{ display: 'flex', gap: '10px', overflowX: 'auto', paddingBottom: '6px' }}>
            {samples.map((s) => (
              <button
                key={s.transaction_id}
                onClick={() => selectSample(s)}
                style={{
                  background: formData.account_id === s.account_id && formData.amount === s.amount ? 'rgba(59, 130, 246, 0.2)' : 'var(--bg-primary)',
                  border: formData.account_id === s.account_id && formData.amount === s.amount ? '1px solid #3b82f6' : '1px solid var(--border-color)',
                  borderRadius: '8px',
                  padding: '8px 12px',
                  textAlign: 'left',
                  cursor: 'pointer',
                  flexShrink: 0
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                  <span className={`badge ${s.is_fraud ? 'badge-danger' : 'badge-success'}`}>
                    {s.is_fraud ? 'Label: Fraud' : 'Label: Normal'}
                  </span>
                  <span style={{ fontSize: '0.78rem', color: '#fff', fontWeight: 600 }}>${s.amount.toFixed(2)}</span>
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  Acc #{s.account_id} • {s.customer_name}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Main Grid: Input Form & Results */}
      <div style={{ display: 'grid', gridTemplateColumns: result ? '380px 1fr' : '500px', gap: '24px' }}>
        {/* Form Panel */}
        <div className="card" style={{ padding: '24px', height: 'fit-content' }}>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '16px' }}>Transaction Parameters</h2>

          <form onSubmit={handleScore} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                Account ID (1 - 999)
              </label>
              <input
                type="number"
                min="1"
                max="999"
                value={formData.account_id}
                onChange={e => setFormData({ ...formData, account_id: e.target.value })}
                className="mono"
                style={{ width: '100%', background: 'var(--bg-primary)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '8px 12px', color: '#fff' }}
                required
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                Transaction Amount ($ USD)
              </label>
              <input
                type="number"
                step="0.01"
                value={formData.amount}
                onChange={e => setFormData({ ...formData, amount: e.target.value })}
                className="mono"
                style={{ width: '100%', background: 'var(--bg-primary)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '8px 12px', color: '#fff' }}
                required
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                Merchant ID
              </label>
              <input
                type="number"
                min="1"
                value={formData.merchant_id}
                onChange={e => setFormData({ ...formData, merchant_id: e.target.value })}
                className="mono"
                style={{ width: '100%', background: 'var(--bg-primary)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '8px 12px', color: '#fff' }}
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                marginTop: '8px',
                background: '#3b82f6',
                color: '#fff',
                padding: '11px',
                borderRadius: '8px',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                cursor: loading ? 'not-allowed' : 'pointer'
              }}
            >
              {loading ? 'Evaluating Graph Features...' : 'Run XGBoost Scoring Model'}
            </button>
          </form>
        </div>

        {/* Results Panel */}
        {result && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Top Score Banner */}
            <div className="card" style={{
              padding: '24px',
              borderLeft: result.risk_label === 'High' ? '6px solid #ef4444' : result.risk_label === 'Medium' ? '6px solid #f59e0b' : '6px solid #10b981',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Model Determination
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '4px' }}>
                  <span style={{ fontSize: '2.2rem', fontWeight: 800, color: '#fff' }}>
                    {(result.fraud_probability * 100).toFixed(1)}%
                  </span>
                  <span className={`badge ${result.risk_label === 'High' ? 'badge-danger' : result.risk_label === 'Medium' ? 'badge-warning' : 'badge-success'}`} style={{ fontSize: '0.9rem', padding: '4px 12px' }}>
                    {result.risk_label} Risk
                  </span>
                </div>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '6px' }}>
                  {result.risk_label === 'High'
                    ? '🚨 High conviction fraud. Transaction matches coordinated syndicate patterns.'
                    : result.risk_label === 'Medium'
                    ? '⚠️ Borderline risk. Manual analyst verification recommended.'
                    : '✅ Clean transaction profile within normal historical spending.'}
                </p>
              </div>

              {/* Action Button: Explore in Ring Explorer */}
              <div>
                <button
                  onClick={() => navigate(`/rings?account=${result.account_id}`)}
                  style={{
                    background: 'rgba(139, 92, 246, 0.2)',
                    border: '1px solid #8b5cf6',
                    color: '#c4b5fd',
                    padding: '10px 16px',
                    borderRadius: '8px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  <Network size={16} />
                  Inspect Syndicate Ring
                </button>
              </div>
            </div>

            {/* Decision Support: Top Explanatory Reasons */}
            <div className="card" style={{ padding: '24px' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Zap size={18} color="#f59e0b" />
                Decision-Support: Top Risk Drivers
              </h3>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {result.top_reasons.map((reason, idx) => (
                  <div
                    key={idx}
                    style={{
                      background: 'var(--bg-primary)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '8px',
                      padding: '12px 16px',
                      display: 'flex',
                      alignItems: 'flex-start',
                      justifyContent: 'space-between',
                      gap: '12px'
                    }}
                  >
                    <div>
                      <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#fff', marginBottom: '2px' }}>
                        {reason.description}
                      </div>
                      <div style={{ fontSize: '0.74rem', color: 'var(--text-dim)' }}>
                        Feature Signal: <code className="mono" style={{ color: 'var(--text-muted)' }}>{reason.feature} = {reason.value}</code>
                      </div>
                    </div>
                    <span className={`badge ${reason.contribution_level === 'Critical' ? 'badge-danger' : reason.contribution_level === 'High' ? 'badge-warning' : 'badge-blue'}`}>
                      {reason.contribution_level} Impact
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Extracted Graph Features Table */}
            <div className="card" style={{ padding: '20px' }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '12px', color: 'var(--text-muted)' }}>
                MongoDB Dynamic Feature Store Snapshot
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', fontSize: '0.8rem' }}>
                <div style={{ background: 'var(--bg-primary)', padding: '10px', borderRadius: '6px' }}>
                  <span style={{ color: 'var(--text-dim)', display: 'block' }}>Hops to Flagged Node:</span>
                  <strong style={{ fontSize: '1rem', color: '#fff' }}>{result.graph_features.hops_to_flagged}</strong>
                </div>
                <div style={{ background: 'var(--bg-primary)', padding: '10px', borderRadius: '6px' }}>
                  <span style={{ color: 'var(--text-dim)', display: 'block' }}>Degree Centrality:</span>
                  <strong style={{ fontSize: '1rem', color: '#fff' }}>{result.graph_features.degree_centrality?.toFixed(4)}</strong>
                </div>
                <div style={{ background: 'var(--bg-primary)', padding: '10px', borderRadius: '6px' }}>
                  <span style={{ color: 'var(--text-dim)', display: 'block' }}>Fraud Neighbors Count:</span>
                  <strong style={{ fontSize: '1rem', color: '#fff' }}>{result.graph_features.prior_fraud_neighbors_count}</strong>
                </div>
                <div style={{ background: 'var(--bg-primary)', padding: '10px', borderRadius: '6px' }}>
                  <span style={{ color: 'var(--text-dim)', display: 'block' }}>Shared Merchants (24h):</span>
                  <strong style={{ fontSize: '1rem', color: '#fff' }}>{result.graph_features.shared_merchant_count_24h}</strong>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

