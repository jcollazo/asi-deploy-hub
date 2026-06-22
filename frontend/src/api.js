const BASE = '/api';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export const api = {
  // Agencies
  getAgencies: () => request('/agencies'),
  createAgency: (data) => request('/agencies', { method: 'POST', body: JSON.stringify(data) }),

  // Apps
  getApps: () => request('/apps'),
  createApp: (data) => request('/apps', { method: 'POST', body: JSON.stringify(data) }),

  // Releases
  getReleases: (appKey) => request(`/releases${appKey ? `?app_key=${appKey}` : ''}`),
  createRelease: (data) => request('/releases', { method: 'POST', body: JSON.stringify(data) }),
  uploadArtifact: (releaseId, file) => {
    const form = new FormData();
    form.append('file', file);
    return fetch(`${BASE}/releases/${releaseId}/upload`, { method: 'POST', body: form }).then(r => r.json());
  },

  // Deployments
  getDeployments: () => request('/deployments'),
  createDeployment: (data) => request('/deployments', { method: 'POST', body: JSON.stringify(data) }),
  getDeploymentStatus: (id) => request(`/deployments/${id}/status`),
  rollbackDeployment: (id) => request(`/deployments/${id}/rollback`, { method: 'POST' }),

  // Health
  getHealth: () => request('/health'),
};
