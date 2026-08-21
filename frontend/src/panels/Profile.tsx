import { useState } from 'react'
import type { Engine } from '../store'
import type { EntityType, KBEntity } from '../api/types'
import { Badge, Button, Card, Empty } from '../ui'

const GROUPS: { type: EntityType; label: string }[] = [
  { type: 'skill', label: 'Skills' },
  { type: 'project', label: 'Projects' },
  { type: 'experience', label: 'Experience' },
  { type: 'education', label: 'Education' },
  { type: 'certification', label: 'Certifications' },
  { type: 'achievement', label: 'Achievements' },
]

function EntityRow({ e, engine }: { e: KBEntity; engine: Engine }) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(e.name)
  const [content, setContent] = useState(e.content)

  if (editing) {
    return (
      <div className="rounded-lg border border-slate-700 p-2">
        <input value={name} onChange={ev => setName(ev.target.value)}
          className="mb-1 w-full rounded bg-slate-900 px-2 py-1 text-sm" />
        <textarea value={content} onChange={ev => setContent(ev.target.value)}
          className="w-full rounded bg-slate-900 px-2 py-1 text-xs" rows={2} />
        <div className="mt-1 flex gap-2">
          <Button onClick={() => { engine.editEntity(e.id, { name, content }); setEditing(false) }}>Save</Button>
          <Button variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
        </div>
      </div>
    )
  }
  return (
    <div className="flex items-start justify-between gap-2 rounded-lg border border-slate-800 px-2 py-1.5">
      <div className="min-w-0">
        <div className="flex items-center gap-2 text-sm">
          <span className="font-medium">{e.name}</span><Badge status={e.status} />
        </div>
        {e.entity_type !== 'skill' &&
          <div className="truncate text-xs text-slate-400">{e.content}</div>}
      </div>
      <div className="flex shrink-0 gap-1">
        <Button variant="ghost" onClick={() => setEditing(true)}>Edit</Button>
        <Button variant="danger" onClick={() => engine.deleteEntity(e.id)}>×</Button>
      </div>
    </div>
  )
}

function AddSkill({ engine }: { engine: Engine }) {
  const [name, setName] = useState('')
  return (
    <div className="mt-2 flex gap-2">
      <input value={name} onChange={e => setName(e.target.value)} placeholder="Add a skill you have…"
        className="flex-1 rounded bg-slate-900 px-2 py-1 text-sm"
        onKeyDown={e => { if (e.key === 'Enter' && name.trim()) { engine.addEntity({ entity_type: 'skill', name: name.trim(), content: name.trim() }); setName('') } }} />
      <Button disabled={!name.trim()}
        onClick={() => { engine.addEntity({ entity_type: 'skill', name: name.trim(), content: name.trim() }); setName('') }}>Add</Button>
    </div>
  )
}

function CandidateHeader({ engine }: { engine: Engine }) {
  const c = engine.candidate!
  const [f, setF] = useState({ name: c.name, headline: c.headline, email: c.email, location: c.location })
  const field = (k: keyof typeof f, ph: string) => (
    <input value={f[k]} placeholder={ph} onChange={e => setF({ ...f, [k]: e.target.value })}
      className="rounded bg-slate-900 px-2 py-1 text-sm" />
  )
  return (
    <Card title="Candidate">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {field('name', 'Name')}{field('headline', 'Headline')}
        {field('email', 'Email')}{field('location', 'Location')}
      </div>
      <div className="mt-2"><Button onClick={() => engine.editCandidate(f)}>Save details</Button></div>
    </Card>
  )
}

export default function Profile({ engine }: { engine: Engine }) {
  if (!engine.candidate) {
    return (
      <Card title="Get started">
        <p className="mb-3 text-sm text-slate-400">
          Upload a résumé (PDF/DOCX/TXT), load the bundled sample, or paste text.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={engine.seed}>Load sample candidate</Button>
          <label className="cursor-pointer rounded-md border border-slate-600 px-3 py-1.5 text-[13px] text-slate-200 hover:bg-slate-700/40">
            Upload résumé
            <input type="file" accept=".pdf,.docx,.txt,.md" className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) engine.ingestFile(f) }} />
          </label>
        </div>
        <PasteResume engine={engine} />
      </Card>
    )
  }
  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <CandidateHeader engine={engine} />
      <Card title={`Knowledge base — ${engine.entities.length} items`}>
        <p className="mb-3 text-xs text-slate-500">
          Everything the tailoring reasons over. Edit anything the parser got wrong —
          you're never forced to trust the extraction.
        </p>
        <div className="space-y-4">
          {GROUPS.map(g => {
            const items = engine.entities.filter(e => e.entity_type === g.type)
            if (!items.length && g.type !== 'skill') return null
            return (
              <div key={g.type}>
                <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">{g.label}</div>
                <div className="space-y-1">
                  {items.map(e => <EntityRow key={e.id} e={e} engine={engine} />)}
                  {!items.length && <Empty>None yet.</Empty>}
                </div>
                {g.type === 'skill' && <AddSkill engine={engine} />}
              </div>
            )
          })}
        </div>
      </Card>
    </div>
  )
}

function PasteResume({ engine }: { engine: Engine }) {
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  if (!open) return <div className="mt-3"><Button variant="ghost" onClick={() => setOpen(true)}>Paste résumé text instead</Button></div>
  return (
    <div className="mt-3">
      <textarea value={text} onChange={e => setText(e.target.value)} rows={6}
        placeholder="Paste résumé text…"
        className="w-full rounded bg-slate-900 px-2 py-2 text-xs" />
      <div className="mt-2"><Button disabled={!text.trim()} onClick={() => engine.ingest(text)}>Build profile</Button></div>
    </div>
  )
}
