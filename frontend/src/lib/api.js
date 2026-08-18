import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://blueseatra-api.onrender.com';
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API, timeout: 90000 });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('bs_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Retry automatique sur les erreurs reseau transitoires (aucune reponse HTTP
// recue : blip reseau mobile, defi anti-bot Cloudflare/CDN passager,
// coupure TLS/DNS breve). Ne retente JAMAIS une erreur qui a une reponse HTTP
// (401/404/422/500...) : celles-ci sont deterministes, pas transitoires.
// GET uniquement (les methodes avec effet de bord ne sont jamais retentees
// automatiquement, pour eviter de dupliquer une creation/suppression).
const RETRYABLE_METHODS = new Set(['get', 'head', 'options']);
const MAX_RETRIES = 2;
const RETRY_DELAYS_MS = [500, 1500];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    if (err.response && err.response.status === 401) {
      localStorage.removeItem('bs_token');
      if (!window.location.pathname.startsWith('/login') && !window.location.pathname.startsWith('/signup') && window.location.pathname !== '/') {
        window.location.href = '/login';
      }
      return Promise.reject(err);
    }
    const config = err.config;
    const method = (config?.method || 'get').toLowerCase();
    const isNetworkError = !err.response && err.code !== 'ECONNABORTED';
    if (isNetworkError && config && RETRYABLE_METHODS.has(method)) {
      config.__retryCount = config.__retryCount || 0;
      if (config.__retryCount < MAX_RETRIES) {
        const delay = RETRY_DELAYS_MS[config.__retryCount] || RETRY_DELAYS_MS[RETRY_DELAYS_MS.length - 1];
        config.__retryCount += 1;
        await sleep(delay);
        return api(config);
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
