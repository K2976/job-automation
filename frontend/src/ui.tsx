import type { ReactNode } from 'react'

// Status → colour bucket. Green = trustworthy/supported, amber = needs attention,
// red = missing/unsupported.
const GREEN = new Set([
  'STRONG_MATCH', 'SUPPORTED_BY_ORIGINAL', 'USER_CONFIRMED', 'USER_EDITED', 'ORIGINAL',
])
const AMBER = new Set([
  'PARTIAL_MATCH', 'WEAK_MATCH', 'SUPPORTED_BY_USER_CONFIRMATION', 'AI_SUGGESTED',
])
const RED = new Set([
  'MISSING', 'UNSUPPORTED', 'USER_CONFIRMATION_REQUIRED', 'AI_SUGGESTED_NOT_APPROVED',
  'REJECTED',
])

export function badgeClass(status: string): string {
  if (GREEN.has(status)) return 'bg-emerald-500/15 text-emerald-400'
  if (AMBER.has(status)) return 'bg-amber-500/15 text-amber-400'
  if (RED.has(status)) return 'bg-red-500/15 text-red-400'
  return 'bg-slate-500/15 text-slate-300'
}

export function Badge({ status }: { status: string }) {
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold ${badgeClass(status)}`}>
      {status.replace(/_/g, ' ')}
    </span>
  )
}

export function Card({ title, children, className = '' }:
  { title?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-slate-700/60 bg-slate-800/40 p-4 ${className}`}>
      {title && <h2 className="mb-3 text-sm font-semibold text-sky-400">{title}</h2>}
      {children}
    </section>
  )
}

export function Button({ children, onClick, variant = 'primary', disabled, className = '', title }:
  {
    children: ReactNode; onClick?: () => void; disabled?: boolean
    variant?: 'primary' | 'ghost' | 'danger'; className?: string; title?: string
  }) {
  const base = 'rounded-md px-3 py-1.5 text-[13px] font-medium transition disabled:opacity-40 disabled:cursor-not-allowed'
  const styles = {
    primary: 'bg-sky-600 text-white hover:bg-sky-500',
    ghost: 'border border-slate-600 text-slate-200 hover:bg-slate-700/40',
    danger: 'border border-red-600/60 text-red-300 hover:bg-red-600/15',
  }[variant]
  return (
    <button className={`${base} ${styles} ${className}`} onClick={onClick}
      disabled={disabled} title={title}>{children}</button>
  )
}

export function Bar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100)
  return (
    <div className="my-1.5">
      <div className="flex justify-between text-xs">
        <span>{label}</span><span className="text-slate-400">{pct}%</span>
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded bg-slate-900">
        <div className="h-full bg-sky-500" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export function Spinner({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-400">
      <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-600 border-t-sky-400" />
      {label}
    </div>
  )
}

export function ErrorNote({ message }: { message: string }) {
  return <div className="rounded-md border border-red-600/40 bg-red-600/10 px-3 py-2 text-sm text-red-300">{message}</div>
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-lg border border-dashed border-slate-700 px-4 py-6 text-center text-sm text-slate-500">{children}</div>
}
