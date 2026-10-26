import { useRef, type KeyboardEvent, type ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface TabItem<T extends string> {
  id: T
  label: string
  count?: number
}

interface Props<T extends string> {
  tabs: TabItem<T>[]
  value: T
  onChange: (id: T) => void
  label: string
  panelId: string
  children: ReactNode
}

export function Tabs<T extends string>({ tabs, value, onChange, label, panelId, children }: Props<T>) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({})

  function onKey(e: KeyboardEvent, index: number) {
    const dir = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!dir) return
    e.preventDefault()
    const next = tabs[(index + dir + tabs.length) % tabs.length]
    if (next) {
      onChange(next.id)
      refs.current[next.id]?.focus()
    }
  }

  return (
    <div>
      <div role="tablist" aria-label={label} className="flex gap-1 overflow-x-auto border-b border-line">
        {tabs.map((t, i) => (
          <button
            key={t.id}
            ref={(el) => {
              refs.current[t.id] = el
            }}
            role="tab"
            id={`${panelId}-tab-${t.id}`}
            aria-selected={value === t.id}
            aria-controls={panelId}
            tabIndex={value === t.id ? 0 : -1}
            onKeyDown={(e) => onKey(e, i)}
            onClick={() => onChange(t.id)}
            className={cn(
              '-mb-px whitespace-nowrap border-b-2 px-4 py-2.5 text-sm transition-colors',
              value === t.id
                ? 'border-brand-700 font-semibold text-ink'
                : 'border-transparent text-muted hover:text-ink',
            )}
          >
            {t.label}
            {t.count !== undefined && (
              <span className="ml-1.5 rounded bg-sunken px-1.5 py-0.5 text-xs tabular-nums text-ink-soft">
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={panelId} aria-labelledby={`${panelId}-tab-${value}`} className="pt-4">
        {children}
      </div>
    </div>
  )
}
