import axios from 'axios';

const getBaseUrl = () => {
  if (typeof window !== 'undefined' && window.location) {
    const hostname = window.location.hostname || 'localhost';
    if (window.location.port === '5173') {
      return `http://${hostname}:8000/api/v1`;
    }
  }
  return '/api/v1';
};

const api = axios.create({
  baseURL: getBaseUrl(),
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('bhoomi_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      const url = error.config?.url || '';
      // Do not redirect or reload if 401 is from /auth/login or /auth/me
      if (!url.includes('/auth/login')) {
        localStorage.removeItem('bhoomi_token');
        localStorage.removeItem('bhoomi_user');
        if (window.location.pathname !== '/login') {
          window.location.replace('/login');
        }
      }
    }
    return Promise.reject(error);
  }
);

export default api;
