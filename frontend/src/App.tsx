import { useEngine } from './store'
import { Badge, ErrorNote, Spinner } from './ui'
import Profile from './panels/Profile'
import Analysis from './panels/Analysis'
import Modifications from './panels/Modifications'
import Resume from './panels/Resume'

const STEPS = ['Profile', 'Analysis', 'Modifications', 'Résumé']

export default function App() {
  const engine = useEngine()
  const { step, candidate, analysis, generation } = engine

  const enabled = [true, !!candidate, !!analysis, !!analysis]
  const Panel = [Profile, Analysis, Modifications, Resume][step]

  return (
    <div className="min-h-full">
      <header className="border-b border-slate-800 px-6 py-3">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3">
          <h1 className="text-lg font-semibold">Adaptive Résumé Engineer</h1>
          {engine.health && (
            <span className="text-xs text-slate-500">
              LLM: <b className="text-slate-300">{engine.health.llm_provider}</b> ·
              embeddings: {engine.health.embedding_provider}
            </span>
          )}
          <div className="ml-auto flex items-center gap-3 text-xs text-slate-400">
            {candidate && <span>{candidate.name}</span>}
            {engine.roleProfiles.length > 0 &&
              <span className="rounded bg-slate-700/50 px-2 py-0.5">
                {engine.roleProfiles.length} role view{engine.roleProfiles.length > 1 ? 's' : ''}
              </span>}
          </div>
        </div>
      </header>

      <nav className="border-b border-slate-800 px-6">
        <div className="mx-auto flex max-w-6xl gap-1">
          {STEPS.map((label, i) => (
            <button key={label} disabled={!enabled[i]} onClick={() => engine.setStep(i)}
              className={`border-b-2 px-3 py-2 text-sm transition disabled:opacity-30
                ${step === i ? 'border-sky-500 text-sky-300'
                  : 'border-transparent text-slate-400 hover:text-slate-200'}`}>
              <span className="mr-1 text-xs text-slate-500">{i + 1}</span>{label}
              {i === 3 && generation && <span className="ml-1 text-emerald-400">•</span>}
            </button>
          ))}
        </div>
      </nav>

      <main className="mx-auto max-w-6xl px-6 py-5">
        {engine.busy && <div className="mb-3"><Spinner label={engine.busy} /></div>}
        {engine.error && <div className="mb-3"><ErrorNote message={engine.error} /></div>}
        <Panel engine={engine} />
      </main>

      <footer className="mx-auto max-w-6xl px-6 py-6 text-xs text-slate-600">
        JD-alignment scores are product indicators, not a guaranteed ATS result.
        {' '}Provenance <Badge status="ORIGINAL" /> <Badge status="USER_CONFIRMED" /> is preserved end-to-end.
      </footer>
    </div>
  )
}
