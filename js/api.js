/**
 * BuildTrack API Service Layer
 * Replaces LocalStorage DataStore with real Flask API calls.
 * All modules import this via window.ApiService.
 */

(function () {
  'use strict';

  const BASE = new URL('/api', window.location.origin).pathname;

  // -------------------------------------------------------------------------
  // Core fetch helpers
  // -------------------------------------------------------------------------

  async function _request(method, endpoint, body) {
    const opts = {
      method,
      credentials: 'same-origin',
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
    };
    if (body !== undefined) {
      opts.body = JSON.stringify(body);
    }
    const url = endpoint.startsWith('http') ? endpoint : BASE + endpoint;
    let response;
    try {
      response = await fetch(url, opts);
    } catch (networkErr) {
      throw new Error('Network error — is the BuildTrack server running? ' + networkErr.message);
    }
    if (response.status === 204) return null;
    const json = await response.json().catch(() => ({}));
    if (!response.ok) {
      const msg =
        json.error ||
        (typeof json === 'object' ? Object.values(json).join('; ') : response.statusText);
      const err = new Error(msg || `HTTP ${response.status}`);
      err.status = response.status;
      err.data = json;
      if (response.status === 401 && !endpoint.startsWith('/auth/login') && !endpoint.startsWith('/auth/me') && !endpoint.startsWith('/auth/logout')) {
        err.message = 'Your session expired or is no longer valid. Please sign in again.';
        window.dispatchEvent(new CustomEvent('buildtrack:sessionexpired'));
      }
      throw err;
    }
    return json;
  }

  const get = (ep) => _request('GET', ep);
  const post = (ep, body) => _request('POST', ep, body);
  const put = (ep, body) => _request('PUT', ep, body);
  const patch = (ep, body) => _request('PATCH', ep, body);
  const del = (ep) => _request('DELETE', ep);

  // -------------------------------------------------------------------------
  // Auth
  // -------------------------------------------------------------------------

  const auth = {
    login: (email, password) => post('/auth/login', { email, password }),
    logout: () => post('/auth/logout'),
    me: () => get('/auth/me'),
    register: (data) => post('/auth/register', data),
    users: () => get('/auth/users'),
    updateUser: (id, data) => patch(`/auth/users/${id}`, data),
    deleteUser: (id) => del(`/auth/users/${id}`),
    updateMe: (data) => patch('/auth/me', data),
  };

  // -------------------------------------------------------------------------
  // Projects
  // -------------------------------------------------------------------------

  const projects = {
    list: () => get('/projects'),
    get: (id) => get(`/projects/${encodeURIComponent(id)}`),
    create: (data) => post('/projects', data),
    update: (id, data) => patch(`/projects/${encodeURIComponent(id)}`, data),
    delete: (id) => del(`/projects/${encodeURIComponent(id)}`),
  };

  // -------------------------------------------------------------------------
  // Tasks
  // -------------------------------------------------------------------------

  const tasks = {
    list: (projectId) =>
      get('/tasks' + (projectId && projectId !== 'all' ? `?projectId=${projectId}` : '')),
    get: (id) => get(`/tasks/${encodeURIComponent(id)}`),
    create: (data) => post('/tasks', data),
    update: (id, data) => patch(`/tasks/${encodeURIComponent(id)}`, data),
    delete: (id) => del(`/tasks/${encodeURIComponent(id)}`),
  };

  // -------------------------------------------------------------------------
  // Labour / Workers
  // -------------------------------------------------------------------------

  const workers = {
    list: (projectId) =>
      get('/workers' + (projectId && projectId !== 'all' ? `?projectId=${projectId}` : '')),
    get: (id) => get(`/workers/${id}`),
    create: (data) => post('/workers', data),
    update: (id, data) => patch(`/workers/${id}`, data),
    delete: (id) => del(`/workers/${id}`),
  };

  // -------------------------------------------------------------------------
  // Attendance
  // -------------------------------------------------------------------------

  const attendance = {
    get: (date, projectId) => {
      let ep = `/attendance?date=${date}`;
      if (projectId && projectId !== 'all') ep += `&projectId=${projectId}`;
      return get(ep);
    },
    records: (date) => get(`/attendance/records?date=${encodeURIComponent(date)}`),
    save: (date, attendanceMap) => post('/attendance', { date, attendance: attendanceMap }),
    summary: (date, projectId) => {
      let ep = `/attendance/summary?date=${date}`;
      if (projectId && projectId !== 'all') ep += `&projectId=${projectId}`;
      return get(ep);
    },
  };

  // -------------------------------------------------------------------------
  // Materials
  // -------------------------------------------------------------------------

  const materials = {
    list: (projectId) =>
      get('/materials' + (projectId && projectId !== 'all' ? `?projectId=${projectId}` : '')),
    get: (id) => get(`/materials/${id}`),
    create: (data) => post('/materials', data),
    update: (id, data) => patch(`/materials/${id}`, data),
    delete: (id) => del(`/materials/${id}`),
    stockIn: (id, qty, notes, projectId, date) =>
      post(`/materials/${id}/stock-in`, { quantity: qty, notes, projectId, movementDate: date }),
    stockOut: (id, qty, notes, projectId, date) =>
      post(`/materials/${id}/stock-out`, { quantity: qty, notes, projectId, movementDate: date }),
    transactions: (id) => get(`/materials/${id}/transactions`),
    inventorySummary: (projectId) =>
      get('/materials/inventory-summary' + (projectId && projectId !== 'all' ? `?projectId=${projectId}` : '')),
  };

  // -------------------------------------------------------------------------
  // Finance / Expenses
  // -------------------------------------------------------------------------

  const expenses = {
    list: (projectId) =>
      get('/expenses' + (projectId && projectId !== 'all' ? `?projectId=${projectId}` : '')),
    get: (id) => get(`/expenses/${id}`),
    create: (data) => post('/expenses', data),
    update: (id, data) => patch(`/expenses/${id}`, data),
    delete: (id) => del(`/expenses/${id}`),
    summary: (projectId) =>
      get('/expenses/summary' + (projectId && projectId !== 'all' ? `?projectId=${projectId}` : '')),
    chartData: (projectId, startDate, endDate) => {
      let ep = '/expenses/chart-data';
      const params = [];
      if (projectId && projectId !== 'all') params.push(`projectId=${projectId}`);
      if (startDate) params.push(`startDate=${startDate}`);
      if (endDate) params.push(`endDate=${endDate}`);
      if (params.length) ep += '?' + params.join('&');
      return get(ep);
    },
  };

  // -------------------------------------------------------------------------
  // Payments
  // -------------------------------------------------------------------------

  const payments = {
    list: (projectId) =>
      get('/payments' + (projectId && projectId !== 'all' ? `?projectId=${projectId}` : '')),
    get: (id) => get(`/payments/${id}`),
    create: (data) => post('/payments', data),
    update: (id, data) => patch(`/payments/${id}`, data),
    delete: (id) => del(`/payments/${id}`),
  };

  // -------------------------------------------------------------------------
  // Progress / DPR
  // -------------------------------------------------------------------------

  const progress = {
    list: (projectId) =>
      get('/progress' + (projectId && projectId !== 'all' ? `?projectId=${projectId}` : '')),
    get: (id) => get(`/progress/${id}`),
    create: (data) => post('/progress', data),
    update: (id, data) => patch(`/progress/${id}`, data),
    delete: (id) => del(`/progress/${id}`),
  };

  // -------------------------------------------------------------------------
  // Risks
  // -------------------------------------------------------------------------

  const risks = {
    list: (projectId) =>
      get('/risks' + (projectId && projectId !== 'all' ? `?projectId=${projectId}` : '')),
  };

  // -------------------------------------------------------------------------
  // Dashboard
  // -------------------------------------------------------------------------

  const dashboard = {
    stats: (projectId, date) => {
      let ep = '/dashboard/stats';
      const params = [];
      if (projectId && projectId !== 'all') params.push(`projectId=${projectId}`);
      if (date) params.push(`asOfDate=${date}`);
      if (params.length) ep += '?' + params.join('&');
      return get(ep);
    },
    chartData: (projectId) =>
      get('/dashboard/chart-data' + (projectId && projectId !== 'all' ? `?projectId=${projectId}` : '')),
    recent: () => get('/dashboard/recent'),
  };

  // -------------------------------------------------------------------------
  // Reports
  // -------------------------------------------------------------------------

  const reports = {
    get: (type, projectId, date) => {
      let ep = `/reports/${type}`;
      const params = [];
      if (projectId && projectId !== 'all') params.push(`projectId=${projectId}`);
      if (date) params.push(`asOfDate=${date}`);
      if (params.length) ep += '?' + params.join('&');
      return get(ep);
    },
  };

  // -------------------------------------------------------------------------
  // Settings
  // -------------------------------------------------------------------------

  const settings = {
    get: () => get('/settings'),
    update: (data) => patch('/settings', data),
  };

  const demoData = {
    load: () => post('/demo-data', { confirm: true }),
    status: () => get('/demo-data/status'),
    remove: () => _request('DELETE', '/demo-data', { confirm: true }),
  };

  // -------------------------------------------------------------------------
  // Export
  // -------------------------------------------------------------------------

  window.ApiService = {
    auth,
    projects,
    tasks,
    workers,
    attendance,
    materials,
    expenses,
    payments,
    progress,
    risks,
    dashboard,
    reports,
    settings,
    demoData,
    // Convenience shortcuts matching old DataStore interface
    getProjects: () => projects.list().then((r) => r.projects || []),
    getTasks: (pid) => tasks.list(pid).then((r) => r.tasks || []),
    getWorkers: (pid) => workers.list(pid).then((r) => r.workers || []),
    getMaterials: (pid) => materials.list(pid).then((r) => r.materials || []),
    getExpenses: (pid) => expenses.list(pid).then((r) => r.expenses || []),
    getPayments: (pid) => payments.list(pid).then((r) => r.payments || []),
    getProgressReports: (pid) => progress.list(pid).then((r) => r.reports || []),
  };

  console.log('[BuildTrack] ApiService loaded — backend mode active');
})();

