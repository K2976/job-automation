import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import Applications from './Applications'

const json = (data: unknown) => Promise.resolve({ ok: true, json: async () => data } as Response)

const BATCH = { id: 1, candidate_id: 1, name: 'Batch A', max_opportunities: 2,
  target_roles: [], opportunity_ids: [1], status: 'READY', created_at: '',
  approval_mode: 'REVIEW_BEFORE_SUBMIT' }
const OPP = { id: 1, title: 'AI Engineer Intern', company: 'Nimbus AI' }

function mockApi() {
  let created = false
  let status = 'READY'
  vi.stubGlobal('fetch', (url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    if (url.endsWith('/batches') && method === 'GET') return json({ batches: [BATCH] })
    if (url.endsWith('/opportunities')) return json({ opportunities: [OPP] })
    if (url.endsWith('/applications') && method === 'GET' && url.includes('/candidates/'))
      return json({ tasks: created ? [{ id: 9, opportunity_id: 1, batch_id: 1, status,
        approval_mode: 'REVIEW_BEFORE_SUBMIT', questions: [], logs: [], retry_count: 0 }] : [] })
    if (url.endsWith('/applications') && method === 'POST') {
      created = true; status = 'READY'
      return json({ tasks: [{ id: 9 }], count: 1, max_opportunities: 2 })
    }
    if (url.includes('/start')) { status = 'REVIEW_REQUIRED'; return json({ task_id: 9 }) }
    return json({})
  })
}

afterEach(() => vi.unstubAllGlobals())

test('prompts to load a profile when none', () => {
  mockApi()
  render(<Applications candidateId={null} />)
  expect(screen.getByText('Load your profile first')).toBeInTheDocument()
})

test('mounts, creates tasks, and shows the queue', async () => {
  mockApi()
  render(<Applications candidateId={1} />)
  const create = await screen.findByRole('button', { name: /Create tasks/i })
  fireEvent.click(create)
  // Task queue appears with the opportunity label.
  await waitFor(() => expect(screen.getByText(/AI Engineer Intern/)).toBeInTheDocument())
})
