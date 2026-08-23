import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type {
  ApplicationSummary, ApplicationTask, ApprovalMode, Opportunity,
} from '../api/types'
import { useApplications, type AppsEngine } from '../applications'
import { Alert, Badge, Button, EmptyState, Loading, SectionHeader, Surface, icons } from '../ui'

const MODES: { id: ApprovalMode; label: string; hint: string }[] = [
  { id: 'MANUAL', label: 'Manual', hint: 'Fill only — you submit on the site yourself.' },
  { id: 'REVIEW_BEFORE_SUBMIT', label: 'Review before submit',
    hint: 'Agent fills; you approve each before it submits.' },
  { id: 'AUTONOMOUS', label: 'Autonomous',
    hint: 'Submits automatically when everything is safely resolved.' },
]

// Poll the automation worker's liveness. Tolerates the endpoint being absent/empty (older
// backend or test mock) by staying "offline" rather than throwing.
function WorkerBadge() {
  const [w, setW] = useState<{ online?: boolean; inline?: boolean } | null>(null)
  useEffect(() => {
    let alive = true
    const tick = () => api.workerStatus().then(s => alive && setW(s)).catch(() => {})
    tick()
    const id = setInterval(tick, 8000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  // In-process mode (local dev): the backend runs the browser itself — no separate worker.
  if (w?.inline) return null
  const online = !!w?.online
  return (
    <div className="mb-5 flex items-center gap-2.5 rounded-lg border border-default px-3 py-2">
      <span className={`h-2 w-2 rounded-full ${online ? 'bg-emerald-500' : 'bg-slate-400'}`} />
      <span className="text-sm font-medium">Automation worker</span>
      <span className="text-sm text-muted">
        {online
          ? 'Online — ready to process applications.'
          : 'Offline — start the local browser worker to enable automated applications.'}
      </span>
    </div>
  )
}

export default function Applications({ candidateId, active }: { candidateId: number | null; active?: boolean }) {
  const eng = useApplications(candidateId, active)
  const [detail, setDetail] = useState<number | null>(null)

  if (!candidateId)
    return <EmptyState title="Load your profile first">
      Application automation runs on batches you prepared under Opportunities.
    </EmptyState>

  return (
    <div>
      <WorkerBadge />
      {eng.error && <div className="mb-5"><Alert title="Something went wrong">{eng.error}</Alert></div>}
      {eng.busy && <div className="mb-5"><Loading label={eng.busy} /></div>}

      <SectionHeader title="Application batches"
        description="Create browser tasks for a prepared batch, choose how much you want to approve, and run them. Nothing is submitted unless you allow it." />

      {eng.batches.length === 0
        ? <EmptyState title="No batches yet">
            Prepare a batch of opportunities under Opportunities → Results first.
          </EmptyState>
        : <div className="grid gap-3">
            {eng.batches.map(b => <BatchRow key={b.id} eng={eng} batchId={b.id} />)}
          </div>}

      {eng.tasks.length > 0 &&
        <div className="mt-8">
          <SectionHeader title="Application queue"
            description="Each task drives one application in an isolated browser. You stay in control of submission." />
          <div className="grid gap-2">
            {eng.tasks.map(t => (
              <TaskRow key={t.id} eng={eng} task={t} opp={eng.opps[t.opportunity_id]}
                onView={() => setDetail(t.id)} />
            ))}
          </div>
        </div>}

      {detail !== null &&
        <TaskDetail eng={eng} taskId={detail} onClose={() => setDetail(null)} />}
    </div>
  )
}

function BatchRow({ eng, batchId }: { eng: AppsEngine; batchId: number }) {
  const batch = eng.batches.find(b => b.id === batchId)!
  const [mode, setMode] = useState<ApprovalMode>(
    (batch.approval_mode as ApprovalMode) || 'REVIEW_BEFORE_SUBMIT')
  const tasks = eng.tasks.filter(t => t.batch_id === batchId)

  return (
    <Surface className="p-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex-1">
          <div className="text-[16px] font-semibold text-ink">{batch.name}</div>
          <div className="text-[13px] text-muted">
            {tasks.length} task{tasks.length === 1 ? '' : 's'} · max {batch.max_opportunities}
          </div>
        </div>
        <select className={inputCls + ' w-52'} value={mode}
          onChange={e => setMode(e.target.value as ApprovalMode)}>
          {MODES.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
        </select>
        {tasks.length === 0
          ? <Button size="sm" onClick={() => eng.createTasks(batchId, mode)}>Create tasks</Button>
          : <Button size="sm" icon={icons.arrowRight} disabled={!!eng.busy}
              onClick={() => eng.startBatch(batchId)}>Run batch</Button>}
      </div>
      <p className="mt-2 text-[13px] text-faint">{MODES.find(m => m.id === mode)?.hint}</p>
    </Surface>
  )
}

function TaskRow({ eng, task, opp, onView }:
  { eng: AppsEngine; task: ApplicationTask; opp?: Opportunity; onView: () => void }) {
  const title = opp ? `${opp.title} · ${opp.company}` : `Opportunity #${task.opportunity_id}`
  const canApprove = task.approval_mode === 'REVIEW_BEFORE_SUBMIT' &&
    task.status === 'REVIEW_REQUIRED'
  const canRetry = task.status === 'FAILED' || task.status === 'BLOCKED'
  return (
    <Surface className="flex flex-wrap items-center gap-3 p-3">
      <button onClick={onView} className="min-w-0 flex-1 truncate text-left">
        <span className="text-[15px] text-ink hover:text-accent">{title}</span>
      </button>
      <Badge status={task.status} />
      <div className="flex gap-1.5">
        {(task.status === 'READY' || task.status === 'QUEUED') &&
          <Button size="sm" variant="secondary" disabled={!!eng.busy}
            onClick={() => eng.startTask(task.id)}>Start</Button>}
        {canApprove &&
          <Button size="sm" disabled={!!eng.busy}
            onClick={() => eng.approve(task.id)}>Approve &amp; submit</Button>}
        {canRetry && task.retry_count < 2 &&
          <Button size="sm" variant="secondary"
            onClick={() => eng.control(task.id, 'retry')}>Retry</Button>}
        {task.status !== 'CANCELLED' && task.status !== 'CONFIRMED' &&
          <Button size="sm" variant="ghost"
            onClick={() => eng.control(task.id, 'cancel')}>Cancel</Button>}
      </div>
    </Surface>
  )
}

function TaskDetail({ eng, taskId, onClose }:
  { eng: AppsEngine; taskId: number; onClose: () => void }) {
  const [data, setData] = useState<{ task: ApplicationTask; summary: ApplicationSummary } | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  useEffect(() => { api.getApplication(taskId).then(setData).catch(() => {}) }, [taskId, eng.tasks])

  const t = data?.task
  const s = data?.summary
  const opp = t ? eng.opps[t.opportunity_id] : undefined
  const needsInput = t && (t.status === 'USER_ACTION_REQUIRED' || t.status === 'LOGIN_REQUIRED')

  return (
    <div className="fixed inset-0 z-30 flex items-end bg-black/30" onClick={onClose}>
      <div className="sheet-panel h-1/2 w-full overflow-y-auto rounded-t-xl bg-surface p-6 shadow-xl"
        onClick={e => e.stopPropagation()}>
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-[20px] font-bold text-ink">
              {opp ? `${opp.title} · ${opp.company}` : `Task #${taskId}`}
            </h2>
            {t && <div className="mt-1"><Badge status={t.status} /></div>}
          </div>
          <Button size="sm" variant="ghost" icon={icons.x} onClick={onClose}>Close</Button>
        </div>

        {!t && <Loading label="Loading task…" />}
        {t && s &&
          <div className="grid gap-5">
            <Surface className="grid grid-cols-2 gap-2 p-4 text-[14px]">
              <Stat label="Questions" value={s.questions} />
              <Stat label="Deterministic" value={s.deterministic} />
              <Stat label="LLM-generated" value={s.llm_generated} />
              <Stat label="You provided" value={s.user_provided} />
              <Stat label="Unresolved" value={s.unresolved} strong={s.unresolved > 0} />
              <Stat label="Can submit" value={s.can_submit ? 'yes' : 'no'} />
            </Surface>

            {t.error_message &&
              <Alert tone="warn" title={t.error_code || 'Note'}>{t.error_message}</Alert>}
            {t.status === 'BLOCKED' &&
              <Alert tone="warn" title="Blocked">
                A CAPTCHA or anti-bot challenge was detected. The agent stopped and did not
                attempt to bypass it. You can take this application over manually.
              </Alert>}
            {t.confirmation_reference &&
              <Alert tone="info" title="Confirmation">“{t.confirmation_reference}”</Alert>}

            {needsInput && s.unresolved_questions.length > 0 &&
              <Surface className="p-4">
                <div className="mb-2 text-[14px] font-semibold text-ink">Questions needing your answer</div>
                {s.unresolved_questions.map(q => (
                  <label key={q.key} className="mb-3 block">
                    <span className="mb-1 block text-[14px] text-ink-soft">{q.text}</span>
                    <input className={inputCls}
                      onChange={e => setAnswers(a => ({ ...a, [q.key]: e.target.value }))} />
                  </label>
                ))}
                <Button size="sm" disabled={!!eng.busy}
                  onClick={() => eng.provideAnswers(t.id, answers)}>Save &amp; continue</Button>
              </Surface>}

            <div>
              <div className="mb-1.5 text-[14px] font-semibold text-ink">Answered fields</div>
              <div className="grid gap-1 text-[13px]">
                {t.questions.map((q, i) => (
                  <div key={i} className="flex items-center justify-between gap-3">
                    <span className="truncate text-muted">{q.question_text || q.name}</span>
                    <Badge status={q.requires_review ? 'AI_SUGGESTED_NOT_APPROVED'
                      : q.answer ? 'USER_CONFIRMED' : 'MISSING'} subtle />
                  </div>
                ))}
              </div>
            </div>

            <details>
              <summary className="cursor-pointer text-[14px] text-ink-soft">Activity log</summary>
              <ol className="mt-2 grid gap-1 font-mono text-[12px] text-muted">
                {t.logs.map((e, i) => <li key={i}>{e.event}{e.detail ? ` — ${e.detail}` : ''}</li>)}
              </ol>
            </details>
          </div>}
      </div>
    </div>
  )
}

const inputCls = 'w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-[15px] text-ink outline-none focus:border-accent'

function Stat({ label, value, strong }: { label: string; value: number | string; strong?: boolean }) {
  return (
    <div className="flex items-baseline justify-between">
      <span className="text-muted">{label}</span>
      <span className={`font-mono ${strong ? 'font-semibold text-warn' : 'text-ink-soft'}`}>{value}</span>
    </div>
  )
}
