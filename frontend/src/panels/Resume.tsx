import { useState } from 'react'
import { api } from '../api/client'
import type { Engine } from '../store'
import type { TailoredResume } from '../api/types'
import { Badge, Button, EmptyState, Meter, Surface, icons } from '../ui'

type Tab = 'preview' | 'alignment' | 'validation' | 'compare'

export default function Resume({ engine }: { engine: Engine }) {
  const [tab, setTab] = useState<Tab>('preview')
  const [saved, setSaved] = useState('')
  const g = engine.generation
  const a = engine.analysis

  if (!a) return <EmptyState title="No résumé yet">Analyze a job description first.</EmptyState>
  if (!g) return (
    <EmptyState icon={icons.doc} title="Ready to generate"
      action={<Button icon={icons.arrowRight} onClick={engine.generate}>Generate tailored résumé</Button>}>
      Build the tailored résumé from your approved evidence, then review and export it.
    </EmptyState>
  )

  const jobId = a.job_id
  const save = async () => {
    const name = prompt('Name this role view:', `${g.resume.target_role} view`)
    if (name) { await engine.saveRoleProfile(name); setSaved(`Saved “${name}”`) }
  }
  const TABS: [Tab, string][] = [
    ['preview', 'Preview'], ['alignment', 'Alignment'],
    ['validation', 'Validation'], ['compare', 'Compare'],
  ]

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3 border-b border-line pb-3">
        <div className="flex rounded-md border border-line bg-surface p-0.5">
          {TABS.map(([t, label]) => (
            <button key={t} onClick={() => setTab(t)}
              className={`rounded px-3.5 py-1.5 text-[14px] font-medium transition-colors
                ${tab === t ? 'bg-accent text-white' : 'text-ink-soft hover:bg-raised'}`}>{label}</button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-2">
          {saved && <span className="text-[13px] text-success">{saved}</span>}
          <Button size="sm" variant="ghost" onClick={save}>Save as view</Button>
          <a href={api.exportUrl(jobId, 'latex.pdf')} target="_blank" rel="noreferrer">
            <Button size="sm" icon={icons.doc}>Professional PDF</Button></a>
          <a href={api.exportUrl(jobId, 'pdf')} target="_blank" rel="noreferrer">
            <Button size="sm" variant="ghost">PDF (standard)</Button></a>
          <a href={api.exportUrl(jobId, 'tex')} target="_blank" rel="noreferrer" className="text-[13px] text-muted underline underline-offset-4 hover:text-ink">.tex</a>
          <a href={api.exportUrl(jobId, 'html')} target="_blank" rel="noreferrer" className="text-[13px] text-muted underline underline-offset-4 hover:text-ink">HTML</a>
          <a href={api.exportUrl(jobId, 'md')} target="_blank" rel="noreferrer" className="text-[13px] text-muted underline underline-offset-4 hover:text-ink">Markdown</a>
        </div>
      </div>

      {tab === 'preview' && <Preview r={g.resume} />}
      {tab === 'alignment' && <Alignment g={g} />}
      {tab === 'validation' && <Validation g={g} />}
      {tab === 'compare' && <Compare g={g} />}
    </div>
  )
}

/* ------------------------------------------------------------ résumé paper -- */
function Preview({ r }: { r: TailoredResume }) {
  const contact = [r.candidate.email, r.candidate.phone, r.candidate.location].filter(Boolean).join('  ·  ')
  return (
    <div className="flex justify-center">
      <article className="w-full max-w-[760px] rounded-lg border border-line bg-white px-10 py-9 shadow-sm">
        <h1 className="text-[26px] font-bold tracking-tight text-ink">{r.candidate.name}</h1>
        <div className="text-[15px] text-accent">{r.target_role}</div>
        {contact && <div className="mt-1 font-mono text-[12px] text-muted">{contact}</div>}
        {r.summary && <DocSection title="Summary"><p className="text-[14.5px] leading-relaxed text-ink-soft">{r.summary}</p></DocSection>}
        {r.skills.length > 0 && <DocSection title="Skills"><p className="text-[14.5px] text-ink-soft">{r.skills.join('  ·  ')}</p></DocSection>}
        {r.sections.map((s, i) => (
          <DocSection key={i} title={s.title}>
            <ul className="space-y-1.5">
              {s.bullets.map((b, j) => (
                <li key={j} className="flex gap-2 text-[14.5px] leading-relaxed text-ink-soft">
                  <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-line-strong" />{b.text}
                </li>
              ))}
            </ul>
          </DocSection>
        ))}
      </article>
    </div>
  )
}

function DocSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-5">
      <h2 className="mb-2 border-b border-line pb-1 text-[12px] font-semibold uppercase tracking-[0.14em] text-accent">{title}</h2>
      {children}
    </section>
  )
}

