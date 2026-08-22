import { useRef, useState } from 'react'
import type { Engine } from '../store'
import type { EntityType, KBEntity } from '../api/types'
import { Badge, Button, EmptyState, SectionHeader, Surface, icons } from '../ui'

const GROUPS: { type: EntityType; label: string }[] = [
  { type: 'skill', label: 'Skills' },
  { type: 'project', label: 'Projects' },
  { type: 'experience', label: 'Experience' },
  { type: 'education', label: 'Education' },
  { type: 'certification', label: 'Certifications' },
  { type: 'achievement', label: 'Achievements' },
]

/* ------------------------------------------------------------- start screen -- */
function Start({ engine }: { engine: Engine }) {
  const [drag, setDrag] = useState(false)
  const [pasting, setPasting] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const pick = (f?: File) => { if (f) engine.ingestFile(f) }

  return (
    <div className="mx-auto max-w-[680px]">
      <p className="mb-6 text-[17px] leading-relaxed text-ink-soft">
        Upload your master résumé once. For each job description, the engine finds your
        relevant experience, flags real gaps, and proposes changes you approve — before it
        writes a role-specific résumé. Nothing is invented and nothing is applied without you.
      </p>

      <div
        onDragOver={e => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={e => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files?.[0]) }}
        className={`rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors
          ${drag ? 'border-accent bg-accent-soft' : 'border-line-strong bg-surface'}`}>
        <icons.upload className="mx-auto mb-3 text-[30px] text-faint" />
        <div className="text-[17px] font-medium text-ink">Drop your résumé here</div>
        <div className="mt-1 text-[15px] text-muted">PDF, DOCX or TXT — up to 5&nbsp;MB</div>
        <div className="mt-5 flex items-center justify-center gap-3">
          <Button icon={icons.doc} onClick={() => fileRef.current?.click()}>Browse files</Button>
          <Button variant="secondary" onClick={engine.seed}>Use sample candidate</Button>
        </div>
        <input ref={fileRef} type="file" accept=".pdf,.docx,.txt,.md" className="hidden"
          onChange={e => pick(e.target.files?.[0])} />
      </div>

      <div className="mt-4 text-center">
        <button onClick={() => setPasting(v => !v)} className="text-[14px] text-muted underline decoration-line-strong underline-offset-4 hover:text-ink">
          or paste résumé text
        </button>
      </div>
      {pasting && <PasteBox engine={engine} />}
    </div>
  )
}

function PasteBox({ engine }: { engine: Engine }) {
  const [text, setText] = useState('')
  return (
    <div className="mt-3">
      <textarea value={text} onChange={e => setText(e.target.value)} rows={7}
        placeholder="Paste your résumé text…"
        className="w-full resize-y rounded-md border border-line-strong bg-surface px-3.5 py-3 text-[15px] placeholder:text-faint focus:border-accent focus:outline-none" />
      <div className="mt-2"><Button disabled={!text.trim()} onClick={() => engine.ingest(text)}>Build profile</Button></div>
    </div>
  )
}

/* --------------------------------------------------------------- editor -- */
function EntityRow({ e, engine }: { e: KBEntity; engine: Engine }) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(e.name)
  const [content, setContent] = useState(e.content)

  if (editing) return (
    <div className="rounded-md border border-line-strong bg-surface p-3">
      <input value={name} onChange={ev => setName(ev.target.value)}
        className="mb-2 w-full rounded border border-line px-2.5 py-1.5 text-[15px] focus:border-accent focus:outline-none" />
      <textarea value={content} onChange={ev => setContent(ev.target.value)} rows={2}
        className="w-full rounded border border-line px-2.5 py-1.5 text-[14px] focus:border-accent focus:outline-none" />
      <div className="mt-2 flex gap-2">
        <Button size="sm" onClick={() => { engine.editEntity(e.id, { name, content }); setEditing(false) }}>Save</Button>
        <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
      </div>
    </div>
  )
  return (
    <div className="group flex items-start justify-between gap-3 rounded-md px-3 py-2 hover:bg-raised">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[15px] font-medium text-ink">{e.name}</span>
          {e.status !== 'ORIGINAL' && <Badge status={e.status} subtle />}
        </div>
        {e.entity_type !== 'skill' && <p className="mt-0.5 line-clamp-1 text-[14px] text-muted">{e.content}</p>}
      </div>
      <div className="flex shrink-0 gap-1 opacity-0 transition-opacity group-hover:opacity-100">
        <Button size="sm" variant="ghost" icon={icons.pencil} onClick={() => setEditing(true)}>Edit</Button>
        <Button size="sm" variant="ghost" icon={icons.x} onClick={() => engine.deleteEntity(e.id)} aria-label="Remove" />
      </div>
    </div>
  )
}

