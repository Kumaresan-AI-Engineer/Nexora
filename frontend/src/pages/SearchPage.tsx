import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { Stepper } from '@/components/layout/Stepper'
import { AgentActivity } from '@/components/results/AgentActivity'
import { IdentifiedPanel } from '@/components/results/IdentifiedPanel'
import { OffersSection } from '@/components/results/OffersSection'
import { RefinePanel } from '@/components/results/RefinePanel'
import { ResultsHero } from '@/components/results/ResultsHero'
import { SearchDetailsPanel } from '@/components/results/SearchProgressPanel'
import { Button } from '@/components/ui/Button'
import { Alert, EmptyState, Spinner } from '@/components/ui/feedback'
import { useSearchLive } from '@/hooks/queries'
import { ApiError } from '@/lib/api'
import type { SearchDetail } from '@/lib/types'
import { useDiscovery } from '@/store/discovery'

function StateNotice({ d }: { d: SearchDetail }) {
  const { state, message } = d.progress
  if (!d.is_terminal) return null
  switch (state) {
    case 'NEEDS_CLARIFICATION':
      return (
        <Alert tone="warn" title="We could not identify the product">
          {message}
        </Alert>
      )
    case 'SOURCE_UNAVAILABLE':
      return (
        <Alert tone="danger" title="No supplier source could be searched">
          {message} Check the source list below, and the configuration notes in the README (for example TAVILY_API_KEY,
          or DEMO_MODE=true to see clearly labelled fictional data).
        </Alert>
      )
    case 'NO_MATCHES':
      return (
        <Alert tone="info" title="No matching offers found">
          {message} Try correcting the product details, or use a clearer image.
        </Alert>
      )
    case 'PARTIAL_RESULTS':
      return (
        <Alert tone="warn" title="Results may be incomplete">
          {message}
        </Alert>
      )
    case 'FAILED':
      return (
        <Alert tone="danger" title="The search failed">
          {d.progress.error ?? message}
        </Alert>
      )
    default:
      return null
  }
}

export function SearchPage() {
  const { id = '' } = useParams()
  const { data, error, isLoading, refetch, streaming } = useSearchLive(id)
  const { priceFilter } = useDiscovery()

  if (isLoading) {
    return (
      <div className="py-16 text-center">
        <Spinner label="Loading search…" />
      </div>
    )
  }
  if (error || !data) {
    const notFound = error instanceof ApiError && error.status === 404
    return notFound ? (
      <EmptyState
        title="Search not found"
        action={
          <Link to="/" className="text-sm font-medium text-brand-700 underline">
            Start a new search
          </Link>
        }
      >
        It may have been deleted, or it belongs to a different browser session.
      </EmptyState>
    ) : (
      <Alert tone="danger" title="Could not load this search">
        {error instanceof Error ? error.message : 'Unknown error.'}
        <div className="mt-2">
          <Button variant="secondary" size="sm" onClick={() => void refetch()}>
            Retry
          </Button>
        </div>
      </Alert>
    )
  }

  const o = data.options

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Stepper current={2} />
        <Link to="/" className="inline-flex items-center gap-1 text-sm text-ink-soft hover:text-ink">
          <ArrowLeft className="size-4" aria-hidden /> New search
        </Link>
      </div>

      <ResultsHero detail={data} />

      {data.is_demo_data_present && (
        <Alert tone="warn" title="Demonstration data present">
          Some rows come from fictional fixtures. Their suppliers, prices and links are not real, and they are never
          shown as verified.
        </Alert>
      )}

      <StateNotice d={data} />

      <AgentActivity progress={data.progress} streaming={streaming} />

      {data.offers.length > 0 && (
        <OffersSection
          offers={data.offers}
          options={o}
          finished={data.is_terminal}
          initialPrice={{ min: priceFilter.min, max: priceFilter.max }}
        />
      )}

      <div className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface shadow-[0_1px_2px_rgba(14,35,48,0.05)]">
        <SearchDetailsPanel progress={data.progress} />
        {data.is_terminal && <IdentifiedPanel key={`identified-${data.id}`} detail={data} />}
        {data.is_terminal && data.progress.state !== 'NEEDS_CLARIFICATION' && (
          <RefinePanel key={`refine-${data.id}`} detail={data} />
        )}
      </div>
    </div>
  )
}
