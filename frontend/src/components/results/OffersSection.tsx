import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/feedback'
import { Input, Select } from '@/components/ui/form'
import { VERIFICATION_HELP, VERIFICATION_LABEL } from '@/lib/format'
import {
  countByTier,
  countries,
  DEFAULT_FILTERS,
  filterOffers,
  sortOffers,
  TIERS,
  type OfferFilters,
  type SortDir,
  type SortKey,
  type StatusFilter,
} from '@/lib/offers'
import type { Availability, Offer, SearchOptions } from '@/lib/types'
import { OfferTable } from './OfferTable'
import { VerificationBadge } from './VerificationBadge'

interface Props {
  offers: Offer[]
  options: SearchOptions
  finished: boolean
  initialPrice?: { min: string; max: string }
}

/** One list for every offer: the verification tag on each row says how far it can be trusted. */
export function OffersSection({ offers, options, finished, initialPrice }: Props) {
  const [filters, setFilters] = useState<OfferFilters>({
    ...DEFAULT_FILTERS,
    minPrice: initialPrice?.min ?? '',
    maxPrice: initialPrice?.max ?? '',
  })
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir }>({ key: 'rank', dir: 'asc' })

  const counts = useMemo(() => countByTier(offers), [offers])
  const listed = offers.length - counts.REJECTED
  const comparable = offers.filter((o) => o.tier !== 'REJECTED' && o.pricing.pack_price_original !== null).length
  const visible = useMemo(() => sortOffers(filterOffers(offers, filters), sort.key, sort.dir), [offers, filters, sort])
  const filtersActive = JSON.stringify(filters) !== JSON.stringify(DEFAULT_FILTERS)
  const multiCountry = countries(offers).length > 1

  function onSort(key: SortKey) {
    setSort((s) => (s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'asc' }))
  }

  return (
    <section
      aria-label="Supplier offers"
      className="overflow-hidden rounded-xl border border-line bg-surface shadow-[0_1px_2px_rgba(14,35,48,0.05)]"
    >
      <header className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div>
          <h2 className="text-[15px] font-semibold">Offers</h2>
          <p className="text-sm text-ink-soft">
            {listed} listing{listed === 1 ? '' : 's'}, {comparable} with a price, ranked by cost for {options.quantity}{' '}
            pack{options.quantity === 1 ? '' : 's'}
          </p>
        </div>
        <ul className="flex flex-wrap items-center gap-2 text-xs text-ink-soft" aria-label="Offers by status">
          {TIERS.filter((t) => t !== 'REJECTED' && counts[t] > 0).map((t) => (
            <li key={t} className="flex items-center gap-1.5">
              <VerificationBadge status={t} />
              <span className="font-semibold tabular-nums text-ink">{counts[t]}</span>
            </li>
          ))}
        </ul>
      </header>

      <div
        className={`grid gap-3 border-y border-line bg-sunken/50 px-5 py-3 sm:grid-cols-2 ${
          multiCountry
            ? 'lg:grid-cols-[minmax(0,1fr)_10rem_10rem_10rem_7rem_7rem]'
            : 'lg:grid-cols-[minmax(0,1fr)_11rem_11rem_8rem_8rem]'
        }`}
      >
        <Input
          aria-label="Search suppliers or products"
          placeholder="Search supplier or product"
          value={filters.text}
          onChange={(e) => setFilters({ ...filters, text: e.target.value })}
        />
        <Select
          aria-label="Status"
          value={filters.status}
          onChange={(e) => setFilters({ ...filters, status: e.target.value as StatusFilter })}
        >
          <option value="ALL">All statuses</option>
          {TIERS.map((t) => (
            <option key={t} value={t}>
              {VERIFICATION_LABEL[t]} ({counts[t]})
            </option>
          ))}
        </Select>
        <Select
          aria-label="Availability"
          value={filters.availability}
          onChange={(e) => setFilters({ ...filters, availability: e.target.value as Availability | 'any' })}
        >
          <option value="any">Any availability</option>
          <option value="in_stock">In stock</option>
          <option value="limited">Limited</option>
          <option value="out_of_stock">Out of stock</option>
          <option value="unknown">Unknown</option>
        </Select>
        {multiCountry && (
          <Select
            aria-label="Supplier country"
            value={filters.country}
            onChange={(e) => setFilters({ ...filters, country: e.target.value })}
          >
            <option value="any">Any country</option>
            {countries(offers).map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
        )}
        <Input
          aria-label="Minimum price per pack"
          placeholder="Min price"
          inputMode="decimal"
          value={filters.minPrice}
          onChange={(e) => setFilters({ ...filters, minPrice: e.target.value })}
        />
        <Input
          aria-label="Maximum price per pack"
          placeholder="Max price"
          inputMode="decimal"
          value={filters.maxPrice}
          onChange={(e) => setFilters({ ...filters, maxPrice: e.target.value })}
        />
      </div>

      {offers.length === 0 ? (
        <div className="p-5">
          <EmptyState title={finished ? 'No offers found' : 'Nothing here yet'}>
            {finished
              ? 'No supplier offer matched this product.'
              : 'Offers appear here as sources respond, each tagged with how far it could be verified.'}
          </EmptyState>
        </div>
      ) : visible.length === 0 ? (
        <div className="p-5">
          <EmptyState
            title="No offers match the filters"
            action={
              <Button variant="secondary" size="sm" onClick={() => setFilters(DEFAULT_FILTERS)}>
                Clear filters
              </Button>
            }
          >
            {filters.status === 'ALL' && counts.REJECTED > 0
              ? `${counts.REJECTED} offer(s) that did not match the product are hidden; choose "Rejected" in Status to audit them.`
              : undefined}
          </EmptyState>
        </div>
      ) : (
        <OfferTable
          offers={visible}
          mode={options.mode}
          sortKey={sort.key}
          sortDir={sort.dir}
          onSort={onSort}
          quantity={options.quantity}
        />
      )}

      {counts.REJECTED > 0 && filters.status === 'ALL' && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line px-5 py-2.5 text-sm">
          <span className="text-ink-soft">
            {counts.REJECTED} listing{counts.REJECTED === 1 ? '' : 's'} hidden: not the same product (different
            strength, form, brand or details).
          </span>
          <button
            onClick={() => setFilters({ ...filters, status: 'REJECTED' })}
            className="font-medium text-brand-700 hover:underline"
          >
            Show them
          </button>
        </div>
      )}

      <footer className="border-t border-line bg-sunken/50 px-5 py-3 text-xs text-muted">
        <ul className="grid gap-x-6 gap-y-1 sm:grid-cols-3">
          {TIERS.filter((t) => t !== 'REJECTED').map((t) => (
            <li key={t}>
              <span className="font-semibold text-ink-soft">{VERIFICATION_LABEL[t]}:</span> {VERIFICATION_HELP[t]}
            </li>
          ))}
        </ul>
        <p className="mt-2">
          Ranked by supplier price for the requested quantity (before shipping and tax), lowest first. Offers that
          cannot be compared are listed last.
          {filtersActive && ' Filters are active.'}
        </p>
      </footer>
    </section>
  )
}
