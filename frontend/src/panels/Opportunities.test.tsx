import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import Opportunities from './Opportunities'

const json = (data: unknown) => Promise.resolve({ ok: true, json: async () => data } as Response)

const OPP = {
  id: 1, candidate_id: 1, source: 'fixtures', source_url: '', application_url: 'https://x/apply',
  source_refs: [], company: 'Nimbus AI', title: 'AI Engineer Intern', location: 'Remote',
  work_mode: 'remote', employment_type: 'internship', salary: '', description_raw: 'Build RAG.',
  technologies: ['python'], cheap_score: 0.5, match_score: 0.8, opportunity_score: 0.7,
  requirements: null, matches: [], gaps: [], job_id: null, cover_letter: '',
  status: 'ANALYZED', discovered_at: '', closing_date: '',
}

// Stateful stub: opportunities is empty until a discovery run "completes".
function mockApi() {
  let discovered = false
  vi.stubGlobal('fetch', (url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    if (url.endsWith('/preferences'))
      return json({ target_roles: [], target_domains: [], preferred_locations: [],
        remote_preference: 'any', employment_types: [], experience_level: '',
        minimum_match_score: 0, technology_preferences: [], excluded_roles: [],
        excluded_companies: [], sources: [] })
    if (url.includes('/opportunities')) return json({ opportunities: discovered ? [OPP] : [] })
    if (url.endsWith('/batches')) return json({ batches: [] })
    if (url.endsWith('/sources')) return json({ sources: [{ name: 'fixtures',
      configured: true, status: 'AVAILABLE', detail: '', discovered: 8 }] })
    if (url.includes('/discovery/runs') && method === 'POST') { discovered = true; return json({ run_id: 1 }) }
    if (url.includes('/discovery/runs/1'))
      return json({ id: 1, candidate_id: 1, status: 'COMPLETE', stage: 'Done',
        sources_checked: 1, sources_successful: 1, sources_skipped: 0, discovered: 8,
        after_filtering: 7, after_dedup: 6, deeply_analyzed: 6, shortlisted: 1,
        source_health: [], opportunity_ids: [1], error: '' })
    return json({})
  })
}

afterEach(() => vi.unstubAllGlobals())

test('shows a prompt when no candidate is loaded', () => {
  mockApi()
  render(<Opportunities candidateId={null} />)
  expect(screen.getByText('Load your profile first')).toBeInTheDocument()
})

test('mounts, runs a discovery, and shows a ranked result', async () => {
  mockApi()
  render(<Opportunities candidateId={1} />)
  // Discover form actually rendered (component mounted without throwing).
  const button = await screen.findByRole('button', { name: /Discover opportunities/i })

  fireEvent.click(button)

  // Progress panel shows real backend counts, then the result card appears.
  await waitFor(() => expect(screen.getByText('AI Engineer Intern')).toBeInTheDocument())
  expect(screen.getByText('Nimbus AI · Remote · remote')).toBeInTheDocument()
})
