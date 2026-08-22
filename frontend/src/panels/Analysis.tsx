import { useState } from 'react'
import { api } from '../api/client'
import type { Engine } from '../store'
import type { MatchStatus, RequirementMatch } from '../api/types'
import { Badge, Button, EmptyState, SectionHeader, Surface, icons } from '../ui'

const GROUPS: { key: MatchStatus[]; title: string; hint: string }[] = [
  { key: ['STRONG_MATCH'], title: 'Strong matches', hint: 'Clearly evidenced in your profile.' },
  { key: ['PARTIAL_MATCH', 'WEAK_MATCH'], title: 'Partial matches', hint: 'Related experience — worth reframing.' },
  { key: ['USER_CONFIRMATION_REQUIRED'], title: 'Needs your confirmation', hint: 'Only include if it genuinely applies.' },
  { key: ['MISSING'], title: 'Gaps', hint: 'No supporting evidence — not invented.' },
]

function JdInput({ engine }: { engine: Engine }) {
  return (
    <Surface className="p-5">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="mr-1 text-[14px] text-muted">Start from a sample:</span>
        {Object.entries(engine.sampleJds).map(([role, text]) => (
          <Button key={role} size="sm" variant="secondary" onClick={() => engine.setJd(text)}>{role}</Button>
        ))}
        <label className="inline-flex h-8 cursor-pointer items-center gap-2 rounded-md border border-line-strong px-3 text-[14px] text-ink-soft hover:bg-raised sm:ml-auto">
          <icons.upload /> Upload JD file
          <input type="file" accept=".pdf,.docx,.txt,.md" className="hidden"
            onChange={async e => { const f = e.target.files?.[0]; if (f) { const { text } = await api.extractJd(f); engine.setJd(text) } }} />
        </label>
      </div>
      <label htmlFor="jd" className="mb-1.5 block text-[15px] font-medium text-ink">Job description</label>
      <textarea id="jd" value={engine.jdText} onChange={e => engine.setJd(e.target.value)}
        rows={9} placeholder="Paste the job description here…"
        className="w-full resize-y rounded-md border border-line-strong bg-surface px-3.5 py-3 text-[15px] leading-relaxed
          placeholder:text-faint focus:border-accent focus:outline-none" />
      <div className="mt-3 flex items-center gap-3">
        <Button disabled={!engine.candidate || !engine.jdText.trim()} icon={icons.arrowRight}
          onClick={engine.analyze}>Analyze job</Button>
        {!engine.candidate && <span className="text-[14px] text-muted">Load a candidate first.</span>}
      </div>
    </Surface>
  )
}

function EvidenceChain({ m }: { m: RequirementMatch }) {
  return (
    <div className="space-y-4">
      <div>
        <div className="font-mono text-[12px] uppercase tracking-wider text-accent">Requirement</div>
        <div className="mt-0.5 text-[17px] font-semibold text-ink">{m.requirement}</div>
        <div className="mt-1"><Badge status={m.match_status} /></div>
      </div>
      <Step label="Why">
        <p className="text-[15px] leading-relaxed text-ink-soft">{m.reason}</p>
      </Step>
      <Step label="Evidence" last>
        {m.evidence.length === 0
          ? <p className="text-[15px] text-muted">No supporting evidence in your profile.</p>
          : <ul className="space-y-2">
              {m.evidence.map((e, i) => (
                <li key={i} className="rounded-md border border-line bg-paper px-3 py-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[15px] font-medium text-ink">{e.name}</span>
                    <Badge status={e.status} subtle />
                  </div>
                  <div className="mt-0.5 flex items-center gap-2 text-[13px] text-muted">
                    <span className="font-mono">{e.entity_type}</span>
                    <span className="font-mono">· relevance {e.score}</span>
                  </div>
                  {e.snippet && <p className="mt-1 line-clamp-2 text-[14px] text-muted">{e.snippet}</p>}
                </li>
              ))}
            </ul>}
      </Step>
    </div>
  )
}

