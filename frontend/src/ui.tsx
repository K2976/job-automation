import type { ButtonHTMLAttributes, ReactNode, SVGProps } from 'react'

/* ------------------------------------------------------------------ icons --
   One consistent line-icon set (1.75 stroke, currentColor). Icons support
   meaning; they never replace a clear label. */
type Icon = (p: SVGProps<SVGSVGElement>) => ReactNode
const svg = (path: ReactNode): Icon => (p) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75"
    strokeLinecap="round" strokeLinejoin="round" width="1em" height="1em"
    aria-hidden="true" {...p}>{path}</svg>
)
export const icons = {
  check: svg(<path d="M20 6 9 17l-5-5" />),
  x: svg(<path d="M18 6 6 18M6 6l12 12" />),
  pencil: svg(<><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" /></>),
  upload: svg(<><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="M17 8l-5-5-5 5" /><path d="M12 3v12" /></>),
  arrowRight: svg(<path d="M5 12h14M13 6l6 6-6 6" />),
  arrowDown: svg(<path d="M12 5v14M6 13l6 6 6-6" />),
  info: svg(<><circle cx="12" cy="12" r="9" /><path d="M12 16v-4M12 8h.01" /></>),
  doc: svg(<><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z" /><path d="M14 3v5h5" /></>),
  mark: svg(<><path d="M4 20V6a2 2 0 0 1 2-2h8l6 6v10a0 0 0 0 1 0 0" /><path d="M14 4v6h6" /><path d="M8 14h6M8 17h4" /></>),
}

/* ---------------------------------------------------------------- status --
   Human labels + tone. Meaning survives without colour (text + dot). */
type Tone = 'pos' | 'warn' | 'neg' | 'accent' | 'neutral'
const LABEL: Record<string, string> = {
  ORIGINAL: 'Original', USER_CONFIRMED: 'Confirmed', USER_EDITED: 'Edited',
  AI_SUGGESTED: 'AI suggestion', GENERATED: 'Generated', REJECTED: 'Rejected',
  STRONG_MATCH: 'Strong', PARTIAL_MATCH: 'Partial', WEAK_MATCH: 'Weak',
  MISSING: 'Gap', USER_CONFIRMATION_REQUIRED: 'Confirm?',
  SUPPORTED_BY_ORIGINAL: 'Supported', SUPPORTED_BY_USER_CONFIRMATION: 'Confirmed',
  AI_SUGGESTED_NOT_APPROVED: 'Unapproved', UNSUPPORTED: 'Unsupported',
}
const TONE: Record<string, Tone> = {
  ORIGINAL: 'accent', USER_CONFIRMED: 'pos', USER_EDITED: 'pos', GENERATED: 'neutral',
  AI_SUGGESTED: 'warn', REJECTED: 'neg',
  STRONG_MATCH: 'pos', PARTIAL_MATCH: 'warn', WEAK_MATCH: 'warn',
  MISSING: 'neg', USER_CONFIRMATION_REQUIRED: 'warn',
  SUPPORTED_BY_ORIGINAL: 'pos', SUPPORTED_BY_USER_CONFIRMATION: 'pos',
  AI_SUGGESTED_NOT_APPROVED: 'warn', UNSUPPORTED: 'neg',
}
const TONE_CLASS: Record<Tone, string> = {
  pos: 'bg-success-soft text-success', warn: 'bg-warn-soft text-warn',
  neg: 'bg-danger-soft text-danger', accent: 'bg-accent-soft text-accent-ink',
  neutral: 'bg-raised text-muted',
}
const DOT: Record<Tone, string> = {
  pos: 'bg-success', warn: 'bg-warn', neg: 'bg-danger', accent: 'bg-accent',
  neutral: 'bg-faint',
}

export function statusLabel(s: string) { return LABEL[s] ?? s.replace(/_/g, ' ') }

export function Badge({ status, subtle }: { status: string; subtle?: boolean }) {
  const tone = TONE[status] ?? 'neutral'
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5
      font-mono text-[12px] font-medium tracking-tight
      ${subtle ? 'text-muted' : TONE_CLASS[tone]}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${DOT[tone]}`} />
      {statusLabel(status)}
    </span>
  )
}

/* ---------------------------------------------------------------- button -- */
type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
  icon?: Icon
}
export function Button({ variant = 'primary', size = 'md', icon: I, children, className = '', ...rest }: BtnProps) {
  const sizes = size === 'sm' ? 'h-8 px-3 text-[14px]' : 'h-10 px-4 text-[15px]'
  const variants = {
    primary: 'bg-accent text-white hover:bg-accent-hover shadow-sm',
    secondary: 'bg-surface text-ink border border-line-strong hover:bg-raised',
    ghost: 'text-ink-soft hover:bg-raised',
    danger: 'text-danger border border-danger/30 hover:bg-danger-soft',
  }[variant]
  return (
    <button className={`inline-flex items-center justify-center gap-2 rounded-md font-medium
      transition-colors disabled:opacity-45 disabled:cursor-not-allowed ${sizes} ${variants} ${className}`}
      {...rest}>
      {I && <I className="text-[1.05em]" />}{children}
    </button>
  )
}

/* ----------------------------------------------------------------- misc UI -- */
export function Surface({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-lg border border-line bg-surface ${className}`}>{children}</div>
}

export function SectionHeader({ eyebrow, title, description, action }:
  { eyebrow?: string; title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="mb-4 flex items-end justify-between gap-4">
      <div>
        {eyebrow && <div className="mb-1 font-mono text-[12px] font-medium uppercase tracking-wider text-accent">{eyebrow}</div>}
        <h2 className="text-[20px] font-semibold text-ink">{title}</h2>
        {description && <p className="mt-0.5 text-[15px] text-muted">{description}</p>}
      </div>
      {action}
    </div>
  )
}

export function Meter({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100)
  return (
    <div className="my-2">
      <div className="mb-1 flex items-baseline justify-between">
        <span className="text-[14px] text-ink-soft">{label}</span>
        <span className="font-mono text-[13px] text-muted">{pct}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-raised">
        <div className="h-full rounded-full bg-accent transition-[width]" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export function Loading({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2.5 text-[15px] text-muted">
      <span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-line-strong border-t-accent" />
      {label}
    </div>
  )
}

export function Alert({ tone = 'danger', title, children }:
  { tone?: 'danger' | 'warn' | 'info'; title?: string; children: ReactNode }) {
  const c = {
    danger: 'border-danger/25 bg-danger-soft text-danger',
    warn: 'border-warn/25 bg-warn-soft text-warn',
    info: 'border-line bg-raised text-ink-soft',
  }[tone]
  return (
    <div className={`flex gap-2.5 rounded-md border px-4 py-3 text-[15px] ${c}`}>
      <icons.info className="mt-0.5 shrink-0 text-[1.1em]" />
      <div>{title && <div className="font-semibold">{title}</div>}<div>{children}</div></div>
    </div>
  )
}

export function EmptyState({ icon: I = icons.doc, title, children, action }:
  { icon?: Icon; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-line-strong bg-surface px-6 py-12 text-center">
      <I className="mx-auto mb-3 text-[28px] text-faint" />
      <div className="text-[17px] font-medium text-ink">{title}</div>
      {children && <p className="mx-auto mt-1 max-w-md text-[15px] text-muted">{children}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
