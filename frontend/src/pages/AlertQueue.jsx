import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import {
  BellRing,
  Search,
  Filter,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Network,
  History,
  X,
  Send,
  UserCheck
} from 'lucide-react';

export default function AlertQueue() {
  const [alerts, setAlerts] = useState([]);
  const [statusFilter, setStatusFilter] = useState('open');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  // Review form state
  const [reviewStatus, setReviewStatus] = useState('reviewing');
  const [decision, setDecision] = useState('Confirmed Fraud Syndicate');
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [activeTab, setActiveTab] = useState('review'); // 'review' | 'audit'

  const navigate = useNavigate();

  const fetchAlerts = async () => {
    try {
      setLoading(true);
      const params = {};
      if (statusFilter !== 'ALL') params.status = statusFilter;
      const data = await api.getAlerts(params);
      setAlerts(data);
      if (data.length > 0 && !selectedAlert) {
        selectAlert(data[0]);
      }
    } catch (err) {
      console.error('Failed to load alerts:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, [statusFilter]);

  const selectAlert = async (alertItem) => {
    setSelectedAlert(alertItem);
    setReviewStatus(alertItem.status);
    setDecision(alertItem.decision || 'Confirmed Fraud Syndicate');
    setNote(alertItem.note || '');
    setActiveTab('review');

    // Load audit trail
    try {
      const logs = await api.getAlertAudit(alertItem.alert_id);
      setAuditLogs(logs);
    } catch (err) {
      console.error('Failed to load audit trail:', err);
    }
  };

  const handleSubmitReview = async (e) => {
    e.preventDefault();
    if (!selectedAlert) return;
    setSubmitting(true);

    try {
      const updated = await api.reviewAlert(selectedAlert.alert_id, {
        status: reviewStatus,
        decision,
        note
      });
      // Update local alerts list
      setAlerts(prev => prev.map(a => a.alert_id === updated.alert_id ? updated : a));
      setSelectedAlert(updated);

      // Refresh audit
      const logs = await api.getAlertAudit(updated.alert_id);
      setAuditLogs(logs);
      alert('Alert decision & audit trail recorded successfully!');
    } catch (err) {
      alert('Failed to save review: ' + err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const filtered = alerts.filter(a => {
    const term = searchTerm.toLowerCase();
    return (
      a.customer_name?.toLowerCase().includes(term) ||
      a.merchant_name?.toLowerCase().includes(term) ||
      String(a.alert_id).includes(term) ||
      String(a.account_id).includes(term)
    );
  });

  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.4rem', fontWeight: 800, color: '#fff', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <BellRing size={24} color="#f87171" />
            Fraud Investigation Alert Queue
          </h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Decision-support workflow: Review high-probability transactions, record determinations, and trace multi-hop syndicate rings.
          </p>
        </div>

        {/* Filter Bar */}
        <div style={{ display: 'flex', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '6px 12px', gap: '8px' }}>
            <Search size={16} color="var(--text-dim)" />
            <input
              type="text"
              placeholder="Search alert, customer, merchant..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              style={{ background: 'transparent', border: 'none', color: '#fff', fontSize: '0.82rem', outline: 'none', width: '220px' }}
            />
          </div>

          <div style={{ display: 'flex', background: 'var(--bg-secondary)', borderRadius: '8px', border: '1px solid var(--border-color)', padding: '2px' }}>
            {['open', 'reviewing', 'closed', 'ALL'].map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                style={{
                  padding: '6px 14px',
                  borderRadius: '6px',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  color: statusFilter === st ? '#fff' : 'var(--text-muted)',
                  background: statusFilter === st ? '#3b82f6' : 'transparent',
                  cursor: 'pointer'
                }}
              >
                {st}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Grid: Alert List + Review Drawer */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 480px', gap: '24px', alignItems: 'flex-start' }}>
        {/* Alerts Table */}
        <div className="card" style={{ padding: '0px', overflow: 'hidden' }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Showing {filtered.length} Prioritized Alerts</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Sorted by Risk Probability</span>
          </div>

          <div style={{ overflowX: 'auto', maxHeight: '720px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)', background: 'rgba(0,0,0,0.1)' }}>
                  <th style={{ padding: '12px' }}>Alert #</th>
                  <th style={{ padding: '12px' }}>Customer / Acc</th>
                  <th style={{ padding: '12px' }}>Merchant</th>
                  <th style={{ padding: '12px' }}>Amount</th>
                  <th style={{ padding: '12px' }}>Probability</th>
                  <th style={{ padding: '12px' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((al) => {
                  const isSelected = selectedAlert?.alert_id === al.alert_id;
                  const probPct = Math.round(al.fraud_probability * 100);

                  return (
                    <tr
                      key={al.alert_id}
                      onClick={() => selectAlert(al)}
                      style={{
                        borderBottom: '1px solid var(--border-color)',
                        background: isSelected ? 'rgba(59, 130, 246, 0.12)' : 'transparent',
                        cursor: 'pointer',
                        transition: 'background 0.15s ease'
                      }}
                    >
                      <td style={{ padding: '12px' }} className="mono">
                        <strong style={{ color: '#fff' }}>AL-{al.alert_id}</strong>
                      </td>
                      <td style={{ padding: '12px' }}>
                        <div style={{ fontWeight: 600, color: '#fff' }}>{al.customer_name}</div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>Acc #{al.account_id}</div>
                      </td>
                      <td style={{ padding: '12px' }}>
                        <div style={{ color: 'var(--text-main)' }}>{al.merchant_name}</div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>{al.txn_timestamp?.split(' ')[0]}</div>
                      </td>
                      <td style={{ padding: '12px', fontWeight: 600 }}>
                        ${al.amount.toFixed(2)}
                      </td>
                      <td style={{ padding: '12px' }}>
                        <span className={`badge ${probPct >= 70 ? 'badge-danger' : probPct >= 30 ? 'badge-warning' : 'badge-success'}`}>
                          {probPct}% ({al.risk_label})
                        </span>
                      </td>
                      <td style={{ padding: '12px' }}>
                        <span className={`badge ${al.status === 'open' ? 'badge-danger' : al.status === 'reviewing' ? 'badge-purple' : 'badge-success'}`} style={{ textTransform: 'uppercase' }}>
                          {al.status}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Selected Alert Decision Drawer */}
        {selectedAlert ? (
          <div className="card" style={{ padding: '24px', position: 'sticky', top: '80px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid var(--border-color)', paddingBottom: '12px' }}>
              <div>
                <span className="mono" style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>ALERT INSPECTION</span>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff' }}>
                  Alert #{selectedAlert.alert_id} • Acc #{selectedAlert.account_id}
                </h3>
              </div>
              <button
                onClick={() => navigate(`/rings?account=${selectedAlert.account_id}`)}
                className="badge badge-purple"
                style={{ padding: '6px 12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
                title="View Connected Accounts"
              >
                <Network size={14} />
                Explore Ring
              </button>
            </div>

            {/* Quick Metadata Box */}
            <div style={{ background: 'var(--bg-primary)', padding: '14px', borderRadius: '8px', border: '1px solid var(--border-color)', marginBottom: '16px', fontSize: '0.8rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div>
                <span style={{ color: 'var(--text-dim)', display: 'block' }}>Customer:</span>
                <strong style={{ color: '#fff' }}>{selectedAlert.customer_name}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-dim)', display: 'block' }}>Amount:</span>
                <strong style={{ color: '#f87171', fontSize: '0.95rem' }}>${selectedAlert.amount.toFixed(2)}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-dim)', display: 'block' }}>Merchant:</span>
                <span style={{ color: '#cbd5e1' }}>{selectedAlert.merchant_name}</span>
              </div>
              <div>
                <span style={{ color: 'var(--text-dim)', display: 'block' }}>Fraud Probability:</span>
                <strong style={{ color: '#f87171' }}>{(selectedAlert.fraud_probability * 100).toFixed(1)}%</strong>
              </div>
            </div>

            {/* Tabs: Decision Form / Audit Trail */}
            <div style={{ display: 'flex', gap: '10px', borderBottom: '1px solid var(--border-color)', marginBottom: '16px' }}>
              <button
                onClick={() => setActiveTab('review')}
                style={{
                  padding: '8px 12px',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  color: activeTab === 'review' ? '#3b82f6' : 'var(--text-muted)',
                  borderBottom: activeTab === 'review' ? '2px solid #3b82f6' : 'none',
                  background: 'none'
                }}
              >
                Analyst Determination
              </button>
              <button
                onClick={() => setActiveTab('audit')}
                style={{
                  padding: '8px 12px',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  color: activeTab === 'audit' ? '#3b82f6' : 'var(--text-muted)',
                  borderBottom: activeTab === 'audit' ? '2px solid #3b82f6' : 'none',
                  background: 'none',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                <History size={14} />
                Audit Trail ({auditLogs.length})
              </button>
            </div>

            {activeTab === 'review' ? (
              <form onSubmit={handleSubmitReview} style={{ display: 'flex', flexDirection: 'column', gap: '14px', fontSize: '0.82rem' }}>
                <div>
                  <label style={{ display: 'block', color: 'var(--text-muted)', marginBottom: '4px' }}>Review Status</label>
                  <select
                    value={reviewStatus}
                    onChange={e => setReviewStatus(e.target.value)}
                    style={{ width: '100%', background: 'var(--bg-primary)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '8px 10px', color: '#fff' }}
                  >
                    <option value="open">OPEN (Pending Review)</option>
                    <option value="reviewing">REVIEWING (Under Active Investigation)</option>
                    <option value="closed">CLOSED (Determination Finalized)</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', color: 'var(--text-muted)', marginBottom: '4px' }}>Fraud Determination</label>
                  <select
                    value={decision}
                    onChange={e => setDecision(e.target.value)}
                    style={{ width: '100%', background: 'var(--bg-primary)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '8px 10px', color: '#fff' }}
                  >
                    <option value="Confirmed Fraud Syndicate">Confirmed Fraud Syndicate</option>
                    <option value="Account Takeover (ATO)">Account Takeover (ATO)</option>
                    <option value="False Positive - Legitimate Spender">False Positive - Legitimate Spender</option>
                    <option value="Escalated for Merchant Investigation">Escalated for Merchant Investigation</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', color: 'var(--text-muted)', marginBottom: '4px' }}>Analyst Investigation Notes</label>
                  <textarea
                    rows={4}
                    value={note}
                    onChange={e => setNote(e.target.value)}
                    placeholder="Document supporting evidence from multi-hop merchant graph, velocity anomaly, or customer corroboration..."
                    style={{ width: '100%', background: 'var(--bg-primary)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '10px', color: '#fff', resize: 'vertical' }}
                    required
                  />
                </div>

                <button
                  type="submit"
                  disabled={submitting}
                  style={{
                    background: '#3b82f6',
                    color: '#fff',
                    padding: '10px',
                    borderRadius: '8px',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    cursor: submitting ? 'not-allowed' : 'pointer'
                  }}
                >
                  <Send size={15} />
                  {submitting ? 'Recording Audit Trail...' : 'Record Decision & Audit Log'}
                </button>
              </form>
            ) : (
              <div style={{ maxHeight: '350px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {auditLogs.length === 0 ? (
                  <div style={{ textAlign: 'center', color: 'var(--text-dim)', padding: '20px', fontSize: '0.8rem' }}>
                    No prior changes recorded. Alert is at initial ingestion state.
                  </div>
                ) : (
                  auditLogs.map((log) => (
                    <div
                      key={log.audit_id}
                      style={{
                        background: 'var(--bg-primary)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '6px',
                        padding: '10px 12px',
                        fontSize: '0.76rem'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', color: 'var(--text-dim)' }}>
                        <span style={{ fontWeight: 600, color: '#fff' }}>{log.changed_by_name || 'System Analyst'}</span>
                        <span className="mono">{log.changed_at?.split('.')[0]}</span>
                      </div>
                      <div>
                        Status: <strong style={{ color: '#cbd5e1' }}>{log.old_status || 'initial'}</strong> → <strong style={{ color: '#3b82f6' }}>{log.new_status}</strong>
                      </div>
                      {log.new_decision && (
                        <div style={{ marginTop: '2px', color: '#94a3b8' }}>
                          Decision: <em>"{log.new_decision}"</em>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="card" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
            Select an alert to inspect details and record decisions.
          </div>
        )}
      </div>
    </div>
  );
}

