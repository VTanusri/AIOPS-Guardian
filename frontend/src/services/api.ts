const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string; llm_provider: string }>('/health'),
  dashboard: () => request<import('../types').DashboardSummary>('/dashboard/summary'),
  services: () => request<import('../types').ServiceRow[]>('/services'),
  metrics: (params = '') => request<import('../types').Metric[]>(`/metrics${params}`),
  logs: (params = '') => request<import('../types').LogRow[]>(`/logs${params}`),
  traces: () => request<import('../types').TraceRow[]>('/traces'),
  trace: (id: string) => request<import('../types').TraceRow>(`/traces/${id}`),
  anomalies: () => request<any[]>('/anomalies'),
  incidents: () => request<import('../types').Incident[]>('/incidents'),
  incident: (id: string) => request<import('../types').IncidentDetail>(`/incidents/${id}`),
  investigate: (id: string, question?: string) =>
    request(`/incidents/${id}/investigate`, {
      method: 'POST',
      body: JSON.stringify({ question: question || null }),
    }),
  ask: (incident_id: string, question: string) =>
    request('/investigation/ask', {
      method: 'POST',
      body: JSON.stringify({ incident_id, question }),
    }),
  knowledge: () => request<any[]>('/knowledge'),
  knowledgeStatus: () => request<any>('/knowledge/status'),
  reindex: () => request('/knowledge/reindex', { method: 'POST' }),
  ragSearch: (query: string) =>
    request('/rag/search', { method: 'POST', body: JSON.stringify({ query, top_k: 5 }) }),
  scenarios: () => request<{ key: string; name: string; description: string }[]>('/simulation/scenarios'),
  simStatus: () => request<any>('/simulation/status'),
  simStart: (scenario: string) =>
    request('/simulation/start', { method: 'POST', body: JSON.stringify({ scenario }) }),
  simStop: () => request('/simulation/stop', { method: 'POST' }),
  simReset: () => request('/simulation/reset', { method: 'POST' }),
  evaluation: () => request<import('../types').EvaluationMetrics>('/evaluation'),
  githubImport: (url: string, token?: string) =>
    request<any>('/github/import', {
      method: 'POST',
      body: JSON.stringify({ url, token: token || null }),
    }),
  githubProject: () => request<any>('/github/project'),
  githubRefresh: () => request<any>('/github/refresh-signals', { method: 'POST' }),
  githubClear: () => request<any>('/github/clear', { method: 'POST' }),
}

export function subscribeSSE(channel: string, onMessage: (data: any) => void) {
  const es = new EventSource(`/api/stream/${channel}`)
  es.onmessage = (ev) => {
    try {
      onMessage(JSON.parse(ev.data))
    } catch {
      /* ignore */
    }
  }
  return () => es.close()
}
