import type {
  AnalysisResult, ApprovalAction, Candidate, Explanation, GenerationResult,
  Health, KBEntity, ModificationSuggestion, RoleProfile,
} from './types'

// Empty base = same origin (local dev via Vite proxy, or the FastAPI-served build).
// On a split deploy (Vercel frontend + Render backend) set VITE_API_BASE at build time.
const BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '')
const url = (path: string) => BASE + path

async function postForm(path: string, fields: Record<string, string | File>): Promise<unknown> {
  const form = new FormData()
  for (const [k, v] of Object.entries(fields)) form.append(k, v)
  const res = await fetch(url(path), { method: 'POST', body: form })
  if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText)
  return res.json()
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url(path), {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail ?? detail } catch { /* non-json */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => req<Health>('/api/health'),
  sampleJds: () => req<Record<string, string>>('/api/fixtures/jds'),

  seedFixture: () =>
    req<{ candidate_id: number; candidate: Candidate }>(
      '/api/candidates/seed-fixture', { method: 'POST' }),

  getCandidate: (id: number) =>
    req<{ candidate: Candidate; entities: KBEntity[] }>(`/api/candidates/${id}`),

  editCandidate: (id: number, c: Partial<Candidate>) =>
    req<{ candidate: Candidate }>(`/api/candidates/${id}`,
      { method: 'PATCH', body: JSON.stringify(c) }),

  addEntity: (id: number, e: { entity_type: string; name: string; content: string }) =>
    req<KBEntity>(`/api/candidates/${id}/entities`,
      { method: 'POST', body: JSON.stringify(e) }),

  editEntity: (eid: number, patch: Partial<KBEntity>) =>
    req<KBEntity>(`/api/entities/${eid}`,
      { method: 'PATCH', body: JSON.stringify(patch) }),

  deleteEntity: (eid: number) =>
    req<{ deleted: number }>(`/api/entities/${eid}`, { method: 'DELETE' }),

  // Parse résumé text into a (non-persisted) structured profile for review.
  ingestText: (text: string) => postForm('/api/ingest', { text }),

  // Parse an uploaded résumé file (PDF/DOCX/TXT) into a (non-persisted) profile.
  ingestFile: (file: File) => postForm('/api/ingest', { file }),

  // Extract plain text from an uploaded JD file (PDF/DOCX/TXT).
  extractJd: (file: File) =>
    postForm('/api/extract-jd', { file }) as Promise<{ text: string }>,

  // Persist a reviewed profile as the candidate knowledge base.
  createCandidate: (profile: unknown) =>
    req<{ candidate_id: number }>('/api/candidates',
      { method: 'POST', body: JSON.stringify(profile) }),

  analyze: (candidate_id: number, jd_text: string) =>
    req<AnalysisResult>('/api/jobs',
      { method: 'POST', body: JSON.stringify({ candidate_id, jd_text }) }),

  approve: (id: string, action: ApprovalAction, edited_text = '') =>
    req<{ suggestion_id: string; status: string }>(`/api/suggestions/${id}/approve`,
      { method: 'POST', body: JSON.stringify({ action, edited_text }) }),

  plan: (jobId: number) =>
    req<{ suggestions: ModificationSuggestion[] }>(`/api/jobs/${jobId}/plan`),

  generate: (jobId: number) =>
    req<GenerationResult>(`/api/jobs/${jobId}/generate`, { method: 'POST' }),

  explain: (jobId: number, requirement: string) =>
    req<Explanation>(
      `/api/jobs/${jobId}/explain?requirement=${encodeURIComponent(requirement)}`),

  createRoleProfile: (candidateId: number, name: string, job_id: number) =>
    req<RoleProfile>(`/api/candidates/${candidateId}/role-profiles`,
      { method: 'POST', body: JSON.stringify({ name, job_id }) }),

  listRoleProfiles: (candidateId: number) =>
    req<{ role_profiles: RoleProfile[] }>(`/api/candidates/${candidateId}/role-profiles`),

  exportUrl: (jobId: number, fmt: 'pdf' | 'html' | 'md' | 'tex' | 'latex.pdf') =>
    url(`/api/jobs/${jobId}/export.${fmt}`),
}
