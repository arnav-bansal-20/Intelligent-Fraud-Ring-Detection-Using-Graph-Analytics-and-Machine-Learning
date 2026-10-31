const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export async function apiRequest(endpoint, options = {}) {
  const token = localStorage.getItem('fraud_token');
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const url = `${BASE_URL}/api${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    localStorage.removeItem('fraud_token');
    localStorage.removeItem('fraud_user');
    window.location.href = '/login';
    throw new Error('Session expired. Please log in again.');
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const errorMsg = data.detail || `Request failed with status ${response.status}`;
    throw new Error(errorMsg);
  }

  return data;
}

export const api = {
  login: (username, password) =>
    apiRequest('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  getMe: () => apiRequest('/auth/me'),

  // Company Transactions & AI Analysis
  createCompanyTransaction: (payload) =>
    apiRequest('/transactions', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  batchIngestTransactions: (transactions) =>
    apiRequest('/transactions/batch', {
      method: 'POST',
      body: JSON.stringify({ transactions }),
    }),
  getCompanyTransactions: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return apiRequest(`/transactions?${q}`);
  },
  loadDemoCompanyBatch: () =>
    apiRequest('/transactions/demo-batch', {
      method: 'POST',
    }),
  clearCompanyTransactions: () =>
    apiRequest('/transactions/clear', {
      method: 'DELETE',
    }),

  // Scoring
  scoreTransaction: (payload) =>
    apiRequest('/score', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getSampleTransactions: () => apiRequest('/score/sample-transactions'),

  // Alerts
  getAlerts: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return apiRequest(`/alerts?${q}`);
  },
  getAlertDetail: (alertId) => apiRequest(`/alerts/${alertId}`),
  reviewAlert: (alertId, body) =>
    apiRequest(`/alerts/${alertId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  getAlertAudit: (alertId) => apiRequest(`/alerts/${alertId}/audit`),

  // Rings
  getRing: (accountId, hops = 1) => apiRequest(`/rings/${accountId}?hops=${hops}`),

  // Dashboard
  getDashboardMetrics: () => apiRequest('/dashboard/metrics'),
  getBenchmarks: () => apiRequest('/dashboard/benchmarks'),
};

