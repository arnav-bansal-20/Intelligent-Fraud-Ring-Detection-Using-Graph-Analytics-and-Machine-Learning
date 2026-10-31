import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
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
  Sparkles,
  Upload,
  FileSpreadsheet,
  ListOrdered,
  PlusCircle,
  Trash2,
  Search,
  ExternalLink,
  Download,
  FileText,
  X,
  FileUp,
  Check
} from 'lucide-react';

export default function ScoreTransaction() {
  const [activeTab, setActiveTab] = useState('single'); // 'single' | 'batch' | 'history'
  const [searchParams] = useSearchParams();

  // File upload state
  const fileInputRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [filePreview, setFilePreview] = useState([]);
  const [totalFileRows, setTotalFileRows] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [showPasteText, setShowPasteText] = useState(false);

  // Single transaction form state
  const [formData, setFormData] = useState({
    account_number: 'ACC-CORP-201',
    customer_name: 'Metro Retail Enterprises',
    merchant_name: 'Direct Wire Exchange',
    amount: '1250.00',
    txn_timestamp: new Date().toISOString().slice(0, 19),
    notes: ''
  });

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // Batch state
  const [batchCsvText, setBatchCsvText] = useState('');
  const [batchResult, setBatchResult] = useState(null);
  const [batchLoading, setBatchLoading] = useState(false);

  // History state
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const navigate = useNavigate();

  // Load history when tab is clicked
  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const data = await api.getCompanyTransactions({ limit: 100 });
      setHistory(data);
    } catch (err) {
      console.error('Failed to load transaction history:', err);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'history') {
      loadHistory();
    }
  }, [activeTab]);

  // Handle single transaction submit
  const handleSingleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccessMsg('');
    setResult(null);

    try {
      const payload = {
        account_number: formData.account_number.trim(),
        customer_name: formData.customer_name.trim(),
        merchant_name: formData.merchant_name.trim(),
        amount: parseFloat(formData.amount),
        txn_timestamp: formData.txn_timestamp,
        notes: formData.notes.trim() || undefined
      };

      const res = await api.createCompanyTransaction(payload);
      setResult(res);
      setSuccessMsg(`Transaction ${res.trans_num} successfully recorded and analyzed by AI model!`);
    } catch (err) {
      setError(err.message || 'Failed to submit transaction');
    } finally {
      setLoading(false);
    }
  };

  // Handle File Selection (via Picker or Drag & Drop)
  const handleFileChange = (file) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setError('Please select a valid .csv file format.');
      return;
    }
    setError('');
    setSelectedFile(file);

    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target.result;
      setBatchCsvText(text);
      const lines = text.split('\n').filter(l => l.trim().length > 0);
      const isHeader = lines.length > 0 && lines[0].toLowerCase().includes('account');
      const dataLines = isHeader ? lines.slice(1) : lines;
      setTotalFileRows(dataLines.length);

      const previews = [];
      for (let i = 0; i < Math.min(5, dataLines.length); i++) {
        const parts = dataLines[i].split(',').map(p => p.trim().replace(/^["']|["']$/g, ''));
        previews.push({
          account_number: parts[0] || `ACC-${i+1}`,
          customer_name: parts[1] || 'Bank Client',
          merchant_name: parts[2] || 'Counterparty',
          amount: parts[3] || '50.00',
          timestamp: parts[4] || new Date().toISOString().slice(0, 19),
          notes: parts[5] || 'CSV file record'
        });
      }
      setFilePreview(previews);
    };
    reader.readAsText(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  // Submit Uploaded File directly to backend
  const handleUploadFileSubmit = async () => {
    if (!selectedFile) {
      setError('Please select or drag a CSV file first.');
      return;
    }

    setBatchLoading(true);
    setError('');
    setBatchResult(null);

    try {
      const res = await api.uploadTransactionCsv(selectedFile);
      setBatchResult(res);
      setSuccessMsg(`CSV File "${selectedFile.name}" successfully analyzed: ${res.total_ingested} records screened, ${res.alerts_created} alerts generated.`);
    } catch (err) {
      setError(err.message || 'Failed to analyze uploaded CSV file');
    } finally {
      setBatchLoading(false);
    }
  };

  // Download Sample CSV template
  const handleDownloadSampleCsv = () => {
    const csvContent = "account_number,customer_name,merchant_name,amount,timestamp,notes\n" +
      "ACC-CORP-501,Apex Logistics Inc,Direct Wire Exchange,1450.00,2026-10-31T14:30:00,High-value wire transfer\n" +
      "ACC-CORP-502,Beacon Medical Supply,Office Superstore,74.50,2026-10-31T14:35:00,Routine supply order\n" +
      "ACC-CORP-503,Vertex Capital Partners,Global Cloud Hosting,310.00,2026-10-31T14:40:00,Monthly server hosting\n" +
      "ACC-CORP-504,Cascade Energy Corp,Direct Wire Exchange,2800.00,2026-10-31T14:45:00,Urgent vendor payment\n" +
      "ACC-CORP-505,Summit Media Group,City Coffee Roasters,18.75,2026-10-31T14:50:00,Team catering\n";

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', 'sample_company_transactions.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Handle batch CSV parsing
  const handleBatchSubmit = async (e) => {
    e.preventDefault();
    if (!batchCsvText.trim()) {
      setError('Please paste CSV text or load demo batch first.');
      return;
    }

    setBatchLoading(true);
    setError('');
    setBatchResult(null);

    try {
      const lines = batchCsvText.trim().split('\n');
      const transactions = [];

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;
        if (i === 0 && line.toLowerCase().includes('account')) continue;

        const parts = line.split(',').map(p => p.trim().replace(/^["']|["']$/g, ''));
        if (parts.length >= 4) {
          transactions.push({
            account_number: parts[0] || `ACC-${i + 1}`,
            customer_name: parts[1] || 'Bank Client',
            merchant_name: parts[2] || 'Counterparty',
            amount: parseFloat(parts[3]) || 50.0,
            txn_timestamp: parts[4] || new Date().toISOString(),
            notes: parts[5] || 'Batch imported'
          });
        }
      }

      if (transactions.length === 0) {
        throw new Error('No valid CSV rows parsed. Format: account_number, customer_name, merchant_name, amount, [timestamp], [notes]');
      }

      const res = await api.batchIngestTransactions(transactions);
      setBatchResult(res);
      setSuccessMsg(`Batch processed: ${res.total_ingested} transactions analyzed, ${res.alerts_created} alerts generated.`);
    } catch (err) {
      setError(err.message || 'Batch ingestion failed');
    } finally {
      setBatchLoading(false);
    }
  };

  // Handle Load Demo Batch
  const handleLoadDemoBatch = async () => {
    setBatchLoading(true);
    setError('');
    setBatchResult(null);
    try {
      const res = await api.loadDemoCompanyBatch();
      setBatchResult(res);
      setSuccessMsg(`Demo batch loaded: ${res.total_ingested} company transactions analyzed by AI!`);
    } catch (err) {
      setError(err.message || 'Failed to load demo batch');
    } finally {
      setBatchLoading(false);
    }
  };

  // Clear company records
  const handleClearCompanyData = async () => {
    if (!window.confirm('Clear all user-added company transactions and alerts? (Training dataset will remain untouched).')) {
      return;
    }
    try {
      await api.clearCompanyTransactions();
      setHistory([]);
      setResult(null);
      setBatchResult(null);
      setSuccessMsg('All company transactions and alerts cleared.');
    } catch (err) {
      setError(err.message || 'Failed to clear data');
    }
  };

  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '24px' }}>
      {/* Page Header */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="badge badge-blue">Production Intelligence</span>
          <span className="badge badge-purple">XGBoost + Graph Analytics</span>
        </div>
        <h1 style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-main)', marginTop: '6px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <SlidersHorizontal size={24} color="#2563eb" />
          Add Company / Bank Transactions & AI Analysis
        </h1>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '4px' }}>
          Enter or import real company/bank transaction records to run live XGBoost inference and dynamic network proximity analytics.
          Historical training datasets remain segregated exclusively for model governance.
        </p>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '24px', borderBottom: '1px solid var(--border-color)', paddingBottom: '12px' }}>
        <button
          onClick={() => { setActiveTab('single'); setError(''); setSuccessMsg(''); }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 18px',
            borderRadius: '8px',
            fontSize: '0.85rem',
            fontWeight: 600,
            cursor: 'pointer',
            background: activeTab === 'single' ? '#eff6ff' : '#ffffff',
            color: activeTab === 'single' ? '#1d4ed8' : 'var(--text-muted)',
            border: activeTab === 'single' ? '1px solid #bfdbfe' : '1px solid var(--border-color)',
            boxShadow: activeTab === 'single' ? '0 1px 2px 0 rgba(37, 99, 235, 0.05)' : 'none'
          }}
        >
          <PlusCircle size={16} />
          Add Single Transaction
        </button>

        <button
          onClick={() => { setActiveTab('batch'); setError(''); setSuccessMsg(''); }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 18px',
            borderRadius: '8px',
            fontSize: '0.85rem',
            fontWeight: 600,
            cursor: 'pointer',
            background: activeTab === 'batch' ? '#eff6ff' : '#ffffff',
            color: activeTab === 'batch' ? '#1d4ed8' : 'var(--text-muted)',
            border: activeTab === 'batch' ? '1px solid #bfdbfe' : '1px solid var(--border-color)',
            boxShadow: activeTab === 'batch' ? '0 1px 2px 0 rgba(37, 99, 235, 0.05)' : 'none'
          }}
        >
          <Upload size={16} />
          Upload CSV File
        </button>

        <button
          onClick={() => { setActiveTab('history'); setError(''); setSuccessMsg(''); }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 18px',
            borderRadius: '8px',
            fontSize: '0.85rem',
            fontWeight: 600,
            cursor: 'pointer',
            background: activeTab === 'history' ? '#eff6ff' : '#ffffff',
            color: activeTab === 'history' ? '#1d4ed8' : 'var(--text-muted)',
            border: activeTab === 'history' ? '1px solid #bfdbfe' : '1px solid var(--border-color)',
            boxShadow: activeTab === 'history' ? '0 1px 2px 0 rgba(37, 99, 235, 0.05)' : 'none'
          }}
        >
          <ListOrdered size={16} />
          Company Records Log ({history.length})
        </button>
      </div>

      {/* Notifications */}
      {error && (
        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', padding: '12px 16px', borderRadius: '8px', marginBottom: '20px' }}>
          {error}
        </div>
      )}

      {successMsg && (
        <div style={{ background: '#ecfdf5', border: '1px solid #a7f3d0', color: '#047857', padding: '12px 16px', borderRadius: '8px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <CheckCircle2 size={18} />
          <span>{successMsg}</span>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 1: SINGLE TRANSACTION ENTRY                                          */}
      {/* ========================================================================= */}
      {activeTab === 'single' && (
        <div style={{ display: 'grid', gridTemplateColumns: result ? '420px 1fr' : '520px', gap: '24px' }}>
          {/* Form */}
          <div className="card" style={{ padding: '24px' }}>
            <h2 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '6px', color: 'var(--text-main)' }}>
              Company / Bank Transaction Details
            </h2>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '18px' }}>
              Supply transaction fields. The system maps the account and merchant automatically into the network graph.
            </p>

            <form onSubmit={handleSingleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                  Bank Account Number / Identifier
                </label>
                <input
                  type="text"
                  value={formData.account_number}
                  onChange={e => setFormData({ ...formData, account_number: e.target.value })}
                  placeholder="e.g. ACC-CORP-101 or 787"
                  className="mono"
                  style={{ width: '100%', background: '#ffffff', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '9px 12px', color: 'var(--text-main)' }}
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                  Account Holder / Company Customer Name
                </label>
                <input
                  type="text"
                  value={formData.customer_name}
                  onChange={e => setFormData({ ...formData, customer_name: e.target.value })}
                  placeholder="e.g. Acme Corp or Jane Doe"
                  style={{ width: '100%', background: '#ffffff', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '9px 12px', color: 'var(--text-main)' }}
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                  Merchant / Counterparty Store Name
                </label>
                <input
                  type="text"
                  value={formData.merchant_name}
                  onChange={e => setFormData({ ...formData, merchant_name: e.target.value })}
                  placeholder="e.g. Electronics Supercenter or AWS Cloud"
                  style={{ width: '100%', background: '#ffffff', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '9px 12px', color: 'var(--text-main)' }}
                  required
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                    Amount ($ USD)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    value={formData.amount}
                    onChange={e => setFormData({ ...formData, amount: e.target.value })}
                    className="mono"
                    style={{ width: '100%', background: '#ffffff', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '9px 12px', color: 'var(--text-main)' }}
                    required
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                    Date & Time
                  </label>
                  <input
                    type="datetime-local"
                    value={formData.txn_timestamp}
                    onChange={e => setFormData({ ...formData, txn_timestamp: e.target.value })}
                    style={{ width: '100%', background: '#ffffff', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '8px 10px', color: 'var(--text-main)', fontSize: '0.78rem' }}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                  Analyst Notes (Optional)
                </label>
                <textarea
                  rows={2}
                  value={formData.notes}
                  onChange={e => setFormData({ ...formData, notes: e.target.value })}
                  placeholder="e.g. Flagged by internal transaction gateway rule #4"
                  style={{ width: '100%', background: '#ffffff', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '8px 12px', color: 'var(--text-main)', resize: 'vertical' }}
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="btn btn-primary"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  padding: '12px',
                  fontWeight: 700,
                  fontSize: '0.9rem',
                  marginTop: '8px'
                }}
              >
                {loading ? 'Evaluating AI Model & Graph...' : 'Save Record & Run AI Analysis'}
              </button>
            </form>
          </div>

          {/* AI Result Presentation */}
          {result && (
            <div className="card" style={{ padding: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className={`badge ${result.risk_label === 'High' ? 'badge-danger' : result.risk_label === 'Medium' ? 'badge-warning' : 'badge-success'}`}>
                      {result.risk_label} Risk
                    </span>
                    <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                      #{result.trans_num}
                    </span>
                  </div>
                  <h2 style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--text-main)', marginTop: '6px' }}>
                    AI Decision-Support Verdict
                  </h2>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Fraud Probability</div>
                  <div style={{
                    fontSize: '2rem',
                    fontWeight: 800,
                    color: result.fraud_probability >= 0.70 ? '#dc2626' : result.fraud_probability >= 0.30 ? '#d97706' : '#059669'
                  }}>
                    {(result.fraud_probability * 100).toFixed(2)}%
                  </div>
                </div>
              </div>

              {/* Alert Status Banner */}
              {result.alert_id ? (
                <div style={{
                  background: '#fef2f2',
                  border: '1px solid #fecaca',
                  borderRadius: '8px',
                  padding: '12px 16px',
                  marginBottom: '20px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#991b1b', fontSize: '0.85rem' }}>
                    <ShieldAlert size={20} color="#dc2626" />
                    <span><strong>High Risk Alert #{result.alert_id}</strong> automatically created in Analyst Queue.</span>
                  </div>
                  <button
                    onClick={() => navigate('/alerts')}
                    className="btn btn-secondary"
                    style={{ fontSize: '0.78rem', padding: '6px 12px' }}
                  >
                    View in Queue
                  </button>
                </div>
              ) : (
                <div style={{
                  background: '#ecfdf5',
                  border: '1px solid #a7f3d0',
                  borderRadius: '8px',
                  padding: '12px 16px',
                  marginBottom: '20px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  color: '#065f46',
                  fontSize: '0.85rem'
                }}>
                  <CheckCircle2 size={18} color="#059669" />
                  <span>Within normal risk tolerance threshold. Saved to company transaction ledger.</span>
                </div>
              )}

              {/* Explanatory Reasons */}
              <div style={{ marginBottom: '24px' }}>
                <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '12px' }}>
                  Model Decision Factors & Graph Proximity
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {result.top_reasons?.map((reason, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: '#f8fafc',
                        border: '1px solid var(--border-color)',
                        borderRadius: '8px',
                        padding: '12px 16px',
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: '12px'
                      }}
                    >
                      <span className={`badge ${
                        reason.contribution_level === 'Critical' ? 'badge-danger' :
                        reason.contribution_level === 'High' ? 'badge-warning' :
                        reason.contribution_level === 'Moderate' ? 'badge-blue' : 'badge-purple'
                      }`} style={{ flexShrink: 0, marginTop: '2px' }}>
                        {reason.contribution_level}
                      </span>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: '0.82rem', color: 'var(--text-main)', fontWeight: 600 }}>
                          {reason.description}
                        </div>
                        <div className="mono" style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '2px' }}>
                          Feature: {reason.feature} (value: {reason.value})
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Quick Navigation Action Buttons */}
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                <button
                  onClick={() => navigate(`/rings?account=${result.account_id}`)}
                  className="btn btn-secondary"
                  style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 16px' }}
                >
                  <Network size={16} />
                  Inspect Syndicate Ring
                </button>

                <button
                  onClick={() => navigate('/dashboard')}
                  className="btn btn-secondary"
                  style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 16px' }}
                >
                  View Manager Dashboard
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: UPLOAD CSV & BATCH INGESTION                                       */}
      {/* ========================================================================= */}
      {activeTab === 'batch' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <div className="card" style={{ padding: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px', marginBottom: '20px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="badge badge-blue">File Ingestion Engine</span>
                  <span className="badge badge-purple">Point-in-Time Graph Features</span>
                </div>
                <h2 style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-main)', marginTop: '6px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <FileSpreadsheet size={20} color="#2563eb" />
                  Upload Company / Bank Transactions CSV
                </h2>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Select or drag a CSV file with your company/bank records. The system parses headers, extracts multi-hop graph proximity, and scores each transaction with the calibrated XGBoost model.
                </p>
              </div>

              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  onClick={handleDownloadSampleCsv}
                  className="btn btn-secondary"
                  style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px', fontSize: '0.8rem' }}
                >
                  <Download size={15} />
                  Download CSV Template
                </button>

                <button
                  type="button"
                  onClick={handleLoadDemoBatch}
                  disabled={batchLoading}
                  className="btn btn-secondary"
                  style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px', fontSize: '0.8rem', background: '#eff6ff', border: '1px solid #bfdbfe', color: '#1d4ed8' }}
                >
                  <Sparkles size={15} color="#d97706" />
                  Load Bank Demo Batch
                </button>
              </div>
            </div>

            {/* Hidden File Input */}
            <input
              type="file"
              ref={fileInputRef}
              accept=".csv"
              style={{ display: 'none' }}
              onChange={e => {
                if (e.target.files && e.target.files.length > 0) {
                  handleFileChange(e.target.files[0]);
                }
              }}
            />

            {/* Drag & Drop Zone */}
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
              style={{
                border: `2px dashed ${isDragging ? '#2563eb' : selectedFile ? '#059669' : '#cbd5e1'}`,
                borderRadius: '12px',
                padding: '36px 24px',
                textAlign: 'center',
                background: isDragging ? '#eff6ff' : selectedFile ? '#f0fdf4' : '#f8fafc',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                marginBottom: '20px'
              }}
            >
              {selectedFile ? (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
                  <div style={{ padding: '12px', background: '#dcfce7', borderRadius: '50%', color: '#059669' }}>
                    <FileSpreadsheet size={32} />
                  </div>
                  <div>
                    <div style={{ fontSize: '1rem', fontWeight: 700, color: '#065f46' }}>
                      {selectedFile.name}
                    </div>
                    <div style={{ fontSize: '0.8rem', color: '#047857', marginTop: '3px' }}>
                      {(selectedFile.size / 1024).toFixed(1)} KB &bull; ~{totalFileRows} records detected &bull; Click to choose a different file
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }} onClick={e => e.stopPropagation()}>
                    <button
                      type="button"
                      onClick={() => { setSelectedFile(null); setFilePreview([]); setBatchCsvText(''); }}
                      className="btn btn-secondary"
                      style={{ fontSize: '0.78rem', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '6px' }}
                    >
                      <X size={14} /> Remove File
                    </button>
                    <button
                      type="button"
                      onClick={handleUploadFileSubmit}
                      disabled={batchLoading}
                      className="btn btn-primary"
                      style={{ fontSize: '0.82rem', padding: '6px 18px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}
                    >
                      <FileUp size={15} />
                      {batchLoading ? 'Screening Records...' : `Upload & Analyze ${totalFileRows} Records`}
                    </button>
                  </div>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
                  <div style={{ padding: '14px', background: '#eff6ff', borderRadius: '50%', color: '#2563eb' }}>
                    <Upload size={32} />
                  </div>
                  <div>
                    <div style={{ fontSize: '0.98rem', fontWeight: 700, color: 'var(--text-main)' }}>
                      Drag and drop your company transactions CSV file here
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                      or <span style={{ color: '#2563eb', fontWeight: 600, textDecoration: 'underline' }}>browse from your computer</span>
                    </div>
                  </div>
                  <div className="mono" style={{ fontSize: '0.74rem', color: 'var(--text-dim)', background: '#ffffff', padding: '4px 10px', borderRadius: '6px', border: '1px solid var(--border-color)', marginTop: '4px' }}>
                    Columns: account_number, customer_name, merchant_name, amount, [timestamp], [notes]
                  </div>
                </div>
              )}
            </div>

            {/* CSV Data Preview Table */}
            {filePreview.length > 0 && (
              <div style={{ marginBottom: '20px', background: '#ffffff', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <FileText size={16} color="#2563eb" />
                    File Preview (First {filePreview.length} of {totalFileRows} rows)
                  </div>
                  <span className="badge badge-blue">Ready for AI Scoring</span>
                </div>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-color)', textAlign: 'left', color: 'var(--text-muted)', background: '#f8fafc' }}>
                        <th style={{ padding: '8px' }}>Account Number</th>
                        <th style={{ padding: '8px' }}>Customer Name</th>
                        <th style={{ padding: '8px' }}>Merchant / Vendor</th>
                        <th style={{ padding: '8px' }}>Amount</th>
                        <th style={{ padding: '8px' }}>Timestamp</th>
                        <th style={{ padding: '8px' }}>Notes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filePreview.map((row, idx) => (
                        <tr key={idx} style={{ borderBottom: '1px solid var(--border-color)' }}>
                          <td className="mono" style={{ padding: '8px', fontWeight: 600 }}>{row.account_number}</td>
                          <td style={{ padding: '8px' }}>{row.customer_name}</td>
                          <td style={{ padding: '8px' }}>{row.merchant_name}</td>
                          <td className="mono" style={{ padding: '8px', fontWeight: 700 }}>${parseFloat(row.amount || 0).toFixed(2)}</td>
                          <td className="mono" style={{ padding: '8px', color: 'var(--text-dim)' }}>{row.timestamp}</td>
                          <td style={{ padding: '8px', color: 'var(--text-dim)' }}>{row.notes}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Toggleable Text Paste Option */}
            <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '16px', marginTop: '12px' }}>
              <button
                type="button"
                onClick={() => setShowPasteText(!showPasteText)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#2563eb',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: 0
                }}
              >
                {showPasteText ? '− Hide CSV Raw Text Editor' : '+ Or paste raw comma-separated text manually'}
              </button>

              {showPasteText && (
                <form onSubmit={handleBatchSubmit} style={{ marginTop: '14px' }}>
                  <div style={{ marginBottom: '14px' }}>
                    <textarea
                      rows={5}
                      value={batchCsvText}
                      onChange={e => setBatchCsvText(e.target.value)}
                      placeholder={`ACC-BANK-01, Sarah Connor, Whole Foods Market, 45.20\nACC-BANK-02, Marcus Wright, Electronics Depot, 1850.00\nACC-BANK-03, Kyle Reese, Metro Gas Station, 35.00`}
                      className="mono"
                      style={{ width: '100%', background: '#ffffff', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '12px', color: 'var(--text-main)', fontSize: '0.82rem' }}
                    />
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                    <button
                      type="button"
                      onClick={() => setBatchCsvText('')}
                      className="btn btn-secondary"
                      style={{ padding: '8px 16px', fontSize: '0.8rem' }}
                    >
                      Clear Text
                    </button>

                    <button
                      type="submit"
                      disabled={batchLoading}
                      className="btn btn-primary"
                      style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 18px', fontWeight: 700, fontSize: '0.82rem' }}
                    >
                      {batchLoading ? 'Screening Records...' : 'Analyze Pasted Records'}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>

          {/* Batch Ingestion KPI Cards */}
          {batchResult && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                <div className="card" style={{ padding: '18px' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Total Ingested</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--text-main)', marginTop: '4px' }}>
                    {batchResult.total_ingested}
                  </div>
                </div>

                <div className="card" style={{ padding: '18px' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>High Risk Flagged</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#dc2626', marginTop: '4px' }}>
                    {batchResult.high_risk_count}
                  </div>
                </div>

                <div className="card" style={{ padding: '18px' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Alerts Generated</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#d97706', marginTop: '4px' }}>
                    {batchResult.alerts_created}
                  </div>
                </div>

                <div className="card" style={{ padding: '18px' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Normal Activity</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#059669', marginTop: '4px' }}>
                    {batchResult.low_risk_count}
                  </div>
                </div>
              </div>

              {/* Batch Results Table */}
              <div className="card" style={{ padding: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)' }}>
                    Screened Batch Transactions
                  </h3>
                  <button
                    onClick={() => navigate('/alerts')}
                    className="btn btn-secondary"
                    style={{ fontSize: '0.78rem', padding: '6px 12px' }}
                  >
                    Open Alert Queue
                  </button>
                </div>

                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)', textAlign: 'left', background: '#f8fafc' }}>
                        <th style={{ padding: '10px 12px' }}>Trans #</th>
                        <th style={{ padding: '10px 12px' }}>Account</th>
                        <th style={{ padding: '10px 12px' }}>Customer</th>
                        <th style={{ padding: '10px 12px' }}>Merchant</th>
                        <th style={{ padding: '10px 12px' }}>Amount</th>
                        <th style={{ padding: '10px 12px' }}>AI Probability</th>
                        <th style={{ padding: '10px 12px' }}>Risk Label</th>
                        <th style={{ padding: '10px 12px' }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {batchResult.results?.map(tx => (
                        <tr key={tx.transaction_id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                          <td className="mono" style={{ padding: '12px', color: 'var(--text-dim)' }}>
                            {tx.trans_num.slice(0, 16)}...
                          </td>
                          <td className="mono" style={{ padding: '12px', color: 'var(--text-main)', fontWeight: 600 }}>
                            {tx.account_number || `Acc #${tx.account_id}`}
                          </td>
                          <td style={{ padding: '12px', color: 'var(--text-main)' }}>{tx.customer_name}</td>
                          <td style={{ padding: '12px', color: 'var(--text-muted)' }}>{tx.merchant_name}</td>
                          <td className="mono" style={{ padding: '12px', color: 'var(--text-main)', fontWeight: 600 }}>
                            ${tx.amount.toFixed(2)}
                          </td>
                          <td style={{ padding: '12px' }}>
                            <span className="mono" style={{
                              fontWeight: 700,
                              color: tx.fraud_probability >= 0.70 ? '#dc2626' : tx.fraud_probability >= 0.30 ? '#d97706' : '#059669'
                            }}>
                              {(tx.fraud_probability * 100).toFixed(2)}%
                            </span>
                          </td>
                          <td style={{ padding: '12px' }}>
                            <span className={`badge ${tx.risk_label === 'High' ? 'badge-danger' : tx.risk_label === 'Medium' ? 'badge-warning' : 'badge-success'}`}>
                              {tx.risk_label}
                            </span>
                          </td>
                          <td style={{ padding: '12px' }}>
                            <button
                              onClick={() => navigate(`/rings?account=${tx.account_id}`)}
                              className="btn btn-secondary"
                              style={{ padding: '4px 8px', fontSize: '0.72rem' }}
                            >
                              Ring
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: COMPANY TRANSACTION HISTORY                                        */}
      {/* ========================================================================= */}
      {activeTab === 'history' && (
        <div className="card" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '16px' }}>
            <div>
              <h2 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-main)' }}>
                Company / Bank Transaction Ledger
              </h2>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                All user-added company transactions currently recorded in PostgreSQL and indexed in the graph.
              </p>
            </div>

            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                onClick={loadHistory}
                disabled={historyLoading}
                className="btn btn-secondary"
                style={{ fontSize: '0.82rem', padding: '8px 14px' }}
              >
                Refresh Log
              </button>

              <button
                onClick={handleClearCompanyData}
                className="btn btn-secondary"
                style={{ fontSize: '0.82rem', padding: '8px 14px', color: '#dc2626', border: '1px solid #fecaca', background: '#fef2f2' }}
              >
                <Trash2 size={14} style={{ display: 'inline', marginRight: '6px' }} />
                Clear Company Records
              </button>
            </div>
          </div>

          {historyLoading ? (
            <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
              Loading company ledger...
            </div>
          ) : history.length === 0 ? (
            <div style={{
              textAlign: 'center',
              padding: '60px 20px',
              background: '#f8fafc',
              borderRadius: '8px',
              border: '1px dashed var(--border-color)'
            }}>
              <FileSpreadsheet size={40} color="var(--text-dim)" style={{ margin: '0 auto 12px' }} />
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)' }}>No Company Transactions Recorded Yet</h3>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', maxWidth: '420px', margin: '6px auto 16px' }}>
                Add a single transaction in Tab 1 or click below to import a realistic demo bank batch to run AI fraud screening.
              </p>
              <button
                onClick={() => { setActiveTab('batch'); handleLoadDemoBatch(); }}
                className="btn btn-primary"
                style={{ padding: '8px 16px', fontSize: '0.85rem' }}
              >
                Load Realistic Company Demo Batch
              </button>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)', textAlign: 'left', background: '#f8fafc' }}>
                    <th style={{ padding: '10px 12px' }}>Trans #</th>
                    <th style={{ padding: '10px 12px' }}>Account</th>
                    <th style={{ padding: '10px 12px' }}>Customer Name</th>
                    <th style={{ padding: '10px 12px' }}>Merchant</th>
                    <th style={{ padding: '10px 12px' }}>Amount</th>
                    <th style={{ padding: '10px 12px' }}>Timestamp</th>
                    <th style={{ padding: '10px 12px' }}>AI Probability</th>
                    <th style={{ padding: '10px 12px' }}>Risk</th>
                    <th style={{ padding: '10px 12px' }}>Alert</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map(tx => (
                    <tr key={tx.transaction_id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                      <td className="mono" style={{ padding: '12px', color: 'var(--text-dim)' }}>
                        {tx.trans_num.slice(0, 16)}...
                      </td>
                      <td className="mono" style={{ padding: '12px', color: 'var(--text-main)', fontWeight: 600 }}>
                        {tx.account_number || `Acc #${tx.account_id}`}
                      </td>
                      <td style={{ padding: '12px', color: 'var(--text-main)' }}>{tx.customer_name}</td>
                      <td style={{ padding: '12px', color: 'var(--text-muted)' }}>{tx.merchant_name}</td>
                      <td className="mono" style={{ padding: '12px', color: 'var(--text-main)', fontWeight: 600 }}>
                        ${tx.amount.toFixed(2)}
                      </td>
                      <td className="mono" style={{ padding: '12px', color: 'var(--text-dim)', fontSize: '0.75rem' }}>
                        {tx.txn_timestamp}
                      </td>
                      <td style={{ padding: '12px' }}>
                        <span className="mono" style={{
                          fontWeight: 700,
                          color: tx.fraud_probability >= 0.70 ? '#dc2626' : tx.fraud_probability >= 0.30 ? '#d97706' : '#059669'
                        }}>
                          {(tx.fraud_probability * 100).toFixed(2)}%
                        </span>
                      </td>
                      <td style={{ padding: '12px' }}>
                        <span className={`badge ${tx.risk_label === 'High' ? 'badge-danger' : tx.risk_label === 'Medium' ? 'badge-warning' : 'badge-success'}`}>
                          {tx.risk_label}
                        </span>
                      </td>
                      <td style={{ padding: '12px' }}>
                        {tx.alert_id ? (
                          <button
                            onClick={() => navigate('/alerts')}
                            className="badge badge-danger"
                            style={{ cursor: 'pointer', border: 'none' }}
                          >
                            Alert #{tx.alert_id}
                          </button>
                        ) : (
                          <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem' }}>None</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