/* -------------------------------------------------------------- alignment -- */
function Alignment({ g }: { g: NonNullable<Engine['generation']> }) {
  const a = g.ats
  return (
    <div className="grid gap-8 md:grid-cols-[280px_1fr]">
      <div>
        <div className="text-[13px] uppercase tracking-wider text-muted">JD alignment</div>
        <div className="font-mono text-[52px] font-semibold leading-none text-ink">{Math.round(a.overall_score * 100)}%</div>
        <p className="mt-2 text-[14px] text-muted">A coverage indicator, not a guaranteed ATS result.</p>
      </div>
      <div>
        <Meter label="Required skills" value={a.skill_coverage} />
        <Meter label="Keyword coverage" value={a.keyword_coverage} />
        <Meter label="Requirement coverage" value={a.requirement_coverage} />
        <Meter label="Project relevance" value={a.project_relevance} />
        {a.missing_skills.length > 0 && (
          <div className="mt-5">
            <div className="mb-1.5 text-[14px] font-medium text-ink">Areas to strengthen</div>
            <div className="flex flex-wrap gap-1.5">
              {a.missing_skills.map(s => <span key={s} className="rounded bg-warn-soft px-2 py-0.5 text-[13px] text-warn">{s}</span>)}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/* -------------------------------------------------------------- validation -- */
function Validation({ g }: { g: NonNullable<Engine['generation']> }) {
  const v = g.validation
  const flagged = v.claims.filter(c => c.status === 'UNSUPPORTED' || c.status === 'AI_SUGGESTED_NOT_APPROVED')
  const ok = v.claims.filter(c => !flagged.includes(c))
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-x-8 gap-y-2">
        <Stat n={v.supported} label="claims supported" tone="text-success" />
        <Stat n={v.needs_approval} label="need approval" tone="text-warn" />
        <Stat n={v.unsupported} label="unsupported" tone={v.unsupported ? 'text-danger' : 'text-muted'} />
      </div>

      {flagged.length > 0 && (
        <Surface className="border-warn/30 p-5">
          <div className="mb-2 flex items-center gap-2 text-[15px] font-semibold text-warn">
            <icons.info /> {flagged.length} claim{flagged.length > 1 ? 's' : ''} to review before you rely on this résumé
          </div>
          <ul className="space-y-2">
            {flagged.map((c, i) => (
              <li key={i} className="flex items-start justify-between gap-3 rounded-md bg-warn-soft px-3 py-2">
                <span className="text-[14px] text-ink-soft">{c.text}</span>
                <Badge status={c.status} />
              </li>
            ))}
          </ul>
        </Surface>
      )}

      <details className="text-[14px]">
        <summary className="cursor-pointer text-muted hover:text-ink">Show all {v.claims.length} claims and their evidence</summary>
        <ul className="mt-2 divide-y divide-line">
          {ok.map((c, i) => (
            <li key={i} className="flex items-center justify-between gap-3 py-1.5">
              <span className="text-ink-soft">{c.text}</span><Badge status={c.status} subtle />
            </li>
          ))}
        </ul>
      </details>
    </div>
  )
}

function Stat({ n, label, tone }: { n: number; label: string; tone: string }) {
  return <div><span className={`font-mono text-[28px] font-semibold ${tone}`}>{n}</span>
    <span className="ml-2 text-[15px] text-muted">{label}</span></div>
}

/* --------------------------------------------------------------- compare -- */
function Compare({ g }: { g: NonNullable<Engine['generation']> }) {
  const c = g.comparison
  return (
    <div className="grid gap-6 sm:grid-cols-2">
      <div>
        <div className="mb-2 text-[15px] font-semibold text-ink">Foregrounded for this role</div>
        <div className="flex flex-wrap gap-1.5">
          {c.skills_added.length ? c.skills_added.map(s => <span key={s} className="rounded bg-success-soft px-2 py-0.5 text-[14px] text-success">{s}</span>)
            : <span className="text-[14px] text-faint">—</span>}
        </div>
      </div>
      <div>
        <div className="mb-2 text-[15px] font-semibold text-ink">Dropped as not relevant</div>
        <div className="flex flex-wrap gap-1.5">
          {c.skills_dropped.length ? c.skills_dropped.map(s => <span key={s} className="rounded bg-raised px-2 py-0.5 text-[14px] text-muted line-through decoration-line-strong">{s}</span>)
            : <span className="text-[14px] text-faint">—</span>}
        </div>
      </div>
    </div>
  )
}