function AddSkill({ engine }: { engine: Engine }) {
  const [name, setName] = useState('')
  const add = () => { if (name.trim()) { engine.addEntity({ entity_type: 'skill', name: name.trim(), content: name.trim() }); setName('') } }
  return (
    <div className="mt-2 flex gap-2 px-3">
      <input value={name} onChange={e => setName(e.target.value)} placeholder="Add a skill you have…"
        onKeyDown={e => e.key === 'Enter' && add()}
        className="flex-1 rounded-md border border-line px-3 py-1.5 text-[15px] placeholder:text-faint focus:border-accent focus:outline-none" />
      <Button size="sm" variant="secondary" disabled={!name.trim()} onClick={add}>Add</Button>
    </div>
  )
}

function CandidateCard({ engine }: { engine: Engine }) {
  const c = engine.candidate!
  const [f, setF] = useState({ name: c.name, headline: c.headline, email: c.email, location: c.location })
  const field = (k: keyof typeof f, ph: string) => (
    <div>
      <label className="mb-1 block text-[13px] text-muted">{ph}</label>
      <input value={f[k]} onChange={e => setF({ ...f, [k]: e.target.value })}
        className="w-full rounded-md border border-line px-3 py-2 text-[15px] focus:border-accent focus:outline-none" />
    </div>
  )
  return (
    <Surface className="p-5">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {field('name', 'Name')}{field('headline', 'Headline')}
        {field('email', 'Email')}{field('location', 'Location')}
      </div>
      <div className="mt-3"><Button size="sm" variant="secondary" icon={icons.check} onClick={() => engine.editCandidate(f)}>Save details</Button></div>
    </Surface>
  )
}

export default function Profile({ engine }: { engine: Engine }) {
  if (!engine.candidate) return <Start engine={engine} />

  return (
    <div className="grid gap-8 lg:grid-cols-[340px_1fr]">
      <div>
        <SectionHeader title="Details" />
        <CandidateCard engine={engine} />
      </div>
      <div>
        <SectionHeader eyebrow={`${engine.entities.length} items`} title="Knowledge base"
          description="Everything the tailoring reasons over. Correct anything the parser got wrong — you're never forced to trust the extraction." />
        <div className="space-y-6">
          {GROUPS.map(g => {
            const items = engine.entities.filter(e => e.entity_type === g.type)
            if (!items.length && g.type !== 'skill') return null
            return (
              <section key={g.type}>
                <h3 className="mb-1 px-3 text-[13px] font-semibold uppercase tracking-wider text-muted">{g.label}</h3>
                {items.length
                  ? <div className="divide-y divide-line">{items.map(e => <EntityRow key={e.id} e={e} engine={engine} />)}</div>
                  : <p className="px-3 py-2 text-[14px] text-faint">None yet.</p>}
                {g.type === 'skill' && <AddSkill engine={engine} />}
              </section>
            )
          })}
          {!engine.entities.length &&
            <EmptyState title="No profile items" >Upload a résumé to build your knowledge base.</EmptyState>}
        </div>
      </div>
    </div>
  )
}
