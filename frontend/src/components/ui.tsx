import clsx from 'clsx'

export function Panel({
  title,
  children,
  className,
  action,
}: {
  title?: string
  children: React.ReactNode
  className?: string
  action?: React.ReactNode
}) {
  return (
    <section className={clsx('rounded-lg border border-[#1f2a3d] bg-[#111827]', className)}>
      {(title || action) && (
        <div className="flex items-center justify-between border-b border-[#1f2a3d] px-4 py-2.5">
          <h2 className="text-sm font-medium text-slate-200">{title}</h2>
          {action}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}

export function StatCard({
  label,
  value,
  hint,
  tone = 'neutral',
}: {
  label: string
  value: string | number
  hint?: string
  tone?: 'neutral' | 'ok' | 'warn' | 'crit' | 'ai'
}) {
  const toneCls = {
    neutral: 'text-slate-100',
    ok: 'text-emerald-400',
    warn: 'text-amber-400',
    crit: 'text-rose-400',
    ai: 'text-indigo-300',
  }[tone]
  return (
    <div className="rounded-lg border border-[#1f2a3d] bg-[#111827] p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className={clsx('mt-1 text-2xl font-semibold', toneCls)}>{value}</div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  )
}

export function Badge({ children, tone = 'neutral' }: { children: React.ReactNode; tone?: string }) {
  const map: Record<string, string> = {
    healthy: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    ok: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    INFO: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
    LOW: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
    MEDIUM: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    WARNING: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    HIGH: 'bg-orange-500/15 text-orange-300 border-orange-500/30',
    CRITICAL: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    critical: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    high: 'bg-orange-500/15 text-orange-300 border-orange-500/30',
    Detected: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
    Investigating: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30',
    'RCA Available': 'bg-violet-500/15 text-violet-300 border-violet-500/30',
    Resolved: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    Closed: 'bg-slate-500/15 text-slate-400 border-slate-500/30',
    neutral: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
  }
  return (
    <span className={clsx('inline-flex rounded border px-2 py-0.5 text-[11px] font-medium', map[tone] || map.neutral)}>
      {children}
    </span>
  )
}

export function Loading() {
  return <div className="animate-pulse text-sm text-slate-500">Loading…</div>
}
