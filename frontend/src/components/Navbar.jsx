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
    fontWeight: 600,
    textDecoration: 'none',
    color: isActive ? '#1d4ed8' : 'var(--text-muted)',
    background: isActive ? '#eff6ff' : 'transparent',
    border: isActive ? '1px solid #bfdbfe' : '1px solid transparent',
    transition: 'all 0.15s ease'
  });

  return (
    <nav style={{
      background: 'var(--bg-secondary)',
      borderBottom: '1px solid var(--border-color)',
      boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.04)',
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
        <div style={{ padding: '8px', background: 'rgba(220, 38, 38, 0.1)', borderRadius: '10px', color: '#dc2626' }}>
          <ShieldAlert size={22} />
        </div>
        <div>
          <div style={{ fontSize: '1.1rem', fontWeight: 800, letterSpacing: '-0.02em', color: 'var(--text-main)' }}>
            FraudShield <span style={{ color: '#2563eb', fontWeight: 600, fontSize: '0.85rem' }}>AI Decision-Support</span>
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
            Bank & Company Fraud Intelligence Platform
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <NavLink to="/score" style={navItemStyle}>
          <SlidersHorizontal size={16} />
          Add & Upload CSV
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
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 12px', background: 'var(--bg-primary)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          <User size={15} color="var(--text-muted)" />
          <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-main)' }}>{user?.username}</span>
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
            fontWeight: 500,
            border: '1px solid var(--border-color)',
            background: 'var(--bg-primary)'
          }}
        >
          <LogOut size={15} />
          Sign Out
        </button>
      </div>
    </nav>
  );
}