function Step({ label, children, last }: { label: string; children: React.ReactNode; last?: boolean }) {
  return (
    <div className="relative pl-5">
      <span className="absolute left-0 top-1.5 h-2 w-2 rounded-full bg-accent" />
      {!last && <span className="absolute left-[3.5px] top-4 h-[calc(100%-2px)] w-px bg-line-strong" />}
      <div className="font-mono text-[12px] uppercase tracking-wider text-muted">{label}</div>
      <div className="mt-1">{children}</div>
    </div>
  )
}

export default function Analysis({ engine }: { engine: Engine }) {
  const [selected, setSelected] = useState<RequirementMatch | null>(null)
  const a = engine.analysis

  return (
    <div className="space-y-8">
      <JdInput engine={engine} />

      {!a ? (
        <EmptyState icon={icons.doc} title="No analysis yet"
          >Paste a job description above and analyze it to see how your experience matches,
          with the evidence behind every call.</EmptyState>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-1 border-y border-line py-3">
            <span className="text-[15px] font-medium text-ink">{a.requirements.role || 'Role'}</span>
            {GROUPS.map(g => {
              const n = a.matches.filter(m => g.key.includes(m.match_status)).length
              return <span key={g.title} className="text-[14px] text-muted">
                <span className="font-mono text-ink">{n}</span> {g.title.toLowerCase()}
              </span>
            })}
          </div>

          <div className="grid gap-8 lg:grid-cols-[1fr_400px]">
            <div className="space-y-6">
              {GROUPS.map(g => {
                const items = a.matches.filter(m => g.key.includes(m.match_status))
                if (!items.length) return null
                return (
                  <section key={g.title}>
                    <div className="mb-2 flex items-baseline gap-2">
                      <h3 className="text-[16px] font-semibold text-ink">{g.title}</h3>
                      <span className="text-[13px] text-muted">{g.hint}</span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {items.map((m, i) => {
                        const on = selected?.requirement === m.requirement
                        return (
                          <button key={i} onClick={() => setSelected(m)}
                            className={`rounded-md border px-3 py-1.5 text-[14px] transition-colors
                              ${on ? 'border-accent bg-accent-soft text-accent-ink'
                                : 'border-line bg-surface text-ink-soft hover:border-line-strong hover:bg-raised'}`}>
                            {m.requirement}
                          </button>
                        )
                      })}
                    </div>
                  </section>
                )
              })}

              {(a.plan.emphasize.length > 0 || a.plan.deemphasize.length > 0) && (
                <section className="border-t border-line pt-5">
                  <SectionHeader title="What we'll adjust"
                    description="How the tailored résumé will foreground your relevant experience." />
                  <dl className="space-y-2 text-[15px]">
                    <Row term="Emphasize" values={a.plan.emphasize.slice(0, 10)} />
                    <Row term="De-emphasize" values={a.plan.deemphasize.slice(0, 8)} muted />
                    <Row term="Project order" values={a.plan.reorder} />
                  </dl>
                </section>
              )}
            </div>

            <aside className="lg:sticky lg:top-4 lg:self-start">
              <Surface className="p-5">
                {selected
                  ? <EvidenceChain m={selected} />
                  : <div className="py-6 text-center">
                      <icons.info className="mx-auto mb-2 text-[24px] text-faint" />
                      <p className="text-[15px] text-muted">Select a requirement to see why it was
                        classified that way and the evidence behind it.</p>
                    </div>}
              </Surface>
            </aside>
          </div>

          <div className="border-t border-line pt-6">
            <Button size="md" icon={icons.arrowRight} onClick={() => engine.setStep(2)}>
              Review suggested changes
            </Button>
          </div>
        </>
      )}
    </div>
  )
}

function Row({ term, values, muted }: { term: string; values: string[]; muted?: boolean }) {
  return (
    <div className="flex flex-col gap-1 sm:flex-row sm:gap-3">
      <dt className="w-32 shrink-0 text-[14px] text-muted">{term}</dt>
      <dd className="flex flex-wrap gap-1.5">
        {values.length ? values.map(v => (
          <span key={v} className={`rounded px-2 py-0.5 text-[13px] ${muted ? 'bg-raised text-muted' : 'bg-accent-soft text-accent-ink'}`}>{v}</span>
        )) : <span className="text-[14px] text-faint">—</span>}
      </dd>
    </div>
  )
}
