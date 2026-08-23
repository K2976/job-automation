import { useCallback, useEffect, useState } from 'react'
import { api } from './api/client'
import type { ApplicationBatch, ApplicationTask, ApprovalMode, Opportunity } from './api/types'

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))
// Statuses that are still moving — keep polling while any task is in one of these.
// CLAIMED matters in remote mode: the server row sits at CLAIMED for the whole run (the
// MacBook worker drives OPENING/FILLING on its own copy and only reports back at the end),
// so without it the live view would freeze the instant a worker picks the task up.
const ACTIVE = new Set(['QUEUED', 'CLAIMED', 'OPENING', 'INSPECTING', 'FILLING'])

export interface AppsEngine {
  batches: ApplicationBatch[]
  tasks: ApplicationTask[]
  opps: Record<number, Opportunity>
  busy: string | null
  error: string | null
  reload: () => Promise<void>
  createTasks: (batchId: number, mode: ApprovalMode) => Promise<void>
  startBatch: (batchId: number) => Promise<void>
  startTask: (taskId: number) => Promise<void>
  approve: (taskId: number) => Promise<void>
  provideAnswers: (taskId: number, answers: Record<string, string>) => Promise<void>
  control: (taskId: number, action: string) => Promise<void>
}

export function useApplications(candidateId: number | null, active = true): AppsEngine {
  const [batches, setBatches] = useState<ApplicationBatch[]>([])
  const [tasks, setTasks] = useState<ApplicationTask[]>([])
  const [opps, setOpps] = useState<Record<number, Opportunity>>({})
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    if (!candidateId) return
    const [{ batches }, { tasks }, { opportunities }] = await Promise.all([
      api.listBatches(candidateId), api.listApplications(candidateId),
      api.listOpportunities(candidateId)])
    setBatches(batches)
    setTasks(tasks)
    setOpps(Object.fromEntries(opportunities.map(o => [o.id, o])))
  }, [candidateId])

  // Reloads on mount AND every time the tab becomes active again — not just once. This
  // panel stays mounted (hidden, not unmounted) once visited so a running discovery poll
  // survives tab switches; without this, a batch created while you were on another tab
  // would never appear here since the one-time mount reload already ran before it existed.
  useEffect(() => { if (active) reload().catch(() => {}) }, [active, reload])

  // Poll while any task is still moving through the browser worker.
  const pollUntilSettled = useCallback(async () => {
    for (let i = 0; i < 20; i++) {
      await reload()
      const active = (await api.listApplications(candidateId!)).tasks
        .some(t => ACTIVE.has(t.status))
      if (!active) break
      await sleep(1000)
    }
  }, [candidateId, reload])

  const wrap = (msg: string, fn: () => Promise<void>) => async () => {
    setBusy(msg); setError(null)
    try { await fn() }
    catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setBusy(null) }
  }

  const createTasks = (batchId: number, mode: ApprovalMode) =>
    wrap('Creating application tasks…', async () => {
      await api.createApplications(batchId, mode); await reload()
    })()
  const startBatch = (batchId: number) =>
    wrap('Running applications…', async () => {
      await api.startBatchApplications(batchId); await pollUntilSettled()
    })()
  const startTask = (taskId: number) =>
    wrap('Running application…', async () => {
      await api.startApplication(taskId); await pollUntilSettled()
    })()
  const approve = (taskId: number) =>
    wrap('Submitting…', async () => {
      await api.approveApplication(taskId); await pollUntilSettled()
    })()
  const provideAnswers = (taskId: number, answers: Record<string, string>) =>
    wrap('Saving answers…', async () => {
      await api.provideAnswers(taskId, answers)
      await api.startApplication(taskId); await pollUntilSettled()
    })()
  const control = (taskId: number, action: string) =>
    wrap('Updating…', async () => { await api.controlApplication(taskId, action); await reload() })()

  return { batches, tasks, opps, busy, error, reload, createTasks, startBatch,
    startTask, approve, provideAnswers, control }
}
