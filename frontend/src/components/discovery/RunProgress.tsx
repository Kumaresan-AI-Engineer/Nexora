import { Check, Loader2 } from 'lucide-react'
import { useObjectUrl } from '@/hooks/useObjectUrl'
import { cn } from '@/lib/cn'

export interface IdentifiedSummary {
  name: string
  chips: string[]
  seconds: number
}

interface Props {
  file: File
  stage: 'reading' | 'searching'
  providerName: string
  identified: IdentifiedSummary | null
}

type StepState = 'done' | 'active' | 'pending'

function Step({ state, title, children }: { state: StepState; title: string; children?: React.ReactNode }) {
  return (
    <li className="flex gap-3">
      <span
        aria-hidden
        className={cn(
          'mt-0.5 grid size-6 shrink-0 place-items-center rounded-full text-xs',
          state === 'done' && 'bg-brand-700 text-white',
          state === 'active' && 'bg-brand-900 text-white ring-4 ring-brand-100',
          state === 'pending' && 'border border-line-strong bg-surface text-muted',
        )}
      >
        {state === 'done' ? (
          <Check className="size-3.5" />
        ) : state === 'active' ? (
          <Loader2 className="size-3.5 animate-spin" />
        ) : null}
      </span>
      <div className={cn('min-w-0', state === 'pending' && 'text-muted')}>
        <p className={cn('text-sm', state === 'active' ? 'font-semibold' : 'font-medium')}>{title}</p>
        {children}
      </div>
    </li>
  )
}

/** What is happening right after upload. Every step reflects a real request, not a timer. */
export function RunProgress({ file, stage, providerName, identified }: Props) {
  const url = useObjectUrl(file)
  const reading = stage === 'reading'

  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-5 sm:flex-row">
      <div className="relative h-44 w-full shrink-0 overflow-hidden rounded-lg border border-line bg-sunken sm:w-44">
        {url && <img src={url} alt="Image being analysed" className="size-full object-contain" />}
        {reading && (
          <span
            aria-hidden
            className="absolute inset-x-0 h-0.5 animate-scan bg-brand-600 shadow-[0_0_12px_2px_rgba(15,118,110,0.7)]"
          />
        )}
      </div>
      <ol className="flex min-w-0 flex-1 flex-col gap-4">
        <Step
          state={reading ? 'active' : 'done'}
          title={reading ? `Reading the pack with ${providerName}…` : `Read the pack with ${providerName}`}
        >
          <p className="text-xs text-muted">
            {reading
              ? 'Extracting the name, strength, form and pack size. Anything unreadable is left blank.'
              : identified
                ? `Done in ${identified.seconds.toFixed(1)} s`
                : null}
          </p>
        </Step>
        <Step
          state={identified ? 'done' : 'pending'}
          title={identified ? `Identified: ${identified.name}` : 'Identify the product'}
        >
          {identified && identified.chips.length > 0 && (
            <ul className="mt-1.5 flex flex-wrap gap-1.5">
              {identified.chips.map((c) => (
                <li
                  key={c}
                  className="rounded-md border border-line bg-surface px-2 py-0.5 text-xs font-medium text-ink-soft"
                >
                  {c}
                </li>
              ))}
            </ul>
          )}
        </Step>
        <Step state={stage === 'searching' ? 'active' : 'pending'} title="Starting the supplier search">
          {stage === 'searching' && <p className="text-xs text-muted">Opening the live activity view…</p>}
        </Step>
      </ol>
    </div>
  )
}
