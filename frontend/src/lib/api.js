import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://blueseatra-api.onrender.com';
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API, timeout: 90000 });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('bs_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response && err.response.status === 401) {
      localStorage.removeItem('bs_token');
      if (!window.location.pathname.startsWith('/login') && !window.location.pathname.startsWith('/signup') && window.location.pathname !== '/') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(err);
  }
);

export const getToken = () => localStorage.getItem('bs_token');

// Normalize any axios/FastAPI error into a safe display string (handles 422 arrays)
export const apiError = (err, fallback = 'Something went wrong') => {
  if (!err?.response) {
    const msg = (err?.message || '').toLowerCase();
    if (msg.includes('timeout') || err?.code === 'ECONNABORTED') {
      return 'Le serveur met trop de temps à répondre. Réessayez dans quelques secondes.';
    }
    return 'Connexion au serveur impossible. Vérifiez le réseau puis réessayez.';
  }
  const d = err?.response?.data?.detail;
  if (d === undefined || d === null) return err?.message || fallback;
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) {
    return d.map((e) => (typeof e === 'string' ? e : (e?.msg || JSON.stringify(e)))).join(', ') || fallback;
  }
  if (typeof d === 'object') return d.msg || JSON.stringify(d);
  return String(d);
};
