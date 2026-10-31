import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import {
  BellRing,
  Filter,
  CheckCircle2,
  AlertTriangle,
  Clock,
  User,
  ArrowRight,
  ShieldAlert,
  Search,
  ExternalLink,
  ChevronRight
} from 'lucide-react';

export default function AlertQueue() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [statusFilter, setStatusFilter] = useState('open');
  const [searchTerm, setSearchTerm] = useState('');

  // Selected alert for investigation drawer
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [reviewForm, setReviewForm] = useState({
    status: 'closed',
    decision: 'Confirmed Fraud Syndicate',
    note: ''
  });
  const [submitting, setSubmitting] = useState(false);

  const fetchAlerts = async () => {
    setLoading(true);
    setError('');
    try {
      const params = {};
      if (statusFilter && statusFilter !== 'ALL') {
        params.status = statusFilter;
      }
      const data = await api.getAlerts(params);
      setAlerts(data);
      if (data.length > 0 && !selectedAlert) {
        selectAlert(data[0]);
      }
    } catch (err) {
      setError(err.message || 'Failed to fetch alert queue');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, [statusFilter]);

  const selectAlert = async (alertItem) => {
    setSelectedAlert(alertItem);
    setReviewForm({
      status: alertItem.status === 'open' ? 'reviewing' : alertItem.status,
      decision: alertItem.decision || 'Confirmed Fraud Syndicate',
      note: alertItem.note || ''
    });

    try {
      const audit = await api.getAlertAudit(alertItem.alert_id);
      setAuditLogs(audit);
    } catch (err) {
      console.error('Failed to load audit history:', err);
    }
  };

  const handleReviewSubmit = async (e) => {
    e.preventDefault();
    if (!selectedAlert) return;
    setSubmitting(true);

    try {
      const updated = await api.reviewAlert(selectedAlert.alert_id, reviewForm);
      setSelectedAlert(updated);
      setAlerts(prev => prev.map(a => a.alert_id === updated.alert_id ? updated : a));
      const audit = await api.getAlertAudit(selectedAlert.alert_id);
      setAuditLogs(audit);
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
          <h1 style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <BellRing size={24} color="#dc2626" />
            Fraud Investigation Alert Queue
          </h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Decision-support workflow: Review high-probability transactions, record determinations, and trace multi-hop syndicate rings.
          </p>
        </div>

        {/* Filter Bar */}
        <div style={{ display: 'flex', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', background: '#ffffff', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '6px 12px', gap: '8px', boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.03)' }}>
            <Search size={16} color="var(--text-dim)" />
            <input
              type="text"
              placeholder="Search alert, customer, merchant..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              style={{ background: 'transparent', border: 'none', color: 'var(--text-main)', fontSize: '0.82rem', outline: 'none', width: '220px' }}
            />
          </div>

          <div style={{ display: 'flex', background: '#ffffff', borderRadius: '8px', border: '1px solid var(--border-color)', padding: '2px', boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.03)' }}>
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
                  letterSpacing: '0.04em',
                  color: statusFilter === st ? '#ffffff' : 'var(--text-muted)',
                  background: statusFilter === st ? '#2563eb' : 'transparent',
                  transition: 'all 0.15s ease'
                }}
              >
                {st}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', padding: '12px', borderRadius: '8px', marginBottom: '20px' }}>
          {error}
        </div>
      )}

      {/* Main Grid: Queue Table & Inspector Drawer */}
      <div style={{ display: 'grid', gridTemplateColumns: selectedAlert ? '1fr 480px' : '1fr', gap: '24px' }}>
        {/* Alerts Table */}
        <div className="card" style={{ padding: '0px', overflow: 'hidden' }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#ffffff' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-main)' }}>Showing {filtered.length} Prioritized Alerts</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Sorted by Risk Probability</span>
          </div>

          <div style={{ overflowX: 'auto', maxHeight: '720px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)', background: '#f8fafc' }}>
                  <th style={{ padding: '12px' }}>Alert #</th>
                  <th style={{ padding: '12px' }}>Customer / Acc</th>
                  <th style={{ padding: '12px' }}>Merchant</th>
                  <th style={{ padding: '12px' }}>Amount</th>
                  <th style={{ padding: '12px' }}>Probability</th>
                  <th style={{ padding: '12px' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan="6" style={{ textAlign: 'center', padding: '48px 20px', color: 'var(--text-muted)' }}>
                      <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-main)', marginBottom: '6px' }}>No Active Company Alerts</div>
                      <div style={{ fontSize: '0.8rem', maxWidth: '380px', margin: '0 auto 16px' }}>
                        Alerts are dynamically generated when company transactions are evaluated as High Risk (probability ≥ 70%).
                      </div>
                      <a
                        href="/score"
                        className="btn btn-primary"
                        style={{ display: 'inline-block', padding: '8px 16px', fontSize: '0.82rem', textDecoration: 'none' }}
                      >
                        Add & Analyze Company Transactions
                      </a>
                    </td>
                  </tr>
                ) : (
                  filtered.map((al) => {
                    const isSelected = selectedAlert?.alert_id === al.alert_id;
                    const probPct = Math.round(al.fraud_probability * 100);

                    return (
                      <tr
                        key={al.alert_id}
                        onClick={() => selectAlert(al)}
                        style={{
                          borderBottom: '1px solid var(--border-color)',
                          background: isSelected ? '#eff6ff' : 'transparent',
                          cursor: 'pointer',
                          transition: 'background 0.15s ease'
                        }}
                      >
                        <td style={{ padding: '12px' }} className="mono">
                          <strong style={{ color: 'var(--text-main)' }}>AL-{al.alert_id}</strong>
                        </td>
                        <td style={{ padding: '12px' }}>
                          <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>{al.customer_name}</div>
                          <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>Acc #{al.account_id}</div>
                        </td>
                        <td style={{ padding: '12px' }}>
                          <div style={{ color: 'var(--text-main)' }}>{al.merchant_name}</div>
                          <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>{al.txn_timestamp?.split(' ')[0]}</div>
                        </td>
                        <td style={{ padding: '12px', fontWeight: 600, color: 'var(--text-main)' }}>
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
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Selected Alert Decision Drawer */}
        {selectedAlert ? (
          <div className="card" style={{ padding: '24px', position: 'sticky', top: '80px', height: 'fit-content' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid var(--border-color)', paddingBottom: '12px' }}>
              <div>
                <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Alert #{selectedAlert.alert_id}</span>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)' }}>
                  Decision Support Review
                </h3>
              </div>
              <span className={`badge ${selectedAlert.risk_label === 'High' ? 'badge-danger' : 'badge-warning'}`}>
                {Math.round(selectedAlert.fraud_probability * 100)}% Risk
              </span>
            </div>

            {/* Quick Summary Card */}
            <div style={{ background: '#f8fafc', padding: '14px', borderRadius: '8px', border: '1px solid var(--border-color)', marginBottom: '16px', fontSize: '0.8rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div>
                <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.72rem' }}>CUSTOMER</span>
                <strong style={{ color: 'var(--text-main)' }}>{selectedAlert.customer_name}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.72rem' }}>ACCOUNT ID</span>
                <span className="mono" style={{ fontWeight: 600 }}>#{selectedAlert.account_id}</span>
              </div>
              <div>
                <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.72rem' }}>MERCHANT</span>
                <span>{selectedAlert.merchant_name}</span>
              </div>
              <div>
                <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.72rem' }}>TRANSACTION AMT</span>
                <strong style={{ color: '#dc2626' }}>${selectedAlert.amount.toFixed(2)}</strong>
              </div>
            </div>

            {/* 1-Click Ring Inspection Link */}
            <div style={{ marginBottom: '18px' }}>
              <a
                href={`/rings?account=${selectedAlert.account_id}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 14px',
                  background: '#f5f3ff',
                  border: '1px solid #ddd6fe',
                  borderRadius: '8px',
                  color: '#6d28d9',
                  textDecoration: 'none',
                  fontSize: '0.82rem',
                  fontWeight: 600
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <ShieldAlert size={16} />
                  <span>Inspect Account Syndicate Ring (Cytoscape)</span>
                </div>
                <ChevronRight size={16} />
              </a>
            </div>

            {/* Determination & Decision Form */}
            <form onSubmit={handleReviewSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                  Review Status
                </label>
                <select
                  value={reviewForm.status}
                  onChange={e => setReviewForm({ ...reviewForm, status: e.target.value })}
                  style={{ width: '100%', background: '#ffffff', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '8px 10px', color: 'var(--text-main)' }}
                >
                  <option value="open">Open (Keep in queue)</option>
                  <option value="reviewing">In Review (Investigating)</option>
                  <option value="closed">Closed (Resolution Recorded)</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                  Analyst Fraud Determination
                </label>
                <select
                  value={reviewForm.decision}
                  onChange={e => setReviewForm({ ...reviewForm, decision: e.target.value })}
                  style={{ width: '100%', background: '#ffffff', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '8px 10px', color: 'var(--text-main)' }}
                >
                  <option value="Confirmed Fraud Syndicate">Confirmed Fraud Syndicate</option>
                  <option value="Account Takeover (ATO)">Account Takeover (ATO)</option>
                  <option value="Synthetic Identity Ring">Synthetic Identity Ring</option>
                  <option value="False Positive (Legitimate)">False Positive (Legitimate)</option>
                  <option value="Escalated to Compliance / SAR">Escalated to Compliance / SAR</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                  Investigation Notes / Audit Trail
                </label>
                <textarea
                  rows={3}
                  value={reviewForm.note}
                  onChange={e => setReviewForm({ ...reviewForm, note: e.target.value })}
                  placeholder="Record justification and network findings..."
                  style={{ width: '100%', background: '#ffffff', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '10px', color: 'var(--text-main)', resize: 'vertical' }}
                  required
                />
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="btn btn-primary"
                style={{
                  padding: '10px',
                  fontWeight: 600,
                  fontSize: '0.85rem'
                }}
              >
                {submitting ? 'Recording Audit...' : 'Save Decision & Update Audit Trail'}
              </button>
            </form>

            {/* Audit Trail History */}
            {auditLogs.length > 0 && (
              <div style={{ marginTop: '20px', borderTop: '1px solid var(--border-color)', paddingTop: '14px' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase' }}>
                  Historical State Transitions (Trigger-Audited)
                </span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '8px', maxHeight: '180px', overflowY: 'auto' }}>
                  {auditLogs.map((log) => (
                    <div
                      key={log.audit_id}
                      style={{
                        background: '#f8fafc',
                        padding: '8px 12px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-color)',
                        fontSize: '0.72rem'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-dim)' }}>
                        <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>{log.changed_by_name || 'System Analyst'}</span>
                        <span>{log.changed_at?.slice(0, 19).replace('T', ' ')}</span>
                      </div>
                      <div style={{ color: 'var(--text-muted)', marginTop: '2px' }}>
                        Transition: {log.old_status} → <strong>{log.new_status}</strong> ({log.new_decision || 'Pending'})
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
