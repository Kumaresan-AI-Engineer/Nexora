import { CheckCircle2, ChevronDown, CircleAlert, Clock, Loader2, MinusCircle } from 'lucide-react'
import { Badge, type Tone } from '@/components/ui/feedback'
import type { Progress, SourceStatus } from '@/lib/types'

const NODE_LABEL: Record<string, string> = {
  validate_request: 'Validate request',
  analyze_image: 'Analyse image',
  resolve_product_identity: 'Resolve identity',
  check_identity_ambiguity: 'Check identity',
  discover_supplier_sources: 'Select sources',
  search_supplier_connectors: 'Search suppliers',
  extract_and_normalize_offers: 'Read supplier pages',
  deduplicate_offers: 'Merge duplicates',
  verify_offer_evidence: 'Verify evidence',
  calculate_comparable_costs: 'Calculate costs',
  rank_eligible_offers: 'Rank offers',
  finalize_results: 'Finalise',
}

const SOURCE_TONE: Record<SourceStatus['status'], Tone> = {
  pending: 'info',
  ok: 'ok',
  timeout: 'warn',
  error: 'danger',
  skipped: 'neutral',
}
const SOURCE_LABEL: Record<SourceStatus['status'], string> = {
  pending: 'Searching',
  ok: 'Done',
  timeout: 'Timed out',
  error: 'Failed',
  skipped: 'Not configured',
}
const SOURCE_ICON = { pending: Loader2, ok: CheckCircle2, timeout: Clock, error: CircleAlert, skipped: MinusCircle }

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-line bg-canvas px-3 py-2.5">
      <dt className="text-xs font-medium text-muted">{label}</dt>
      <dd className="mt-0.5 text-xl font-semibold tabular-nums">{value}</dd>
    </div>
  )
}

/** Slim live status line, shown only while a search is running. */
export function LiveStatus({ progress, streaming }: { progress: Progress; streaming: boolean }) {
  if (progress.finished) return null
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line bg-surface px-4 py-2.5">
      <p className="flex items-center gap-2 text-sm font-medium">
        <Loader2 className="size-4 animate-spin text-brand-700" aria-hidden />
        <span aria-live="polite">{progress.message || 'Working…'}</span>
      </p>
      <span className="text-xs text-muted">{streaming ? 'Live updates' : 'Refreshing every 2 s'}</span>
    </div>
  )
}

/** Technical detail (counts, sources, unresolved items). Collapsed once the search has finished cleanly. */
export function SearchDetailsPanel({ progress }: { progress: Progress }) {
  const done = progress.sources.filter((s) => s.status !== 'pending' && s.status !== 'skipped').length
  const active = progress.sources.filter((s) => s.status !== 'skipped').length
  const trouble = progress.sources.some((s) => s.status === 'error' || s.status === 'timeout')
  return (
    <details open={!progress.finished || trouble} className="group" aria-label="Search details">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-3.5">
        <span className="text-sm font-semibold">
          Search details
          <span className="ml-2 font-normal text-ink-soft">
            {done} of {active} sources done
            {progress.unresolved.length > 0 && `, ${progress.unresolved.length} unresolved`}
          </span>
        </span>
        <ChevronDown className="size-4 shrink-0 text-muted transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <div className="border-t border-line p-5">
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <Stat label="Discovered" value={progress.offers_discovered} />
          <Stat label="Source-verified" value={progress.offers_verified} />
          <Stat label="Partially verified" value={progress.offers_partially_verified} />
          <Stat label="Unverified" value={progress.offers_unverified} />
          <Stat label="Rejected" value={progress.offers_rejected} />
        </dl>

        {progress.sources.length > 0 && (
          <div className="mt-4">
            <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted">Sources</h3>
            <ul className="divide-y divide-line rounded-md border border-line">
              {progress.sources.map((s) => {
                const Icon = SOURCE_ICON[s.status]
                return (
                  <li
                    key={s.connector_id}
                    className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm"
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <Icon className={`size-4 shrink-0 ${s.status === 'pending' ? 'animate-spin' : ''}`} aria-hidden />
                      <span className="truncate">{s.name}</span>
                      {s.is_demo && <Badge tone="warn">Fictional</Badge>}
                    </span>
                    <span className="flex items-center gap-2 text-xs text-muted">
                      {s.status === 'ok' && <span>{s.offers} candidate(s)</span>}
                      {s.attempts > 1 && <span>{s.attempts} attempts</span>}
                      <Badge tone={SOURCE_TONE[s.status]}>{SOURCE_LABEL[s.status]}</Badge>
                    </span>
                    {s.error && <p className="w-full pl-6 text-xs text-ink-soft">{s.error}</p>}
                  </li>
                )
              })}
            </ul>
          </div>
        )}

        {progress.unresolved.length > 0 && (
          <div className="mt-4">
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Unresolved</h3>
            <ul className="list-disc pl-5 text-sm text-ink-soft">
              {progress.unresolved.slice(0, 6).map((u) => (
                <li key={u}>{u}</li>
              ))}
              {progress.unresolved.length > 6 && <li>and {progress.unresolved.length - 6} more</li>}
            </ul>
          </div>
        )}

        {progress.completed_nodes.length > 0 && (
          <details className="mt-4 text-sm">
            <summary className="cursor-pointer text-xs text-muted">
              Workflow steps completed ({progress.completed_nodes.length})
            </summary>
            <ol className="mt-2 flex flex-wrap gap-1.5">
              {progress.completed_nodes.map((n, i) => (
                <li key={`${n}-${i}`}>
                  <Badge tone="neutral">{NODE_LABEL[n] ?? n}</Badge>
                </li>
              ))}
            </ol>
          </details>
        )}
      </div>
    </details>
  )
}
