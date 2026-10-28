import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
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

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
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

          {/* Fallback route */}
          <Route path="*" element={<Navigate to="/alerts" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
