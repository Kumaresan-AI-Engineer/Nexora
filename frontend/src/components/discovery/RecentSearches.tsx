import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/feedback'
import { Panel } from '@/components/ui/Panel'
import { STATE_TONE } from '@/lib/stateTone'
import { useSearches } from '@/hooks/queries'
import { formatDateTime, STATE_LABEL } from '@/lib/format'

export function RecentSearches({ limit = 5 }: { limit?: number }) {
  const { data, isLoading } = useSearches(limit)
  if (isLoading || !data || data.items.length === 0) return null
  return (
    <Panel
      title="Recent searches"
      bodyClassName="p-0"
      actions={
        <Link to="/history" className="text-sm text-brand-700 underline-offset-2 hover:underline">
          View all
        </Link>
      }
    >
      <ul className="divide-y divide-line">
        {data.items.map((s) => (
          <li key={s.id}>
            <Link
              to={`/searches/${s.id}`}
              className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-sunken"
            >
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium">{s.product_label}</span>
                <span className="block text-xs text-muted">
                  {formatDateTime(s.created_at)} · {s.options.mode} · {s.options.market}
                </span>
              </span>
              <Badge tone={STATE_TONE[s.state]}>{STATE_LABEL[s.state]}</Badge>
            </Link>
          </li>
        ))}
      </ul>
    </Panel>
  )
}
