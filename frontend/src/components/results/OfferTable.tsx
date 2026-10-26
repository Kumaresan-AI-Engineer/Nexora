import { ArrowDown, ArrowUp, ChevronDown, ChevronRight, ExternalLink } from 'lucide-react'
import { Fragment, useState } from 'react'
import { Badge } from '@/components/ui/feedback'
import { cn } from '@/lib/cn'
import { AVAILABILITY_LABEL, formatMoney, relativeAge, safeExternalUrl } from '@/lib/format'
import type { SortDir, SortKey } from '@/lib/offers'
import type { BuyingMode, Offer } from '@/lib/types'
import { OfferDetail } from './OfferDetail'
import { VerificationBadge } from './VerificationBadge'

interface Props {
  offers: Offer[]
  mode: BuyingMode
  sortKey: SortKey
  sortDir: SortDir
  onSort: (key: SortKey) => void
  quantity: number
}

const TH = 'px-4 py-3 font-semibold'

function SortHeader({
  label,
  k,
  props,
  align = 'left',
}: {
  label: string
  k: SortKey
  props: Props
  align?: 'left' | 'right'
}) {
  const active = props.sortKey === k
  const Icon = props.sortDir === 'asc' ? ArrowUp : ArrowDown
  return (
    <th
      scope="col"
      aria-sort={active ? (props.sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
      className={cn(TH, align === 'right' && 'text-right')}
    >
      <button
        onClick={() => props.onSort(k)}
        className={cn('inline-flex items-center gap-1 uppercase tracking-wider hover:text-ink', active && 'text-ink')}
      >
        {label}
        {active && <Icon className="size-3" aria-hidden />}
      </button>
    </th>
  )
}

function PriceCell({ o }: { o: Offer }) {
  const p = o.pricing
  return (
    <div className="text-right tabular-nums">
      {p.pack_price !== null ? (
        <span className="text-[15px] font-semibold">{formatMoney(p.pack_price, p.target_currency)}</span>
      ) : p.pack_price_original !== null ? (
        <>
          <span className="text-[15px] font-semibold">{formatMoney(p.pack_price_original, p.currency_original)}</span>
          <div>
            <Badge tone="warn">Not converted</Badge>
          </div>
        </>
      ) : (
        <span className="text-muted">No price</span>
      )}
      {p.mrp !== null && <div className="text-xs text-muted">MRP {formatMoney(p.mrp, p.target_currency)}</div>}
    </div>
  )
}

function TotalCell({ o }: { o: Offer }) {
  const p = o.pricing
  if (p.estimated_known_total === null) return <span className="text-muted">—</span>
  return (
    <div className="text-right tabular-nums">
      <span className="font-medium">{formatMoney(p.estimated_known_total, p.target_currency)}</span>
      <div className="text-xs text-muted" title={p.exclusions.join('; ')}>
        {p.total_is_complete ? 'Known costs complete' : `Excludes: ${p.exclusions.length} item(s)`}
      </div>
    </div>
  )
}

export function OfferTable(props: Props) {
  const { offers, mode, quantity } = props
  const [open, setOpen] = useState<string | null>(null)
  const business = mode === 'business'
  const colSpan = business ? 10 : 9

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[1000px] border-collapse text-[13.5px]">
        <caption className="sr-only">Supplier offers, sorted by {props.sortKey}</caption>
        <thead className="border-b border-line bg-sunken/70 text-left text-[11px] uppercase tracking-wider text-muted">
          <tr>
            <SortHeader label="#" k="rank" props={props} />
            <SortHeader label="Supplier" k="supplier" props={props} />
            <th scope="col" className={TH}>
              Status
            </th>
            <th scope="col" className={TH}>
              Product / pack
            </th>
            <SortHeader label="Price / pack" k="price" props={props} align="right" />
            <SortHeader label="Unit price" k="unit_price" props={props} align="right" />
            <SortHeader
              label={`Cost for ${quantity} pack${quantity === 1 ? '' : 's'}`}
              k="requested_cost"
              props={props}
              align="right"
            />
            {business && (
              <th scope="col" className={cn(TH, 'text-right')}>
                MOQ (packs)
              </th>
            )}
            <th scope="col" className={TH}>
              Availability
            </th>
            <SortHeader label="Est. total" k="known_total" props={props} align="right" />
            <th scope="col" className={TH}>
              <span className="sr-only">Supplier link</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {offers.map((o) => {
            const expanded = open === o.offer_id
            const link = safeExternalUrl(o.product_url)
            const enquiry = safeExternalUrl(o.enquiry_url)
            const p = o.pricing
            return (
              <Fragment key={o.offer_id}>
                <tr
                  className={cn(
                    'border-t border-line align-top transition-colors hover:bg-brand-50/40',
                    !o.eligible && 'bg-sunken/40 text-ink-soft',
                  )}
                >
                  <td className="px-4 py-3.5 tabular-nums text-muted">{o.rank ?? '—'}</td>
                  <td className="px-4 py-3.5">
                    <button
                      onClick={() => setOpen(expanded ? null : o.offer_id)}
                      aria-expanded={expanded}
                      className="flex items-start gap-1 text-left font-semibold hover:text-brand-700"
                    >
                      {expanded ? (
                        <ChevronDown className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />
                      ) : (
                        <ChevronRight className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />
                      )}
                      <span>
                        {o.supplier_name}
                        <span className="block text-xs font-normal text-muted">
                          {o.supplier_country ?? 'Country unknown'}
                        </span>
                      </span>
                    </button>
                    {o.is_demo && (
                      <Badge tone="warn" className="ml-5 mt-1">
                        Demonstration data
                      </Badge>
                    )}
                  </td>
                  <td className="px-4 py-3.5">
                    <VerificationBadge status={o.tier} />
                    {!o.eligible && o.ineligible_reasons[0] && (
                      <p className="mt-1 max-w-[11rem] text-xs text-muted">Not ranked: {o.ineligible_reasons[0]}</p>
                    )}
                  </td>
                  <td className="max-w-[15rem] px-4 py-3.5">
                    <p className="line-clamp-2">{o.title || '—'}</p>
                    <p className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted">
                      {p.offer_pack_units ? `${p.offer_pack_units} per pack` : 'Pack size unknown'}
                      {p.comparability === 'pack_differs' && <Badge tone="info">Different pack size</Badge>}
                    </p>
                  </td>
                  <td className="px-4 py-3.5">
                    <PriceCell o={o} />
                  </td>
                  <td className="px-4 py-3.5 text-right tabular-nums">
                    {p.unit_price !== null ? (
                      formatMoney(p.unit_price, p.target_currency)
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3.5 text-right tabular-nums">
                    {p.requested_cost !== null ? (
                      <>
                        <span className="font-semibold">{formatMoney(p.requested_cost, p.target_currency)}</span>
                        {(p.moq_applied || p.price_break_applied) && (
                          <div className="text-xs text-muted">{p.moq_applied ? 'MOQ applied' : 'Quantity break'}</div>
                        )}
                      </>
                    ) : (
                      <span className="text-muted" title="Pack size or currency prevents a comparable cost">
                        Not comparable
                      </span>
                    )}
                  </td>
                  {business && (
                    <td className="px-4 py-3.5 text-right tabular-nums">
                      {p.moq_packs ?? <span className="text-muted">—</span>}
                    </td>
                  )}
                  <td className="px-4 py-3.5">
                    <Badge
                      tone={
                        o.availability === 'in_stock'
                          ? 'ok'
                          : o.availability === 'out_of_stock'
                            ? 'danger'
                            : o.availability === 'limited'
                              ? 'warn'
                              : 'neutral'
                      }
                    >
                      {AVAILABILITY_LABEL[o.availability]}
                    </Badge>
                    <p className="mt-1 text-xs text-muted">{o.delivery_estimate ?? 'Delivery not stated'}</p>
                  </td>
                  <td className="px-4 py-3.5">
                    <TotalCell o={o} />
                  </td>
                  <td className="px-4 py-3.5 text-xs">
                    <div className="flex flex-col items-start gap-1">
                      {link ? (
                        <a
                          href={link}
                          target="_blank"
                          rel="noopener noreferrer nofollow"
                          className="inline-flex items-center gap-1 whitespace-nowrap rounded-md border border-line-strong bg-surface px-2.5 py-1.5 text-[13px] font-medium text-brand-700 hover:bg-brand-50"
                        >
                          View at supplier <ExternalLink className="size-3" aria-hidden />
                        </a>
                      ) : (
                        <span className="text-muted">{o.is_demo ? 'No link (demo)' : 'No link available'}</span>
                      )}
                      {business && enquiry && (
                        <a
                          href={enquiry}
                          target="_blank"
                          rel="noopener noreferrer nofollow"
                          className="inline-flex items-center gap-1 whitespace-nowrap font-medium text-brand-700 hover:underline"
                        >
                          Request quote <ExternalLink className="size-3" aria-hidden />
                        </a>
                      )}
                      <span className="text-muted">
                        {o.is_demo ? 'Fictional fixture' : `Observed ${relativeAge(o.source_retrieved_at)}`}
                      </span>
                    </div>
                  </td>
                </tr>
                {expanded && (
                  <tr className="border-t border-line">
                    <td colSpan={colSpan} className="p-0">
                      <OfferDetail offer={o} mode={mode} />
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
