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
      background: 'radial-gradient(ellipse at 50% 20%, #162038 0%, #0a0f1d 70%)'
    }}>
      <div className="card glow-red" style={{ width: '100%', maxWidth: '440px', padding: '36px' }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <div style={{
            width: '56px',
            height: '56px',
            borderRadius: '16px',
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 16px auto',
            color: '#f87171'
          }}>
            <ShieldCheck size={32} />
          </div>
          <h1 style={{ fontSize: '1.45rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.02em' }}>
            FraudShield Portal
          </h1>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Bank Decision-Support & Fraud Ring Investigation
          </p>
        </div>

        {error && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#fca5a5',
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
              background: 'var(--bg-primary)',
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
                style={{ background: 'transparent', border: 'none', color: '#fff', width: '100%', outline: 'none', fontSize: '0.9rem' }}
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
              background: 'var(--bg-primary)',
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
                style={{ background: 'transparent', border: 'none', color: '#fff', width: '100%', outline: 'none', fontSize: '0.9rem' }}
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
              background: '#3b82f6',
              color: '#fff',
              padding: '12px',
              borderRadius: '8px',
              fontWeight: 600,
              fontSize: '0.9rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              boxShadow: '0 4px 12px rgba(59, 130, 246, 0.3)',
              cursor: loading ? 'not-allowed' : 'pointer'
            }}
          >
            {loading ? 'Authenticating...' : 'Sign In to Investigation Portal'}
          </button>
        </form>

        {/* Quick Demo Credentials */}
        <div style={{ marginTop: '28px', borderTop: '1px solid var(--border-color)', paddingTop: '18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.74rem', color: 'var(--text-dim)', marginBottom: '10px' }}>
            <Sparkles size={14} color="#f59e0b" />
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
                background: username === 'analyst' ? 'rgba(59, 130, 246, 0.2)' : 'var(--bg-primary)',
                border: username === 'analyst' ? '1px solid #3b82f6' : '1px solid var(--border-color)',
                fontSize: '0.75rem',
                color: '#fff'
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
                background: username === 'manager' ? 'rgba(139, 92, 246, 0.2)' : 'var(--bg-primary)',
                border: username === 'manager' ? '1px solid #8b5cf6' : '1px solid var(--border-color)',
                fontSize: '0.75rem',
                color: '#fff'
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
                background: username === 'admin' ? 'rgba(239, 68, 68, 0.2)' : 'var(--bg-primary)',
                border: username === 'admin' ? '1px solid #ef4444' : '1px solid var(--border-color)',
                fontSize: '0.75rem',
                color: '#fff'
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

