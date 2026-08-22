import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App'

const json = (data: unknown) => Promise.resolve({ ok: true, json: async () => data } as Response)

// Minimal fetch router so the app mounts and one real interaction (seed) works.
function mockApi() {
  const candidate = { id: 1, name: 'Sample Candidate', email: '', phone: '',
    location: '', headline: 'Engineer', links: [] }
  vi.stubGlobal('fetch', (url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    if (url.endsWith('/api/health')) return json({ status: 'ok', llm_provider: 'mock', embedding_provider: 'local' })
    if (url.endsWith('/api/fixtures/jds')) return json({ 'Data Engineer': 'JD text' })
    if (url.endsWith('/api/candidates/seed-fixture') && method === 'POST')
      return json({ candidate_id: 1, candidate })
    if (url.endsWith('/api/candidates/1')) return json({ candidate, entities: [] })
    if (url.endsWith('/api/candidates/1/role-profiles')) return json({ role_profiles: [] })
    return json({})
  })
}

afterEach(() => vi.unstubAllGlobals())

test('app renders the workflow shell and start screen', () => {
  mockApi()
  render(<App />)
  expect(screen.getByText('Adaptive Résumé Engineer')).toBeInTheDocument()
  expect(screen.getByText('Use sample candidate')).toBeInTheDocument()
  // all four workflow steps are present
  for (const step of ['Profile', 'Analysis', 'Modifications', 'Résumé'])
    expect(screen.getByText(step)).toBeInTheDocument()
})

test('loading a candidate populates the profile', async () => {
  mockApi()
  render(<App />)
  fireEvent.click(screen.getByText('Use sample candidate'))
  await waitFor(() => expect(screen.getByText('Knowledge base')).toBeInTheDocument())
  expect(screen.getAllByDisplayValue('Sample Candidate').length).toBeGreaterThan(0)
})
