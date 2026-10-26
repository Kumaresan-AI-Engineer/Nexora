import { Check } from 'lucide-react'
import { cn } from '@/lib/cn'

const STEPS = ['Upload photo', 'Compare offers']

/** Progress indicator across the three-stage flow. `current` is 1-based. */
export function Stepper({ current }: { current: 1 | 2 }) {
  return (
    <ol aria-label="Progress" className="mb-6 flex items-center gap-2 text-sm">
      {STEPS.map((label, i) => {
        const n = i + 1
        const done = n < current
        const active = n === current
        return (
          <li key={label} aria-current={active ? 'step' : undefined} className="flex items-center gap-2">
            <span
              className={cn(
                'grid size-6 place-items-center rounded-full text-xs font-semibold',
                done && 'bg-brand-700 text-white',
                active && 'bg-brand-900 text-white ring-4 ring-brand-100',
                !done && !active && 'border border-line-strong bg-surface text-muted',
              )}
            >
              {done ? <Check className="size-3.5" aria-hidden /> : n}
            </span>
            <span className={cn(active ? 'font-semibold text-ink' : done ? 'text-ink-soft' : 'text-muted')}>
              {label}
            </span>
            {n < STEPS.length && <span aria-hidden className="mx-1 h-px w-8 bg-line-strong sm:w-12" />}
          </li>
        )
      })}
    </ol>
  )
}
