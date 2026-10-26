import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  FileText,
  Globe,
  Info,
  ListOrdered,
  Loader2,
  ShieldCheck,
  XCircle,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useRef } from 'react'
import { cn } from '@/lib/cn'
import { elapsedSeconds, phaseStates, type StageId } from '@/lib/activity'
import type { ActivityEvent, Progress } from '@/lib/types'

const PHASES: { id: StageId; label: string; icon: LucideIcon }[] = [
  { id: 'plan', label: 'Plan', icon: ClipboardList },
  { id: 'search', label: 'Search sources', icon: Globe },
  { id: 'read', label: 'Read pages', icon: FileText },
  { id: 'verify', label: 'Verify and price', icon: ShieldCheck },
  { id: 'rank', label: 'Rank', icon: ListOrdered },
]

const LEVEL: Record<ActivityEvent['level'], { icon: LucideIcon; cls: string }> = {
  info: { icon: Info, cls: 'text-info-fg' },
  success: { icon: CheckCircle2, cls: 'text-ok-fg' },
  warn: { icon: AlertTriangle, cls: 'text-warn-fg' },
  error: { icon: XCircle, cls: 'text-danger-fg' },
}

export function AgentActivity({ progress, streaming }: { progress: Progress; streaming: boolean }) {
  const running = !progress.finished
  const events = progress.activity
  const states = phaseStates(progress)
  const feedRef = useRef<HTMLOListElement>(null)
  const t0 = events[0] ? new Date(events[0].at).getTime() : 0
  const total = elapsedSeconds(progress)

  useEffect(() => {
    const el = feedRef.current
    if (running && el) el.scrollTop = el.scrollHeight
  }, [events.length, running])

  return (
    <details
      open={running}
      aria-label="Agent activity"
      className="group overflow-hidden rounded-xl border border-line bg-surface shadow-[0_1px_2px_rgba(14,35,48,0.05)]"
    >
      <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-3 px-5 py-4">
        <span className="flex items-center gap-3">
          {running ? (
            <span className="relative flex size-2.5" aria-hidden>
              <span className="absolute inline-flex size-full animate-pulse-dot rounded-full bg-brand-600" />
              <span className="relative inline-flex size-2.5 rounded-full bg-brand-600" />
            </span>
          ) : (
            <CheckCircle2 className="size-4 text-brand-700" aria-hidden />
          )}
          <span className="text-[15px] font-semibold">Agent activity</span>
          <span className="text-sm text-ink-soft">
            {running
              ? streaming
                ? 'Live updates'
                : 'Refreshing every 2 s'
              : `${events.length} steps${total !== null ? ` in ${total.toFixed(1)} s` : ''}`}
          </span>
        </span>
        <ChevronDown className="size-4 shrink-0 text-muted transition-transform group-open:rotate-180" aria-hidden />
      </summary>

      <div className="border-t border-line">
        {running && (
          <p className="flex items-center gap-2 bg-brand-50 px-5 py-2.5 text-sm font-medium text-brand-900">
            <Loader2 className="size-4 animate-spin text-brand-700" aria-hidden />
            <span aria-live="polite">{progress.message || 'Working…'}</span>
          </p>
        )}

        <ol aria-label="Pipeline stages" className="flex flex-wrap gap-2 px-5 py-4">
          {PHASES.map(({ id, label, icon: Icon }, i) => {
            const st = states[id]
            return (
              <li
                key={id}
                data-state={st}
                className={cn(
                  'flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors',
                  st === 'done' && 'border-brand-600/30 bg-brand-50 text-brand-900',
                  st === 'active' && 'border-brand-700 bg-brand-900 text-white shadow-sm',
                  st === 'pending' && 'border-line bg-canvas text-muted',
                  st === 'skipped' && 'border-dashed border-line bg-canvas text-muted line-through decoration-muted/50',
                )}
              >
                <span className="grid size-4 place-items-center" aria-hidden>
                  {st === 'done' ? (
                    <Check className="size-3.5" />
                  ) : st === 'active' ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <Icon className="size-3.5" />
                  )}
                </span>
                {i + 1}. {label}
              </li>
            )
          })}
        </ol>

        {events.length > 0 && (
          <ol
            ref={feedRef}
            aria-label="Activity log"
            className="max-h-72 divide-y divide-line overflow-y-auto border-t border-line bg-canvas/60"
          >
            {events.map((e, i) => {
              const { icon: Icon, cls } = LEVEL[e.level]
              const rel = ((new Date(e.at).getTime() - t0) / 1000).toFixed(1)
              return (
                <li key={`${e.at}-${i}`} className="flex items-start gap-3 px-5 py-2.5 text-sm animate-feed-in">
                  <Icon className={cn('mt-0.5 size-4 shrink-0', cls)} aria-hidden />
                  <span className="min-w-0 flex-1">{e.message}</span>
                  <time className="shrink-0 font-mono text-xs tabular-nums text-muted" dateTime={e.at}>
                    +{rel}s
                  </time>
                </li>
              )
            })}
          </ol>
        )}
      </div>
    </details>
  )
}
