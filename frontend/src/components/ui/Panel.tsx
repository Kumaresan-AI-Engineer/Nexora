import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

interface Props {
  title?: string
  description?: string
  step?: number
  actions?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
  labelledBy?: string
}

/** Standard content container: bordered surface with an optional titled header. */
export function Panel({ title, description, step, actions, children, className, bodyClassName, labelledBy }: Props) {
  const headingId = labelledBy ?? (title ? `panel-${title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}` : undefined)
  return (
    <section
      aria-labelledby={title ? headingId : undefined}
      className={cn('rounded-xl border border-line bg-surface shadow-[0_1px_2px_rgba(14,35,48,0.05)]', className)}
    >
      {title && (
        <header className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div className="flex items-start gap-3">
            {step !== undefined && (
              <span
                aria-hidden
                className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-brand-900 text-xs font-semibold text-white"
              >
                {step}
              </span>
            )}
            <div>
              <h2 id={headingId} className="text-[15px] font-semibold leading-6 text-ink">
                {title}
              </h2>
              {description && <p className="text-sm text-ink-soft">{description}</p>}
            </div>
          </div>
          {actions}
        </header>
      )}
      <div className={cn('p-5', bodyClassName)}>{children}</div>
    </section>
  )
}
