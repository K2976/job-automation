import { useState } from 'react'
import type { Engine } from '../store'
import type { ModificationSuggestion } from '../api/types'
import { Badge, Button, Card, Empty } from '../ui'

function Suggestion({ s, engine }: { s: ModificationSuggestion; engine: Engine }) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(s.suggested)
  const decided = s.status !== 'AI_SUGGESTED'

  return (
    <div className="rounded-lg border border-slate-700 p-3">
      <div className="mb-1 flex items-center justify-between">
        <span className="text-sm font-semibold">
          {s.type.replace(/_/g, ' ')} · <span className="text-slate-300">{s.target}</span>
        </span>
        <Badge status={s.status} />
      </div>
      <p className="mb-2 text-xs text-slate-400">{s.reason}</p>

      {s.type === 'REWRITE' && (
        <div className="mb-2 rounded bg-slate-900/60 p-2 text-xs">
          <div className="text-slate-500">Current</div>
          <div className="mb-1 text-slate-300">{s.current}</div>
        </div>
      )}

      {editing ? (
        <textarea value={text} onChange={e => setText(e.target.value)} rows={3}
          className="w-full rounded bg-slate-900 px-2 py-1 text-sm" />
      ) : (
        <div className="rounded bg-sky-500/5 p-2 text-sm text-sky-100">{s.suggested}</div>
      )}

      <div className="mt-2 flex gap-2">
        {editing ? (
          <>
            <Button onClick={() => { engine.approve(s, 'EDIT', text); setEditing(false) }}>Save edit</Button>
            <Button variant="ghost" onClick={() => { setText(s.suggested); setEditing(false) }}>Cancel</Button>
          </>
        ) : (
          <>
            <Button disabled={decided} onClick={() => engine.approve(s, 'ACCEPT')}>Accept</Button>
            <Button variant="ghost" disabled={decided} onClick={() => setEditing(true)}>Edit</Button>
            <Button variant="danger" disabled={decided} onClick={() => engine.approve(s, 'REJECT')}>Reject</Button>
          </>
        )}
      </div>
    </div>
  )
}

export default function Modifications({ engine }: { engine: Engine }) {
  if (!engine.analysis) return <Empty>Analyze a JD first to get modification suggestions.</Empty>
  const s = engine.suggestions
  const rewrites = s.filter(x => x.type === 'REWRITE')
  const skills = s.filter(x => x.type === 'ADD_SKILL')

  return (
    <div className="space-y-4">
      <Card title="Suggested modifications — your approval required">
        <p className="mb-3 text-xs text-slate-500">
          Nothing is applied until you accept it. Only confirm skills you genuinely have —
          an unapproved suggestion never becomes résumé content.
        </p>
        {!s.length ? <Empty>No suggestions.</Empty> : (
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Project rewrites</div>
              <div className="space-y-3">
                {rewrites.map(x => <Suggestion key={x.id} s={x} engine={engine} />)}
                {!rewrites.length && <Empty>None.</Empty>}
              </div>
            </div>
            <div>
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Skill additions</div>
              <div className="space-y-3">
                {skills.map(x => <Suggestion key={x.id} s={x} engine={engine} />)}
                {!skills.length && <Empty>None.</Empty>}
              </div>
            </div>
          </div>
        )}
      </Card>
      <div><Button onClick={engine.generate}>Generate tailored résumé →</Button></div>
    </div>
  )
}
