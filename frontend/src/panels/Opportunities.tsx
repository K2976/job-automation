import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Opportunity, SearchPreferences, WhyApply } from '../api/types'
import { useOpportunities, type OppEngine } from '../opportunities'
import {
  Alert, Badge, Button, EmptyState, Loading, Meter, SectionHeader, Surface, icons,
} from '../ui'

const TABS = ['Discover', 'Results', 'Applications', 'Sources'] as const
type Tab = typeof TABS[number]

const pct = (n: number) => `${Math.round(n * 100)}%`
const list = (s: string) => s.split(',').map(x => x.trim()).filter(Boolean)

export default function Opportunities({ candidateId }: { candidateId: number | null }) {
  const opp = useOpportunities(candidateId)
  const [tab, setTab] = useState<Tab>('Discover')
  const [detail, setDetail] = useState<number | null>(null)

  if (!candidateId)
    return <EmptyState icon={icons.doc} title="Load your profile first">
      Opportunity discovery reasons over your master profile. Build or load a candidate
      on the Résumé tab, then come back here.
    </EmptyState>

  return (
    <div>
      <nav className="mb-6 flex gap-1 border-b border-line">
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-3.5 py-2 text-[14px] font-medium transition-colors
              ${tab === t ? 'border-accent text-ink' : 'border-transparent text-muted hover:text-ink'}`}>
            {t}
            {t === 'Results' && opp.opportunities.length > 0 &&
              <span className="ml-1.5 font-mono text-[12px] text-faint">{opp.opportunities.length}</span>}
          </button>
        ))}
      </nav>

      {opp.error && <div className="mb-5"><Alert title="Something went wrong">{opp.error}</Alert></div>}

      {tab === 'Discover' && <Discover opp={opp} onDone={() => setTab('Results')} />}
      {tab === 'Results' && <Results opp={opp} onView={setDetail} />}
      {tab === 'Applications' && <Applications opp={opp} onView={setDetail} />}
      {tab === 'Sources' && <Sources opp={opp} />}

      {detail !== null &&
        <Detail oid={detail} onClose={() => setDetail(null)} onStatus={opp.setStatus} />}
    </div>
  )
}

/* --------------------------------------------------------------- Discover -- */
function Discover({ opp, onDone }: { opp: OppEngine; onDone: () => void }) {
  const p = opp.prefs
  const set = (patch: Partial<SearchPreferences>) => opp.setPrefs({ ...p, ...patch })
  const run = opp.run

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <Surface className="p-6">
        <SectionHeader title="Discover opportunities"
          description="Set what you're looking for. We search configured sources, match against your profile, and rank the best fits — nothing is submitted." />
        <div className="grid gap-4">
          <Field label="Target roles" hint="comma-separated — e.g. AI Engineer, ML Engineer">
            <input className={inputCls} defaultValue={p.target_roles.join(', ')}
              onBlur={e => set({ target_roles: list(e.target.value) })}
              placeholder="AI Engineer, ML Engineer" />
          </Field>
          <Field label="Preferred locations" hint="comma-separated; remote roles always pass">
            <input className={inputCls} defaultValue={p.preferred_locations.join(', ')}
              onBlur={e => set({ preferred_locations: list(e.target.value) })}
              placeholder="India, Remote" />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Experience level">
              <select className={inputCls} value={p.experience_level}
                onChange={e => set({ experience_level: e.target.value })}>
                {['', 'internship', 'entry', 'mid', 'senior'].map(v =>
                  <option key={v} value={v}>{v || 'Any'}</option>)}
              </select>
            </Field>
            <Field label="Work mode">
              <select className={inputCls} value={p.remote_preference}
                onChange={e => set({ remote_preference: e.target.value })}>
                {['any', 'remote', 'hybrid', 'onsite'].map(v =>
                  <option key={v} value={v}>{v[0].toUpperCase() + v.slice(1)}</option>)}
              </select>
            </Field>
          </div>
          <Field label="Exclude companies" hint="optional, comma-separated">
            <input className={inputCls} defaultValue={p.excluded_companies.join(', ')}
              onBlur={e => set({ excluded_companies: list(e.target.value) })} />
          </Field>
          <div className="pt-1">
            <Button icon={icons.arrowRight} disabled={opp.discovering}
              onClick={() => opp.discover().then(onDone)}>
              {opp.discovering ? 'Discovering…' : 'Discover opportunities'}
            </Button>
          </div>
        </div>
      </Surface>

      <Surface className="h-fit p-6">
        <div className="mb-3 font-mono text-[12px] font-medium uppercase tracking-wider text-accent">
          Progress
        </div>
        {!run && !opp.discovering &&
          <p className="text-[15px] text-muted">Run a discovery to see live progress here.</p>}
        {opp.discovering && run?.status === 'RUNNING' &&
          <div className="mb-4"><Loading label={`${run.stage}…`} /></div>}
        {run &&
          <dl className="grid gap-1.5 text-[14px]">
            <Stat label="Sources checked" value={run.sources_checked} />
            <Stat label="Sources skipped" value={run.sources_skipped} muted />
            <Stat label="Discovered" value={run.discovered} />
            <Stat label="After filtering" value={run.after_filtering} />
            <Stat label="After deduplication" value={run.after_dedup} />
            <Stat label="Deeply analyzed" value={run.deeply_analyzed} />
            <Stat label="Shortlisted" value={run.shortlisted} strong />
          </dl>}
        {run?.status === 'FAILED' && <div className="mt-3"><Alert>{run.error}</Alert></div>}
      </Surface>
    </div>
  )
}

/* ---------------------------------------------------------------- Results -- */
function Results({ opp, onView }: { opp: OppEngine; onView: (id: number) => void }) {
  const [name, setName] = useState('')
  const [max, setMax] = useState(10)
  const results = opp.opportunities.filter(o =>
    ['ANALYZED', 'SHORTLISTED', 'READY_TO_APPLY', 'TAILORING'].includes(o.status))

  if (results.length === 0)
    return <EmptyState icon={icons.arrowRight} title="No opportunities yet">
      Head to Discover and run a search. Analyzed opportunities, ranked by fit, show up here.
    </EmptyState>

  return (
    <div>
      <SectionHeader title="Ranked opportunities"
        description="Best-fit first. Select the ones you want, then prepare tailored application packages." />
      <div className="grid gap-3">
        {results.map(o => (
          <OppCard key={o.id} o={o} selected={opp.selected.includes(o.id)}
            onToggle={() => opp.toggle(o.id)} onView={() => onView(o.id)} />
        ))}
      </div>

      {opp.selected.length > 0 &&
        <Surface className="sticky bottom-4 mt-5 flex flex-wrap items-center gap-3 p-4 shadow-md">
          <span className="text-[15px] font-medium text-ink">
            {opp.selected.length} selected
          </span>
          <input className={`${inputCls} w-40`} placeholder="Batch name"
            value={name} onChange={e => setName(e.target.value)} />
          <label className="flex items-center gap-2 text-[14px] text-muted">
            Max
            <input type="number" min={1} className={`${inputCls} w-20`} value={max}
              onChange={e => setMax(Math.max(1, Number(e.target.value) || 1))} />
          </label>
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" onClick={opp.clearSelection}>Clear</Button>
            <Button icon={icons.check} disabled={!!opp.busy || opp.selected.length > max}
              onClick={() => opp.prepare(name || `Batch of ${opp.selected.length}`, max)}>
              {opp.busy ? 'Preparing…' : `Prepare ${opp.selected.length} application${opp.selected.length > 1 ? 's' : ''}`}
            </Button>
          </div>
          {opp.selected.length > max &&
            <p className="w-full text-[13px] text-danger">
              Selection exceeds the maximum of {max}. Raise the max or deselect some.
            </p>}
        </Surface>}
    </div>
  )
}

function OppCard({ o, selected, onToggle, onView }:
  { o: Opportunity; selected: boolean; onToggle: () => void; onView: () => void }) {
  return (
    <Surface className={`flex items-center gap-4 p-4 transition-colors ${selected ? 'border-accent' : ''}`}>
      <input type="checkbox" checked={selected} onChange={onToggle}
        style={{ accentColor: 'var(--color-accent)' }}
        className="h-4 w-4 shrink-0" aria-label={`Select ${o.title}`} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-[16px] font-semibold text-ink">{o.title}</span>
          <Badge status={o.status} />
        </div>
        <div className="mt-0.5 truncate text-[14px] text-muted">
          {o.company}{o.location ? ` · ${o.location}` : ''}{o.work_mode ? ` · ${o.work_mode}` : ''}
        </div>
      </div>
      <div className="w-28 shrink-0 text-right">
        <div className="font-mono text-[18px] font-semibold text-ink">{pct(o.match_score)}</div>
        <div className="text-[12px] text-faint">match</div>
      </div>
      <Button size="sm" variant="secondary" onClick={onView}>View</Button>
    </Surface>
  )
}

/* ----------------------------------------------------------- Applications -- */
const TRACK: { status: string; label: string }[] = [
  { status: 'READY_TO_APPLY', label: 'Ready to apply' },
  { status: 'SHORTLISTED', label: 'Shortlisted' },
  { status: 'APPLIED', label: 'Applied' },
  { status: 'REJECTED', label: 'Rejected' },
  { status: 'SKIPPED', label: 'Skipped' },
]

function Applications({ opp, onView }: { opp: OppEngine; onView: (id: number) => void }) {
  return (
    <div className="grid gap-6">
      <div>
        <SectionHeader title="Batches"
          description="Each batch is a controlled set of prepared applications. V2 prepares packages; it never submits." />
        {opp.batches.length === 0
          ? <p className="text-[15px] text-muted">No batches yet. Prepare a selection from Results.</p>
          : <div className="grid gap-3">
            {opp.batches.map(b => (
              <Surface key={b.id} className="flex items-center gap-4 p-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[16px] font-semibold text-ink">{b.name}</span>
                    <Badge status={b.status === 'READY' ? 'READY_TO_APPLY' : 'TAILORING'} />
                  </div>
                  <div className="mt-0.5 text-[14px] text-muted">
                    {b.opportunity_ids.length} of max {b.max_opportunities}
                    {b.target_roles.length ? ` · ${b.target_roles.join(', ')}` : ''}
                  </div>
                </div>
              </Surface>
            ))}
          </div>}
      </div>

      <div>
        <SectionHeader title="Tracker" description="Move opportunities through your pipeline. You set Applied — the system never does." />
        <div className="grid gap-5">
          {TRACK.map(col => {
            const items = opp.opportunities.filter(o => o.status === col.status)
            if (items.length === 0) return null
            return (
              <div key={col.status}>
                <div className="mb-2 flex items-center gap-2">
                  <Badge status={col.status} />
                  <span className="font-mono text-[12px] text-faint">{items.length}</span>
                </div>
                <div className="grid gap-2">
                  {items.map(o => (
                    <Surface key={o.id} className="flex items-center gap-3 p-3">
                      <button onClick={() => onView(o.id)}
                        className="min-w-0 flex-1 truncate text-left text-[15px] text-ink hover:text-accent">
                        {o.title} <span className="text-muted">· {o.company}</span>
                      </button>
                      <select className={`${inputCls} h-8 w-36 text-[13px]`} value={o.status}
                        onChange={e => opp.setStatus(o.id, e.target.value)}>
                        {['SHORTLISTED', 'READY_TO_APPLY', 'APPLIED', 'REJECTED', 'SKIPPED']
                          .map(s => <option key={s} value={s}>{s.replace(/_/g, ' ').toLowerCase()}</option>)}
                      </select>
                    </Surface>
                  ))}
                </div>
              </div>
            )
          })}
          {opp.opportunities.every(o => !TRACK.some(t => t.status === o.status)) &&
            <p className="text-[15px] text-muted">Nothing tracked yet.</p>}
        </div>
      </div>
    </div>
  )
}

/* ----------------------------------------------------------------- Sources -- */
function Sources({ opp }: { opp: OppEngine }) {
  return (
    <div>
      <SectionHeader title="Job sources"
        description="Health from your last discovery. A blocked, rate-limited or CAPTCHA source is skipped and reported — never retried or bypassed." />
      {opp.sources.length === 0
        ? <p className="text-[15px] text-muted">Run a discovery to populate source health.</p>
        : <div className="grid gap-2">
          {opp.sources.map(s => (
            <Surface key={s.name} className="flex items-center gap-4 p-4">
              <span className="flex-1 text-[15px] font-medium text-ink">{s.name}</span>
              {s.status === 'AVAILABLE' && <span className="text-[13px] text-muted">{s.discovered} found</span>}
              {s.detail && <span className="max-w-xs truncate text-[13px] text-faint">{s.detail}</span>}
              <Badge status={s.status} />
            </Surface>
          ))}
        </div>}
    </div>
  )
}

/* ------------------------------------------------------------------ Detail -- */
function Detail({ oid, onClose, onStatus }:
  { oid: number; onClose: () => void; onStatus: (id: number, s: string) => Promise<void> }) {
  const [data, setData] = useState<{ opportunity: Opportunity; why_apply: WhyApply } | null>(null)
  const [showJd, setShowJd] = useState(false)
  useEffect(() => { api.getOpportunity(oid).then(setData).catch(() => {}) }, [oid])

  const o = data?.opportunity
  const why = data?.why_apply
  return (
    <div className="fixed inset-0 z-30 flex justify-end bg-black/30" onClick={onClose}>
      <div className="h-full w-full max-w-xl overflow-y-auto bg-surface p-6 shadow-xl"
        onClick={e => e.stopPropagation()}>
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-[22px] font-bold text-ink">{o?.title ?? 'Loading…'}</h2>
            {o && <p className="text-[15px] text-muted">
              {o.company}{o.location ? ` · ${o.location}` : ''}{o.work_mode ? ` · ${o.work_mode}` : ''}
              {o.employment_type ? ` · ${o.employment_type}` : ''}{o.salary ? ` · ${o.salary}` : ''}
            </p>}
          </div>
          <Button size="sm" variant="ghost" icon={icons.x} onClick={onClose} aria-label="Close">Close</Button>
        </div>

        {!o && <Loading label="Loading opportunity…" />}
        {o && why &&
          <div className="grid gap-5">
            <div className="flex flex-wrap items-center gap-3">
              <Badge status={o.status} />
              {o.source && <span className="text-[13px] text-faint">via {o.source}
                {o.source_refs.length ? ` (+${o.source_refs.join(', ')})` : ''}</span>}
              {o.application_url &&
                <a href={o.application_url} target="_blank" rel="noreferrer"
                  className="ml-auto text-[14px] text-accent hover:underline">Application link ↗</a>}
            </div>

            <Surface className="p-4">
              <Meter label="Match score" value={why.match_score} />
              <Meter label="Opportunity score" value={why.opportunity_score} />
            </Surface>

            <WhyList title="Strong matches" tone="pos" items={why.strong_matches} />
            <WhyList title="Partial matches" tone="warn" items={why.partial_matches} />
            <WhyList title="Gaps" tone="neg" items={why.gaps} />
            {why.best_evidence.length > 0 &&
              <div>
                <div className="mb-1.5 text-[14px] font-semibold text-ink">Best candidate evidence</div>
                <ol className="ml-4 list-decimal text-[14px] text-muted">
                  {why.best_evidence.map((e, i) => <li key={i}>{e}</li>)}
                </ol>
              </div>}

            {o.status === 'READY_TO_APPLY' && o.job_id &&
              <Surface className="p-4">
                <div className="mb-2 text-[14px] font-semibold text-ink">Application package</div>
                <div className="flex flex-wrap gap-2">
                  <a href={api.exportUrl(o.job_id, 'latex.pdf')} className="text-[14px] text-accent hover:underline">Tailored résumé (PDF)</a>
                  <span className="text-faint">·</span>
                  <a href={api.exportUrl(o.job_id, 'tex')} className="text-[14px] text-accent hover:underline">.tex</a>
                </div>
                {o.cover_letter &&
                  <details className="mt-3">
                    <summary className="cursor-pointer text-[14px] text-ink-soft">Cover letter</summary>
                    <pre className="mt-2 whitespace-pre-wrap text-[14px] text-muted">{o.cover_letter}</pre>
                  </details>}
              </Surface>}

            <div>
              <button onClick={() => setShowJd(v => !v)}
                className="text-[14px] text-ink-soft hover:text-ink">
                {showJd ? '▾' : '▸'} Raw job description
              </button>
              {showJd &&
                <pre className="mt-2 max-h-72 overflow-y-auto whitespace-pre-wrap rounded-md bg-raised p-3 text-[13px] text-muted">
                  {o.description_raw || '(none)'}
                </pre>}
            </div>

            <div className="flex gap-2 border-t border-line pt-4">
              <Button size="sm" variant="secondary" onClick={() => onStatus(o.id, 'APPLIED').then(onClose)}>Mark applied</Button>
              <Button size="sm" variant="ghost" onClick={() => onStatus(o.id, 'SKIPPED').then(onClose)}>Skip</Button>
              <Button size="sm" variant="danger" onClick={() => onStatus(o.id, 'REJECTED').then(onClose)}>Reject</Button>
            </div>
          </div>}
      </div>
    </div>
  )
}

function WhyList({ title, tone, items }: { title: string; tone: string; items: string[] }) {
  if (items.length === 0) return null
  const dot = { pos: 'text-success', warn: 'text-warn', neg: 'text-danger' }[tone] ?? ''
  return (
    <div>
      <div className="mb-1.5 text-[14px] font-semibold text-ink">{title}</div>
      <ul className="grid gap-1 text-[14px] text-muted">
        {items.map((it, i) => <li key={i} className="flex gap-2"><span className={dot}>•</span>{it}</li>)}
      </ul>
    </div>
  )
}

/* ------------------------------------------------------------------ atoms -- */
const inputCls = 'w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-[15px] text-ink outline-none focus:border-accent'

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="mb-1 flex items-baseline gap-2">
        <span className="text-[14px] font-medium text-ink">{label}</span>
        {hint && <span className="text-[12px] text-faint">{hint}</span>}
      </div>
      {children}
    </label>
  )
}

function Stat({ label, value, strong, muted }:
  { label: string; value: number; strong?: boolean; muted?: boolean }) {
  return (
    <div className="flex items-baseline justify-between">
      <span className={`text-[14px] ${muted ? 'text-faint' : 'text-muted'}`}>{label}</span>
      <span className={`font-mono ${strong ? 'text-[16px] font-semibold text-ink' : 'text-[14px] text-ink-soft'}`}>{value}</span>
    </div>
  )
}
