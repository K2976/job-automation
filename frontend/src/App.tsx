import { useEngine } from './store'
import { Alert, Loading, icons } from './ui'
import Profile from './panels/Profile'
import Analysis from './panels/Analysis'
import Modifications from './panels/Modifications'
import Resume from './panels/Resume'

const STEPS = [
  { label: 'Profile', title: 'Candidate profile',
    desc: 'Your master résumé, kept as a knowledge base the tailoring reasons over.' },
  { label: 'Analysis', title: 'Job analysis',
    desc: 'How your experience matches a target role — with the evidence behind every call.' },
  { label: 'Modifications', title: 'Suggested changes',
    desc: 'Review each change. Nothing reaches your résumé until you accept it.' },
  { label: 'Résumé', title: 'Tailored résumé',
    desc: 'Your role-specific résumé, validated against your real evidence.' },
]

export function Shell({ engine }: { engine: ReturnType<typeof useEngine> }) {
  const { step, candidate, analysis } = engine
  const done = [!!candidate, !!analysis, !!engine.generation, false]
  const enabled = [true, !!candidate, !!analysis, !!analysis]
  const Panel = [Profile, Analysis, Modifications, Resume][step]
  const wide = step === 3

  return (
    <div className="min-h-full overflow-x-hidden">
      <TopBar engine={engine} />
      <Stepper step={step} done={done} enabled={enabled} onGo={engine.setStep} />

      <main className={`mx-auto w-full px-6 py-8 ${wide ? 'max-w-[1320px]' : 'max-w-[1120px]'}`}>
        <header className="mb-7">
          <h1 className="text-[30px] font-bold tracking-tight text-ink">{STEPS[step].title}</h1>
          <p className="mt-1 text-[16px] text-muted">{STEPS[step].desc}</p>
        </header>

        {engine.busy && <div className="mb-5"><Loading label={engine.busy} /></div>}
        {engine.error &&
          <div className="mb-5">
            <Alert title="Something went wrong">{engine.error}</Alert>
          </div>}

        <Panel engine={engine} />
      </main>
    </div>
  )
}

function TopBar({ engine }: { engine: ReturnType<typeof useEngine> }) {
  return (
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex h-14 max-w-[1320px] items-center gap-3 px-6">
        <div className="flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-md bg-accent text-white">
            <icons.mark className="text-[16px]" />
          </span>
          <span className="text-[16px] font-semibold tracking-tight text-ink">
            Adaptive Résumé Engineer
          </span>
        </div>
        <div className="ml-auto flex items-center gap-4 text-[13px] text-muted">
          {engine.candidate &&
            <span className="hidden sm:inline">{engine.candidate.name}</span>}
          {engine.roleProfiles.length > 0 &&
            <span className="hidden rounded-full bg-raised px-2.5 py-1 md:inline">
              {engine.roleProfiles.length} saved view{engine.roleProfiles.length > 1 ? 's' : ''}
            </span>}
          {engine.health &&
            <span className="font-mono text-[12px] text-faint">
              {engine.health.llm_provider}
            </span>}
        </div>
      </div>
    </header>
  )
}

function Stepper({ step, done, enabled, onGo }:
  { step: number; done: boolean[]; enabled: boolean[]; onGo: (n: number) => void }) {
  return (
    <nav className="border-b border-line bg-surface" aria-label="Progress">
      <ol className="mx-auto flex max-w-[1320px] items-center gap-1 px-4 py-2.5 sm:gap-2 sm:px-6">
        {STEPS.map((s, i) => {
          const current = step === i
          const complete = done[i] && !current
          return (
            <li key={s.label} className="flex items-center">
              <button
                onClick={() => enabled[i] && onGo(i)}
                disabled={!enabled[i]}
                aria-current={current ? 'step' : undefined}
                className={`group flex items-center gap-2 rounded-md px-2.5 py-1.5 text-[14px] transition-colors
                  ${current ? 'text-ink' : enabled[i] ? 'text-muted hover:bg-raised' : 'text-faint cursor-not-allowed'}`}>
                <span className={`grid h-6 w-6 shrink-0 place-items-center rounded-full font-mono text-[12px]
                  ${current ? 'bg-accent text-white'
                    : complete ? 'bg-accent-soft text-accent'
                    : 'border border-line-strong text-faint'}`}>
                  {complete ? <icons.check /> : i + 1}
                </span>
                <span className={`font-medium ${current ? '' : 'hidden sm:inline'}`}>{s.label}</span>
              </button>
              {i < STEPS.length - 1 &&
                <span className="mx-0.5 h-px w-4 bg-line-strong sm:w-8" aria-hidden="true" />}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

export default function App() {
  const engine = useEngine()
  return <Shell engine={engine} />
}
