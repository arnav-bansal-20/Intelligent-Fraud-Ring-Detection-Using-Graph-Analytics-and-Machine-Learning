import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  ShieldAlert,
  SlidersHorizontal,
  BellRing,
  Network,
  BarChart3,
  LogOut,
  User
} from 'lucide-react';

export default function Navbar() {
  const { user, logout, hasRole } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItemStyle = ({ isActive }) => ({
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 14px',
    borderRadius: '8px',
    fontSize: '0.85rem',
    fontWeight: 500,
    textDecoration: 'none',
    color: isActive ? '#fff' : 'var(--text-muted)',
    background: isActive ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
    border: isActive ? '1px solid rgba(59, 130, 246, 0.3)' : '1px solid transparent',
    transition: 'all 0.15s ease'
  });

  return (
    <nav style={{
      background: 'var(--bg-secondary)',
      borderBottom: '1px solid var(--border-color)',
      padding: '12px 28px',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      position: 'sticky',
      top: 0,
      zIndex: 100
    }}>
      {/* Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div style={{ padding: '8px', background: 'rgba(239, 68, 68, 0.2)', borderRadius: '10px', color: '#f87171' }}>
          <ShieldAlert size={22} />
        </div>
        <div>
          <div style={{ fontSize: '1.1rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#fff' }}>
            FraudShield <span style={{ color: '#3b82f6', fontWeight: 500, fontSize: '0.85rem' }}>AI Decision-Support</span>
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
            Hybrid DBMS (PostgreSQL + MongoDB) + XGBoost
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <NavLink to="/score" style={navItemStyle}>
          <SlidersHorizontal size={16} />
          Score Transaction
        </NavLink>

        <NavLink to="/alerts" style={navItemStyle}>
          <BellRing size={16} />
          Alert Queue
        </NavLink>

        <NavLink to="/rings" style={navItemStyle}>
          <Network size={16} />
          Ring Explorer
        </NavLink>

        {hasRole(['manager', 'admin']) && (
          <NavLink to="/dashboard" style={navItemStyle}>
            <BarChart3 size={16} />
            Manager Dashboard
          </NavLink>
        )}
      </div>

      {/* User Info & Logout */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 12px', background: 'rgba(255,255,255,0.04)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          <User size={15} color="var(--text-muted)" />
          <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#fff' }}>{user?.username}</span>
          <span className={`badge ${user?.role === 'admin' ? 'badge-danger' : user?.role === 'manager' ? 'badge-purple' : 'badge-blue'}`} style={{ textTransform: 'capitalize' }}>
            {user?.role}
          </span>
        </div>

        <button
          onClick={handleLogout}
          title="Sign out"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '7px 12px',
            borderRadius: '6px',
            color: 'var(--text-muted)',
            fontSize: '0.82rem',
            border: '1px solid var(--border-color)',
            background: 'transparent'
          }}
        >
          <LogOut size={15} />
          Sign Out
        </button>
      </div>
    </nav>
  );
}

