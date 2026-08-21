import { useState } from 'react'
import { api } from '../api/client'
import type { Engine } from '../store'
import type { Explanation } from '../api/types'
import { Badge, Button, Card, Empty } from '../ui'

function Chips({ items, muted }: { items: string[]; muted?: boolean }) {
  return (
    <div className="flex flex-wrap gap-1">
      {items.map(s => (
        <span key={s} className={`rounded px-1.5 py-0.5 text-xs ${muted ? 'bg-slate-700/40 text-slate-400' : 'bg-sky-500/10 text-sky-300'}`}>{s}</span>
      ))}
      {!items.length && <span className="text-xs text-slate-500">—</span>}
    </div>
  )
}

function JdInput({ engine }: { engine: Engine }) {
  return (
    <Card title="Job description">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        {Object.entries(engine.sampleJds).map(([role, text]) => (
          <Button key={role} variant="ghost" onClick={() => engine.setJd(text)}>{role}</Button>
        ))}
        <label className="cursor-pointer rounded-md border border-slate-600 px-3 py-1.5 text-[13px] text-slate-200 hover:bg-slate-700/40">
          Upload JD file
          <input type="file" accept=".pdf,.docx,.txt,.md" className="hidden"
            onChange={async e => {
              const f = e.target.files?.[0]
              if (f) { const { text } = await api.extractJd(f); engine.setJd(text) }
            }} />
        </label>
      </div>
      <textarea value={engine.jdText} onChange={e => engine.setJd(e.target.value)}
        rows={8} placeholder="Paste a job description…"
        className="w-full rounded bg-slate-900 px-2 py-2 font-mono text-xs" />
      <div className="mt-2">
        <Button disabled={!engine.candidate || !engine.jdText.trim()} onClick={engine.analyze}>
          Analyze match
        </Button>
        {!engine.candidate && <span className="ml-2 text-xs text-slate-500">Load a candidate first.</span>}
      </div>
    </Card>
  )
}

export default function Analysis({ engine }: { engine: Engine }) {
  const [exp, setExp] = useState<Explanation | null>(null)
  const a = engine.analysis

  const explain = async (req: string) => {
    if (!a) return
    setExp(await api.explain(a.job_id, req))
  }

  return (
    <div className="space-y-4">
      <JdInput engine={engine} />
      {!a ? <Empty>Run an analysis to see matches, gaps and evidence.</Empty> : (
        <>
          <Card title={`Match analysis — ${a.requirements.role || 'role'}`}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-slate-400">
                  <tr><th className="py-1 pr-2">Status</th><th className="pr-2">Requirement</th>
                    <th className="pr-2">Kind</th><th className="pr-2">Score</th><th>Top evidence</th></tr>
                </thead>
                <tbody>
                  {a.matches.map((m, i) => (
                    <tr key={i} className="border-t border-slate-800">
                      <td className="py-1.5 pr-2"><Badge status={m.match_status} /></td>
                      <td className="pr-2">
                        <button className="underline decoration-dotted hover:text-sky-300"
                          onClick={() => explain(m.requirement)}>{m.requirement}</button>
                      </td>
                      <td className="pr-2 text-xs text-slate-400">{m.kind}</td>
                      <td className="pr-2 text-xs text-slate-400">{m.score}</td>
                      <td className="text-xs text-slate-400">{m.evidence[0]?.name ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {exp && (
              <div className="mt-3 rounded-lg border border-slate-700 bg-slate-900/50 p-3 text-sm">
                <div className="mb-1 flex items-center gap-2">
                  <b>Why “{exp.requirement}”?</b>
                  {exp.status && <Badge status={exp.status} />}
                </div>
                <div className="text-slate-300">{exp.reason}</div>
                <div className="mt-1 text-xs text-slate-400">
                  Evidence: {exp.evidence?.length
                    ? exp.evidence.map(e => `${e.name} (${e.type}, ${e.score})`).join('; ')
                    : 'none — genuine gap'}
                </div>
              </div>
            )}
          </Card>

          <div className="grid gap-4 md:grid-cols-2">
            <Card title="Emphasis plan">
              <div className="mb-1 text-xs text-slate-400">Emphasize</div>
              <Chips items={a.plan.emphasize} />
              <div className="mb-1 mt-3 text-xs text-slate-400">De-emphasize (not JD-relevant)</div>
              <Chips items={a.plan.deemphasize} muted />
              <div className="mb-1 mt-3 text-xs text-slate-400">Project order</div>
              <Chips items={a.plan.reorder} />
            </Card>
            <Card title={`Gaps — ${a.gaps.length}`}>
              <div className="space-y-1">
                {a.gaps.map((g, i) => (
                  <div key={i} className="rounded border border-slate-800 px-2 py-1">
                    <div className="flex items-center gap-2 text-sm">
                      <Badge status={g.category} /><span>{g.requirement}</span>
                    </div>
                    <div className="text-xs text-slate-500">{g.suggested_action}</div>
                  </div>
                ))}
                {!a.gaps.length && <Empty>No gaps — strong all round.</Empty>}
              </div>
            </Card>
          </div>
          <div><Button onClick={() => engine.setStep(2)}>Review modifications →</Button></div>
        </>
      )}
    </div>
  )
}
