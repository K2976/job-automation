import { useState } from 'react'
import type { Engine } from '../store'
import type { ModificationSuggestion } from '../api/types'
import { Badge, Button, EmptyState, SectionHeader, Surface, icons } from '../ui'

function Suggestion({ s, engine }: { s: ModificationSuggestion; engine: Engine }) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(s.suggested)
  const decided = s.status !== 'AI_SUGGESTED'
  const kind = s.type === 'REWRITE' ? 'Project reframing' : 'Skill addition'

  return (
    <Surface className="overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-3">
        <div>
          <div className="font-mono text-[12px] uppercase tracking-wider text-accent">{kind}</div>
          <div className="text-[16px] font-semibold text-ink">{s.target}</div>
        </div>
        {decided ? <Badge status={s.status} />
          : <span className="text-[13px] text-muted">Awaiting your decision</span>}
      </div>

      <div className="space-y-3 px-5 py-4">
        {s.type === 'REWRITE' && (
          <div>
            <div className="mb-1 text-[13px] font-medium text-muted">Current</div>
            <p className="rounded-md border border-line bg-raised px-3 py-2 text-[14px] leading-relaxed text-muted">{s.current}</p>
          </div>
        )}
        <div>
          <div className="mb-1 text-[13px] font-medium text-accent">
            {s.type === 'REWRITE' ? 'Suggested for this role' : 'Suggested'}
          </div>
          {editing
            ? <textarea value={text} onChange={e => setText(e.target.value)} rows={3}
                className="w-full rounded-md border border-accent bg-surface px-3 py-2 text-[15px] focus:outline-none" />
            : <p className="rounded-md border border-accent/30 bg-accent-soft px-3 py-2 text-[15px] leading-relaxed text-accent-ink">{s.suggested}</p>}
        </div>
        <p className="flex gap-2 text-[14px] text-muted">
          <icons.info className="mt-0.5 shrink-0 text-accent" />{s.reason}
        </p>
      </div>

      <div className="flex items-center gap-2 border-t border-line px-5 py-3">
        {editing ? (
          <>
            <Button size="sm" icon={icons.check} onClick={() => { engine.approve(s, 'EDIT', text); setEditing(false) }}>Save & accept</Button>
            <Button size="sm" variant="ghost" onClick={() => { setText(s.suggested); setEditing(false) }}>Cancel</Button>
          </>
        ) : (
          <>
            <Button size="sm" icon={icons.check} disabled={decided} onClick={() => engine.approve(s, 'ACCEPT')}>Accept</Button>
            <Button size="sm" variant="secondary" icon={icons.pencil} disabled={decided} onClick={() => setEditing(true)}>Edit</Button>
            <Button size="sm" variant="ghost" disabled={decided} onClick={() => engine.approve(s, 'REJECT')}>Reject</Button>
          </>
        )}
      </div>
    </Surface>
  )
}

export default function Modifications({ engine }: { engine: Engine }) {
  if (!engine.analysis)
    return <EmptyState title="Nothing to review yet" >Analyze a job description first to get tailoring suggestions.</EmptyState>

  const s = engine.suggestions
  const rewrites = s.filter(x => x.type === 'REWRITE')
  const skills = s.filter(x => x.type === 'ADD_SKILL')
  const decided = s.filter(x => x.status !== 'AI_SUGGESTED').length

  return (
    <div className="space-y-8">
      <p className="rounded-md border border-line bg-surface px-4 py-3 text-[15px] text-ink-soft">
        Nothing is applied until you accept it. Only confirm skills you genuinely have —
        an unapproved suggestion never becomes résumé content.
        {s.length > 0 && <span className="ml-1 text-muted">({decided} of {s.length} reviewed)</span>}
      </p>

      {!s.length ? <EmptyState title="No suggestions">Your profile already covers this role well.</EmptyState> : (
        <>
          {rewrites.length > 0 && (
            <section>
              <SectionHeader title="Project reframing"
                description="Reposition existing projects for this role — grounded in each project's own evidence." />
              <div className="space-y-4">{rewrites.map(x => <Suggestion key={x.id} s={x} engine={engine} />)}</div>
            </section>
          )}
          {skills.length > 0 && (
            <section>
              <SectionHeader title="Skill additions"
                description="Requirements not in your profile. Add only what genuinely applies — it's recorded as confirmed by you, never as original." />
              <div className="grid gap-4 md:grid-cols-2">{skills.map(x => <Suggestion key={x.id} s={x} engine={engine} />)}</div>
            </section>
          )}
        </>
      )}

      <div className="border-t border-line pt-6">
        <Button icon={icons.arrowRight} onClick={engine.generate}>Generate tailored résumé</Button>
      </div>
    </div>
  )
}
