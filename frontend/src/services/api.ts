import axios from 'axios';

// Use a relative base by default so Vite dev server proxy handles `/api` locally.
// `VITE_API_URL` can override this for production builds.
const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});
// Do not attach Authorization header from localStorage; server uses httpOnly cookies.

// Endpoints where a 401 means "wrong credentials", not "expired session" —
// refreshing (and redirecting) on them would wipe the user's error feedback.
const AUTH_EXCLUDED_PATHS = ['/api/auth/login', '/api/auth/register', '/api/auth/refresh'];

let refreshInFlight: Promise<boolean> | null = null;

function clearStoredUser() {
  try {
    localStorage.removeItem('cloudforge_user');
  } catch {
    // ignore
  }
}

/**
 * Hard-navigate to /login on session expiry, but NEVER when we're already
 * there. AuthProvider mounts on /login too and probes /api/auth/me, so an
 * unconditional redirect would reload the page, re-probe, 401 again, and
 * loop forever (visible as the page refreshing and cancelling requests).
 */
function redirectToLogin() {
  if (window.location.pathname !== '/login') {
    window.location.href = '/login';
  }
}

/** Single-flight silent refresh: parallel 401s share one refresh call. */
function tryRefresh(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = api
      .post('/api/auth/refresh')
      .then(() => true)
      .catch(() => false)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

// Handle 401 globally: attempt one silent session refresh and retry the
// original request; only sign out if the refresh itself fails.
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config as (typeof error.config & { _retriedAfterRefresh?: boolean }) | undefined;
    const url: string = config?.url || '';
    const isAuthCall = AUTH_EXCLUDED_PATHS.some((p) => url.includes(p));

    if (error.response?.status === 401 && config && !config._retriedAfterRefresh && !isAuthCall) {
      config._retriedAfterRefresh = true;
      if (await tryRefresh()) {
        return api.request(config);
      }
      clearStoredUser();
      redirectToLogin();
    } else if (error.response?.status === 401 && !isAuthCall) {
      // Retry already happened (or was not possible) and refresh failed.
      clearStoredUser();
      redirectToLogin();
    }
    return Promise.reject(error);
  }
);

// Auth
export const authApi = {
  register: (data: { email: string; username: string; password: string }) =>
    api.post('/api/auth/register', data),
  login: (data: { email: string; password: string }) =>
    api.post('/api/auth/login', data),
  me: () => api.get('/api/auth/me'),
  refresh: () => api.post('/api/auth/refresh'),
  logout: () => api.post('/api/auth/logout'),
};

// Projects
export const projectsApi = {
  list: () => api.get('/api/projects'),
  get: (id: string) => api.get(`/api/projects/${id}`),
  create: (data: { name: string; description?: string; provider: string }) =>
    api.post('/api/projects', data),
  update: (id: string, data: { name?: string; description?: string; status?: string }) =>
    api.put(`/api/projects/${id}`, data),
  delete: (id: string) => api.delete(`/api/projects/${id}`),
};

// Architecture
export const architectureApi = {
  get: (projectId: string) => api.get(`/api/projects/${projectId}/architecture`),
  save: (projectId: string, data: { nodes: any[]; edges: any[]; aws_region?: string }) =>
    api.put(`/api/projects/${projectId}/architecture`, data),
  validate: (projectId: string) => api.post(`/api/projects/${projectId}/validate`),
  security: (projectId: string) => api.get(`/api/projects/${projectId}/security`),
  cost: (projectId: string) => api.get(`/api/projects/${projectId}/cost`),
};

// Terraform
export const terraformApi = {
  generate: (projectId: string) => api.post(`/api/projects/${projectId}/terraform/generate`),
  get: (projectId: string) => api.get(`/api/projects/${projectId}/terraform`),
  plan: (projectId: string) => api.post(`/api/projects/${projectId}/terraform/plan`),
  apply: (projectId: string) => api.post(`/api/projects/${projectId}/terraform/apply`),
  planDestroy: (projectId: string) => api.post(`/api/projects/${projectId}/terraform/plan-destroy`),
  destroy: (projectId: string) => api.post(`/api/projects/${projectId}/terraform/destroy`),
  infrastructure: (projectId: string) => api.get(`/api/projects/${projectId}/terraform/infrastructure`),
  events: (projectId: string) => api.get(`/api/projects/${projectId}/deployment-events`),
  clear: (projectId: string, force?: boolean) =>
    api.delete(`/api/projects/${projectId}/terraform/clear`, {
      params: force ? { force: true } : undefined,
    }),
  power: (projectId: string, address: string, action: 'start' | 'stop') =>
    api.post(`/api/projects/${projectId}/terraform/resources/${encodeURIComponent(address)}/${action}`),
  deployments: (projectId: string) => api.get(`/api/projects/${projectId}/deployments`),
  deploymentLogs: (projectId: string, deploymentId: string, after: number) =>
    api.get(`/api/projects/${projectId}/deployments/${deploymentId}/logs`, { params: { after } }),
  downloadUrl: (projectId: string) => `${API_BASE_URL || ''}/api/projects/${projectId}/terraform/download`,
};

// Live infrastructure (dashboard bulk summary)
export const infrastructureApi = {
  summary: () => api.get('/api/infrastructure'),
};

// Connected cloud accounts (credentials are write-only; never returned)
export const cloudApi = {
  list: () => api.get('/api/cloud/accounts'),
  create: (data: {
    provider: string;
    name: string;
    region: string;
    access_key_id: string;
    secret_access_key: string;
  }) => api.post('/api/cloud/accounts', data),
  remove: (id: string) => api.delete(`/api/cloud/accounts/${id}`),
};

// Advisory AI assistant (provider-agnostic; disabled unless configured)
export const aiApi = {
  status: () => api.get('/api/ai/status'),
  architect: (prompt: string, projectId?: string) =>
    api.post('/api/ai/architect', { prompt, project_id: projectId }),
  explain: (projectId: string) => api.post('/api/ai/explain', { project_id: projectId }),
  troubleshoot: (projectId: string, error: string) =>
    api.post('/api/ai/troubleshoot', { project_id: projectId, error }),
};

export default api;
