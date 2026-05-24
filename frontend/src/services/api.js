const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';
const ADMIN_TOKEN_STORAGE_KEY = 'ccp_admin_token';

function getAdminToken() {
  const localToken = localStorage.getItem(ADMIN_TOKEN_STORAGE_KEY);
  const envToken = import.meta.env.VITE_ADMIN_TOKEN || '';
  return localToken || envToken;
}

function setAdminToken(token) {
  const nextToken = token.trim();
  if (nextToken) {
    localStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, nextToken);
  } else {
    localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
  }
}

const initialEnvToken = import.meta.env.VITE_ADMIN_TOKEN;
if (initialEnvToken && !localStorage.getItem(ADMIN_TOKEN_STORAGE_KEY)) {
  setAdminToken(initialEnvToken);
}

async function request(path, options = {}) {
  const adminToken = getAdminToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(adminToken ? { 'X-Admin-Token': adminToken } : {}),
    ...(options.headers || {}),
  };

  const response = await fetch(`${API_BASE}${path}`, {
    headers,
    ...options,
  });

  if (!response.ok) {
    let detail = `Erro ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      detail = response.statusText || detail;
    }
    throw new Error(Array.isArray(detail) ? detail.map((item) => item.msg).join(', ') : detail);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

const json = (method, path, payload) => request(path, {
  method,
  body: payload === undefined ? undefined : JSON.stringify(payload),
});

export const api = {
  getAdminToken,
  setAdminToken,
  listCarrosseis: () => request('/carrosseis'),
  getCarrossel: (id) => request(`/carrosseis/${id}`),
  createCarrossel: (payload) => json('POST', '/carrosseis', payload),
  updateCarrossel: (id, payload) => json('PUT', `/carrosseis/${id}`, payload),
  deleteCarrossel: (id) => request(`/carrosseis/${id}`, { method: 'DELETE' }),
  generate: (id) => json('POST', `/carrosseis/${id}/gerar`),
  regenerate: (id) => json('POST', `/carrosseis/${id}/regenerar`),
  renderSlides: (id, payload) => json('POST', `/carrosseis/${id}/renderizar`, payload),
  generateAsset: (id) => json('POST', `/carrosseis/${id}/assets/gerar`),
  listAssets: (id) => request(`/carrosseis/${id}/assets`),
  deleteAsset: (id) => request(`/assets/${id}`, { method: 'DELETE' }),
  updateSlide: (id, payload) => json('PUT', `/slides/${id}`, payload),
  approve: (id) => json('POST', `/carrosseis/${id}/aprovar`),
  reject: (id) => json('POST', `/carrosseis/${id}/rejeitar`),
  schedule: (id, payload) => json('POST', `/carrosseis/${id}/agendar`, payload),
  reschedule: (id, payload) => json('PUT', `/publicacoes/${id}/reagendar`, payload),
  cancelPublication: (id) => json('POST', `/publicacoes/${id}/cancelar`),
  publishNow: (id) => json('POST', `/carrosseis/${id}/publicar-agora`),
  listPublicacoes: () => request('/publicacoes'),
  listLogs: () => request('/logs'),
};
