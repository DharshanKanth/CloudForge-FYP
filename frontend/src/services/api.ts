import axios from 'axios';

// Use a relative base by default so Vite dev server proxy handles `/api` locally.
// `VITE_API_URL` can override this for production builds.
const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach token to every request
api.interceptors.request.use((config) => {
    withCredentials: true,
    const token = localStorage.getItem('cloudforge_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  } catch (e) {
    // localStorage may be unavailable in some environments (SSR/tests)
  }
  return config;
});

// Handle 401 globally
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('cloudforge_token');
      localStorage.removeItem('cloudforge_user');
      window.location.href = '/login';
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
  save: (projectId: string, data: { nodes: any[]; edges: any[] }) =>
    api.put(`/api/projects/${projectId}/architecture`, data),
  validate: (projectId: string) => api.post(`/api/projects/${projectId}/validate`),
};

// Terraform
export const terraformApi = {
  generate: (projectId: string) => api.post(`/api/projects/${projectId}/terraform/generate`),
  get: (projectId: string) => api.get(`/api/projects/${projectId}/terraform`),
  downloadUrl: (projectId: string) => `${API_BASE_URL || ''}/api/projects/${projectId}/terraform/download`,
};

export default api;

    downloadUrl: (projectId: string) => `${API_BASE_URL || ''}/api/projects/${projectId}/terraform/download`,
