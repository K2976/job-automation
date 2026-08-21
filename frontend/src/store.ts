import { useCallback, useEffect, useState } from 'react'
import { api } from './api/client'
import type {
  AnalysisResult, ApprovalAction, Candidate, GenerationResult, Health,
  KBEntity, ModificationSuggestion, RoleProfile, Status,
} from './api/types'

export interface Engine {
  health: Health | null
  candidate: Candidate | null
  entities: KBEntity[]
  sampleJds: Record<string, string>
  jdText: string
  analysis: AnalysisResult | null
  suggestions: ModificationSuggestion[]
  generation: GenerationResult | null
  roleProfiles: RoleProfile[]
  step: number
  busy: string | null
  error: string | null

  setStep: (n: number) => void
  setJd: (s: string) => void
  seed: () => Promise<void>
  ingest: (text: string) => Promise<void>
  editCandidate: (patch: Partial<Candidate>) => Promise<void>
  addEntity: (e: { entity_type: string; name: string; content: string }) => Promise<void>
  editEntity: (id: number, patch: Partial<KBEntity>) => Promise<void>
  deleteEntity: (id: number) => Promise<void>
  analyze: () => Promise<void>
  approve: (s: ModificationSuggestion, action: ApprovalAction, edited?: string) => Promise<void>
  generate: () => Promise<void>
  saveRoleProfile: (name: string) => Promise<void>
}

export function useEngine(): Engine {
  const [health, setHealth] = useState<Health | null>(null)
  const [candidate, setCandidate] = useState<Candidate | null>(null)
  const [entities, setEntities] = useState<KBEntity[]>([])
  const [sampleJds, setSampleJds] = useState<Record<string, string>>({})
  const [jdText, setJd] = useState('')
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [suggestions, setSuggestions] = useState<ModificationSuggestion[]>([])
  const [generation, setGeneration] = useState<GenerationResult | null>(null)
  const [roleProfiles, setRoleProfiles] = useState<RoleProfile[]>([])
  const [step, setStep] = useState(0)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.health().then(setHealth).catch(() => {})
    api.sampleJds().then(setSampleJds).catch(() => {})
  }, [])

  const run = useCallback(async (msg: string, fn: () => Promise<void>) => {
    setBusy(msg); setError(null)
    try { await fn() }
    catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setBusy(null) }
  }, [])

  const loadCandidate = useCallback(async (id: number) => {
    const { candidate, entities } = await api.getCandidate(id)
    setCandidate(candidate); setEntities(entities)
    const { role_profiles } = await api.listRoleProfiles(id)
    setRoleProfiles(role_profiles)
  }, [])

  const seed = () => run('Loading sample candidate…', async () => {
    const { candidate_id } = await api.seedFixture()
    await loadCandidate(candidate_id)
  })

  const ingest = (text: string) => run('Parsing résumé & building profile…', async () => {
    const profile = await api.ingestText(text)        // parse into structured profile
    const { candidate_id } = await api.createCandidate(profile)  // persist
    await loadCandidate(candidate_id)                 // candidate can edit afterwards
  })

  const editCandidate = (patch: Partial<Candidate>) =>
    run('Saving…', async () => {
      if (!candidate?.id) return
      const { candidate: c } = await api.editCandidate(candidate.id, patch)
      setCandidate(c)
    })

  const addEntity = (e: { entity_type: string; name: string; content: string }) =>
    run('Adding…', async () => {
      if (!candidate?.id) return
      await api.addEntity(candidate.id, e)
      await loadCandidate(candidate.id)
    })

  const editEntity = (id: number, patch: Partial<KBEntity>) =>
    run('Saving…', async () => {
      await api.editEntity(id, patch)
      if (candidate?.id) await loadCandidate(candidate.id)
    })

  const deleteEntity = (id: number) =>
    run('Removing…', async () => {
      await api.deleteEntity(id)
      if (candidate?.id) await loadCandidate(candidate.id)
    })

  const analyze = () => run('Analyzing JD & retrieving evidence…', async () => {
    if (!candidate?.id || !jdText.trim()) return
    const result = await api.analyze(candidate.id, jdText)
    setAnalysis(result)
    setSuggestions(result.plan.suggestions)
    setGeneration(null)
    setStep(2)
  })

  const approve = (s: ModificationSuggestion, action: ApprovalAction, edited = '') =>
    run('Recording your decision…', async () => {
      if (!candidate?.id) return
      const { status } = await api.approve(s.id, action, edited)
      setSuggestions(prev => prev.map(x =>
        x.id === s.id ? { ...x, status: status as Status, suggested: edited || x.suggested } : x))
      await loadCandidate(candidate.id) // confirmed skills become KB evidence
    })

  const generate = () => run('Generating tailored résumé & validating…', async () => {
    if (!analysis) return
    const g = await api.generate(analysis.job_id)
    setGeneration(g)
    setStep(3)
  })

  const saveRoleProfile = (name: string) => run('Saving role view…', async () => {
    if (!candidate?.id || !analysis) return
    await api.createRoleProfile(candidate.id, name, analysis.job_id)
    const { role_profiles } = await api.listRoleProfiles(candidate.id)
    setRoleProfiles(role_profiles)
  })

  return {
    health, candidate, entities, sampleJds, jdText, analysis, suggestions,
    generation, roleProfiles, step, busy, error,
    setStep, setJd, seed, ingest, editCandidate, addEntity, editEntity, deleteEntity,
    analyze, approve, generate, saveRoleProfile,
  }
}
