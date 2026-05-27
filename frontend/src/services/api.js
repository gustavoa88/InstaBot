const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';
const AUTH_TOKEN_STORAGE_KEY = 'ccp_auth_token';

function getAuthToken() {
  return localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) || '';
}

function setAuthToken(token) {
  if (token) {
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
  } else {
    localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
  }
}

async function request(path, options = {}) {
  const authToken = getAuthToken();
  const { rawResponse = false, ...fetchOptions } = options;
  const headers = {
    'Content-Type': 'application/json',
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
    ...(fetchOptions.headers || {}),
  };

  const response = await fetch(`${API_BASE}${path}`, {
    headers,
    ...fetchOptions,
  });

  if (!response.ok) {
    let detail = `Erro ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      detail = response.statusText || detail;
    }
    if (response.status === 401) setAuthToken('');
    throw new Error(Array.isArray(detail) ? detail.map((item) => item.msg).join(', ') : detail);
  }

  if (response.status === 204) {
    return null;
  }

  if (rawResponse) {
    return response;
  }

  return response.json();
}

const json = (method, path, payload) => request(path, {
  method,
  body: payload === undefined ? undefined : JSON.stringify(payload),
});

async function auth(method, path, payload) {
  const result = await json(method, path, payload);
  setAuthToken(result.access_token);
  return result;
}

export const api = {
  getAuthToken,
  setAuthToken,
  login: (payload) => auth('POST', '/auth/login', payload),
  register: (payload) => auth('POST', '/auth/register', payload),
  me: () => request('/auth/me'),
  logout: () => setAuthToken(''),
  getConfiguracoes: () => request('/configuracoes'),
  saveConfiguracoes: (payload) => json('PUT', '/configuracoes', payload),
  listCarrosseis: () => request('/carrosseis'),
  getCarrossel: (id) => request(`/carrosseis/${id}`),
  createCarrossel: (payload) => json('POST', '/carrosseis', payload),
  updateCarrossel: (id, payload) => json('PUT', `/carrosseis/${id}`, payload),
  deleteCarrossel: (id) => request(`/carrosseis/${id}`, { method: 'DELETE' }),
  generate: (id) => json('POST', `/carrosseis/${id}/gerar`),
  regenerate: (id) => json('POST', `/carrosseis/${id}/regenerar`),
  renderSlides: (id, payload = {}) => json('POST', `/carrosseis/${id}/renderizar`, { ...payload, aspect_ratio: payload.aspect_ratio || '4:5' }),
  generateAsset: (id) => json('POST', `/carrosseis/${id}/assets/gerar`),
  listAssets: (id) => request(`/carrosseis/${id}/assets`),
  deleteAsset: (id) => request(`/assets/${id}`, { method: 'DELETE' }),
  updateSlide: (id, payload) => json('PUT', `/slides/${id}`, payload),
  downloadCarousel: (id) => request(`/carrosseis/${id}/exportar`, { rawResponse: true }),
  listLogs: () => request('/logs'),
};
