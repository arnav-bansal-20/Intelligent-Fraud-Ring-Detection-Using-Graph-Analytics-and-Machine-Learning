import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ShieldAlert } from 'lucide-react';

export default function ProtectedRoute({ children, allowedRoles }) {
  const { user, loading, isAuthenticated, hasRole } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div style={{ minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Verifying security session...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && !hasRole(allowedRoles)) {
    return (
      <div className="card" style={{ maxWidth: '500px', margin: '60px auto', padding: '30px', textAlign: 'center' }}>
        <div style={{ padding: '12px', background: 'rgba(239, 68, 68, 0.15)', borderRadius: '12px', display: 'inline-block', marginBottom: '16px' }}>
          <ShieldAlert size={36} color="#ef4444" />
        </div>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '8px' }}>Access Restricted</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '20px' }}>
          This section is restricted to <strong>{allowedRoles.join(', ')}</strong> roles. Your current account role is <strong>{user?.role}</strong>.
        </p>
        <button
          onClick={() => window.history.back()}
          style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', color: '#fff', padding: '8px 16px', borderRadius: '6px' }}
        >
          Go Back
        </button>
      </div>
    );
  }

  return children;
}

