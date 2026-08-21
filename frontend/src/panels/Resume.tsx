import { useState } from 'react'
import { api } from '../api/client'
import type { Engine } from '../store'
import type { TailoredResume } from '../api/types'
import { Badge, Bar, Button, Card, Empty } from '../ui'

function Preview({ r }: { r: TailoredResume }) {
  return (
    <div className="max-h-[70vh] overflow-y-auto rounded-lg bg-white p-6 text-slate-900 shadow">
      <h1 className="text-2xl font-bold">{r.candidate.name}</h1>
      <div className="text-sm text-slate-500">{r.target_role}</div>
      <div className="mb-3 text-xs text-slate-500">
        {[r.candidate.email, r.candidate.phone, r.candidate.location].filter(Boolean).join(' · ')}
      </div>
      {r.summary && <>
        <h2 className="mt-3 border-b border-slate-300 text-xs font-bold uppercase tracking-wide text-sky-700">Summary</h2>
        <p className="mt-1 text-sm">{r.summary}</p>
      </>}
      {r.skills.length > 0 && <>
        <h2 className="mt-3 border-b border-slate-300 text-xs font-bold uppercase tracking-wide text-sky-700">Skills</h2>
        <p className="mt-1 text-sm">{r.skills.join(' · ')}</p>
      </>}
      {r.sections.map((sec, i) => (
        <div key={i}>
          <h2 className="mt-3 border-b border-slate-300 text-xs font-bold uppercase tracking-wide text-sky-700">{sec.title}</h2>
          <ul className="mt-1 list-disc pl-5 text-sm">
            {sec.bullets.map((b, j) => <li key={j} className="mt-0.5">{b.text}</li>)}
          </ul>
        </div>
      ))}
    </div>
  )
}

export default function Resume({ engine }: { engine: Engine }) {
  const g = engine.generation
  const a = engine.analysis
  const [savedMsg, setSavedMsg] = useState('')

  if (!a) return <Empty>Analyze a JD first.</Empty>
  if (!g) return (
    <Card title="Generate">
      <p className="mb-3 text-sm text-slate-400">Build the tailored résumé from your approved evidence.</p>
      <Button onClick={engine.generate}>Generate tailored résumé</Button>
    </Card>
  )

  const jobId = a.job_id
  const save = async () => {
    const name = prompt('Name this role view:', `${g.resume.target_role} view`)
    if (name) { await engine.saveRoleProfile(name); setSavedMsg(`Saved “${name}”.`) }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <a href={api.exportUrl(jobId, 'pdf')} target="_blank" rel="noreferrer">
            <Button>Download PDF</Button></a>
          <a href={api.exportUrl(jobId, 'html')} target="_blank" rel="noreferrer">
            <Button variant="ghost">HTML</Button></a>
          <a href={api.exportUrl(jobId, 'md')} target="_blank" rel="noreferrer">
            <Button variant="ghost">Markdown</Button></a>
          <Button variant="ghost" onClick={save}>Save as role view</Button>
          {savedMsg && <span className="text-xs text-emerald-400">{savedMsg}</span>}
        </div>
        <Preview r={g.resume} />
      </div>

      <div className="space-y-4">
        <Card title="JD alignment (ATS-style)">
          <div className="text-2xl font-bold">{Math.round(g.ats.overall_score * 100)}%</div>
          <Bar label="Required skills" value={g.ats.skill_coverage} />
          <Bar label="Keywords" value={g.ats.keyword_coverage} />
          <Bar label="Requirements" value={g.ats.requirement_coverage} />
          <Bar label="Project relevance" value={g.ats.project_relevance} />
          {g.ats.missing_skills.length > 0 &&
            <p className="mt-2 text-xs text-red-300">Missing: {g.ats.missing_skills.join(', ')}</p>}
          {g.ats.potential_issues.map((i, k) => <p key={k} className="text-xs text-slate-400">⚠ {i}</p>)}
        </Card>

        <Card title="Claim validation">
          <p className="mb-2 text-xs text-slate-400">
            supported {g.validation.supported} · needs approval {g.validation.needs_approval} · unsupported {g.validation.unsupported}
          </p>
          <div className="max-h-64 space-y-1 overflow-y-auto">
            {g.validation.claims.map((c, i) => (
              <div key={i} className="flex items-start gap-2 text-xs">
                <Badge status={c.status} />
                <span className="text-slate-300">{c.text}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Original vs tailored">
          <p className="text-xs">Skills added: <b>{g.comparison.skills_added.join(', ') || '—'}</b></p>
          <p className="mt-1 text-xs text-slate-400">Dropped as irrelevant: {g.comparison.skills_dropped.join(', ') || '—'}</p>
        </Card>
      </div>
    </div>
  )
}
