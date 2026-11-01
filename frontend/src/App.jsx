import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Navbar from './components/Navbar';

import Login from './pages/Login';
import ScoreTransaction from './pages/ScoreTransaction';
import AlertQueue from './pages/AlertQueue';
import RingExplorer from './pages/RingExplorer';
import ManagerDashboard from './pages/ManagerDashboard';

function AppLayout({ children }) {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar />
      <main style={{ flex: 1, paddingBottom: '40px' }}>
        {children}
      </main>
    </div>
  );
}

// Automatically tracks the last visited path & search parameters in localStorage
function RouteTracker() {
  const location = useLocation();

  useEffect(() => {
    if (location.pathname && location.pathname !== '/login') {
      const fullPath = location.pathname + (location.search || '');
      localStorage.setItem('fraud_last_visited', fullPath);
    }
  }, [location]);

  return null;
}

// Redirects to where the user left off, or to appropriate home route
function RootRedirect() {
  const { user } = useAuth();
  const lastVisited = localStorage.getItem('fraud_last_visited');

  if (lastVisited && lastVisited !== '/' && !lastVisited.startsWith('/login')) {
    // If last visited was dashboard, make sure analyst is not restricted
    if (lastVisited.startsWith('/dashboard') && user && user.role === 'analyst') {
      return <Navigate to="/alerts" replace />;
    }
    return <Navigate to={lastVisited} replace />;
  }

  if (user && (user.role === 'manager' || user.role === 'admin')) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Navigate to="/alerts" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <RouteTracker />
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route
            path="/score"
            element={
              <ProtectedRoute>
                <AppLayout>
                  <ScoreTransaction />
                </AppLayout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/alerts"
            element={
              <ProtectedRoute>
                <AppLayout>
                  <AlertQueue />
                </AppLayout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/rings"
            element={
              <ProtectedRoute>
                <AppLayout>
                  <RingExplorer />
                </AppLayout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/dashboard"
            element={
              <ProtectedRoute allowedRoles={['manager', 'admin']}>
                <AppLayout>
                  <ManagerDashboard />
                </AppLayout>
              </ProtectedRoute>
            }
          />

          {/* Root & Fallback routes remember where user left off */}
          <Route path="/" element={<RootRedirect />} />
          <Route path="*" element={<RootRedirect />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
