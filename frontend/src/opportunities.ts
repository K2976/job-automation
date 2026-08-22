import { useCallback, useEffect, useState } from 'react'
import { api } from './api/client'
import type {
  ApplicationBatch, DiscoveryRun, Opportunity, SearchPreferences, SourceHealth,
} from './api/types'

export const EMPTY_PREFS: SearchPreferences = {
  target_roles: [], target_domains: [], preferred_locations: [], remote_preference: 'any',
  employment_types: [], experience_level: '', minimum_match_score: 0,
  technology_preferences: [], excluded_roles: [], excluded_companies: [], sources: [],
}

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))

export interface OppEngine {
  prefs: SearchPreferences
  setPrefs: (p: SearchPreferences) => void
  run: DiscoveryRun | null
  discovering: boolean
  opportunities: Opportunity[]
  selected: number[]
  batches: ApplicationBatch[]
  sources: SourceHealth[]
  busy: string | null
  error: string | null
  discover: () => Promise<void>
  reload: () => Promise<void>
  toggle: (oid: number) => void
  clearSelection: () => void
  prepare: (name: string, max: number) => Promise<ApplicationBatch | null>
  setStatus: (oid: number, status: string) => Promise<void>
}

export function useOpportunities(candidateId: number | null): OppEngine {
  const [prefs, setPrefs] = useState<SearchPreferences>(EMPTY_PREFS)
  const [run, setRun] = useState<DiscoveryRun | null>(null)
  const [discovering, setDiscovering] = useState(false)
  const [opportunities, setOpportunities] = useState<Opportunity[]>([])
  const [selected, setSelected] = useState<number[]>([])
  const [batches, setBatches] = useState<ApplicationBatch[]>([])
  const [sources, setSources] = useState<SourceHealth[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Load saved preferences + any prior opportunities when the candidate changes.
  useEffect(() => {
    if (!candidateId) return
    api.getPreferences(candidateId).then(setPrefs).catch(() => {})
    reload().catch(() => {})
    api.sources(candidateId).then(r => setSources(r.sources)).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candidateId])

  const reload = useCallback(async () => {
    if (!candidateId) return
    const [{ opportunities }, { batches }] = await Promise.all([
      api.listOpportunities(candidateId), api.listBatches(candidateId)])
    setOpportunities(opportunities)
    setBatches(batches)
  }, [candidateId])

  const discover = useCallback(async () => {
    if (!candidateId) return
    setError(null); setDiscovering(true); setRun(null)
    try {
      const { run_id } = await api.startDiscovery(candidateId, prefs)
      // Poll the run; the backend writes real progress as it goes (never faked).
      for (;;) {
        const r = await api.getRun(run_id)
        setRun(r)
        if (r.status !== 'RUNNING') break
        await sleep(1200)
      }
      await reload()
      const s = await api.sources(candidateId)
      setSources(s.sources)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setDiscovering(false)
    }
  }, [candidateId, prefs, reload])

  const toggle = (oid: number) =>
    setSelected(prev => prev.includes(oid) ? prev.filter(x => x !== oid) : [...prev, oid])
  const clearSelection = () => setSelected([])

  const wrap = async (msg: string, fn: () => Promise<void>) => {
    setBusy(msg); setError(null)
    try { await fn() }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); throw e }
    finally { setBusy(null) }
  }

  const prepare = useCallback(async (name: string, max: number) => {
    if (!candidateId || selected.length === 0) return null
    let batch: ApplicationBatch | null = null
    await wrap('Preparing application packages…', async () => {
      batch = await api.createBatch(candidateId, name, max, prefs.target_roles)
      await api.setSelection(batch.id, selected)
      await api.prepareBatch(batch.id)
      await reload()
      setSelected([])
    }).catch(() => {})
    return batch
  }, [candidateId, selected, prefs.target_roles, reload])

  const setStatus = useCallback(async (oid: number, status: string) => {
    await wrap('Updating…', async () => {
      await api.setOpportunityStatus(oid, status)
      await reload()
    }).catch(() => {})
  }, [reload])

  return {
    prefs, setPrefs, run, discovering, opportunities, selected, batches, sources,
    busy, error, discover, reload, toggle, clearSelection, prepare, setStatus,
  }
}
