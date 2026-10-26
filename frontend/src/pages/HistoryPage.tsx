import { Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/Button'
import { Alert, Badge, EmptyState, Spinner } from '@/components/ui/feedback'
import { useDeleteSearch, useSearches } from '@/hooks/queries'
import { formatDateTime, STATE_LABEL } from '@/lib/format'
import { STATE_TONE } from '@/lib/stateTone'

export function HistoryPage() {
  const { data, isLoading, error } = useSearches(50)
  const del = useDeleteSearch()

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-semibold tracking-tight">Search history</h1>
      <p className="mt-1 text-sm text-ink-soft">
        Searches from this browser session. Deleting a search removes its results from your history.
      </p>

      <div className="mt-6">
        {isLoading && <Spinner label="Loading history…" />}
        {error && (
          <Alert tone="danger" title="Could not load history">
            {error.message}
          </Alert>
        )}
        {del.error && (
          <Alert tone="danger" title="Could not delete the search">
            {del.error.message}
          </Alert>
        )}
        {data && data.items.length === 0 && (
          <EmptyState
            title="No searches yet"
            action={
              <Link to="/" className="text-sm font-medium text-brand-700 underline">
                Identify a product
              </Link>
            }
          >
            Searches you run will appear here.
          </EmptyState>
        )}
        {data && data.items.length > 0 && (
          <ul className="divide-y divide-line rounded-md border border-line bg-surface">
            {data.items.map((s) => (
              <li key={s.id} className="flex items-center gap-2 pr-2">
                <Link
                  to={`/searches/${s.id}`}
                  className="flex min-w-0 flex-1 items-center justify-between gap-3 px-4 py-3 hover:bg-sunken"
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium">{s.product_label}</span>
                    <span className="block text-xs text-muted">
                      {formatDateTime(s.created_at)} · {s.options.mode} · {s.options.market} · {s.offers_discovered}{' '}
                      candidate offer(s)
                    </span>
                  </span>
                  <Badge tone={STATE_TONE[s.state]}>{STATE_LABEL[s.state]}</Badge>
                </Link>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Delete search for ${s.product_label}`}
                  onClick={() => del.mutate(s.id)}
                  disabled={del.isPending}
                >
                  <Trash2 className="size-4" aria-hidden />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
