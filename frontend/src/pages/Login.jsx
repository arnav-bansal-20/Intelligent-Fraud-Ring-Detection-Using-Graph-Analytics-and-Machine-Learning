import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ShieldCheck, Lock, User, AlertCircle, KeyRound, Sparkles } from 'lucide-react';

export default function Login() {
  const [username, setUsername] = useState('analyst');
  const [password, setPassword] = useState('password123');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/alerts';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(username, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.message || 'Login failed. Please verify credentials.');
    } finally {
      setLoading(false);
    }
  };

  const setDemoUser = (u, p) => {
    setUsername(u);
    setPassword(p);
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px',
      background: 'linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%)'
    }}>
      <div className="card" style={{ width: '100%', maxWidth: '440px', padding: '36px', boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.05)' }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <div style={{
            width: '56px',
            height: '56px',
            borderRadius: '16px',
            background: 'rgba(220, 38, 38, 0.1)',
            border: '1px solid rgba(220, 38, 38, 0.25)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 16px auto',
            color: '#dc2626'
          }}>
            <ShieldCheck size={32} />
          </div>
          <h1 style={{ fontSize: '1.45rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
            FraudShield Portal
          </h1>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Bank Decision-Support & Fraud Ring Investigation
          </p>
        </div>

        {error && (
          <div style={{
            background: '#fef2f2',
            border: '1px solid #fecaca',
            color: '#b91c1c',
            padding: '10px 14px',
            borderRadius: '8px',
            fontSize: '0.82rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            marginBottom: '20px'
          }}>
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '6px' }}>
              Analyst Username
            </label>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              background: '#f8fafc',
              border: '1px solid var(--border-color)',
              borderRadius: '8px',
              padding: '10px 14px',
              gap: '10px'
            }}>
              <User size={16} color="var(--text-dim)" />
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-main)', width: '100%', outline: 'none', fontSize: '0.9rem' }}
                placeholder="Username"
                required
              />
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '6px' }}>
              Password
            </label>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              background: '#f8fafc',
              border: '1px solid var(--border-color)',
              borderRadius: '8px',
              padding: '10px 14px',
              gap: '10px'
            }}>
              <Lock size={16} color="var(--text-dim)" />
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-main)', width: '100%', outline: 'none', fontSize: '0.9rem' }}
                placeholder="Password"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              marginTop: '8px',
              background: '#2563eb',
              color: '#ffffff',
              padding: '12px',
              borderRadius: '8px',
              fontWeight: 600,
              fontSize: '0.9rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              boxShadow: '0 4px 12px rgba(37, 99, 235, 0.25)',
              cursor: loading ? 'not-allowed' : 'pointer'
            }}
          >
            {loading ? 'Authenticating...' : 'Sign In to Investigation Portal'}
          </button>
        </form>

        {/* Quick Demo Credentials */}
        <div style={{ marginTop: '28px', borderTop: '1px solid var(--border-color)', paddingTop: '18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.74rem', color: 'var(--text-dim)', marginBottom: '10px' }}>
            <Sparkles size={14} color="#d97706" />
            <span>Select Demo Role (Password: <code className="mono">password123</code>):</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
            <button
              type="button"
              onClick={() => setDemoUser('analyst', 'password123')}
              className="card"
              style={{
                padding: '8px',
                textAlign: 'center',
                background: username === 'analyst' ? '#eff6ff' : '#f8fafc',
                border: username === 'analyst' ? '1px solid #2563eb' : '1px solid var(--border-color)',
                fontSize: '0.75rem',
                color: 'var(--text-main)'
              }}
            >
              <div style={{ fontWeight: 600 }}>analyst</div>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)' }}>Queue & Triage</div>
            </button>

            <button
              type="button"
              onClick={() => setDemoUser('manager', 'password123')}
              className="card"
              style={{
                padding: '8px',
                textAlign: 'center',
                background: username === 'manager' ? '#f5f3ff' : '#f8fafc',
                border: username === 'manager' ? '1px solid #7c3aed' : '1px solid var(--border-color)',
                fontSize: '0.75rem',
                color: 'var(--text-main)'
              }}
            >
              <div style={{ fontWeight: 600 }}>manager</div>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)' }}>Full + Metrics</div>
            </button>

            <button
              type="button"
              onClick={() => setDemoUser('admin', 'password123')}
              className="card"
              style={{
                padding: '8px',
                textAlign: 'center',
                background: username === 'admin' ? '#fef2f2' : '#f8fafc',
                border: username === 'admin' ? '1px solid #dc2626' : '1px solid var(--border-color)',
                fontSize: '0.75rem',
                color: 'var(--text-main)'
              }}
            >
              <div style={{ fontWeight: 600 }}>admin</div>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)' }}>Full System</div>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
