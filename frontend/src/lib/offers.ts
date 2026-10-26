// Pure view logic for the comparison table. Pricing and verification are computed by the backend;
// this module only filters and orders what the server already decided.
import type { Availability, Offer, VerificationStatus } from './types'

export type SortKey = 'rank' | 'supplier' | 'unit_price' | 'requested_cost' | 'known_total' | 'price' | 'observed'
export type SortDir = 'asc' | 'desc'

/** 'ALL' shows every offer except rejected ones, which stay hidden unless asked for. */
export type StatusFilter = VerificationStatus | 'ALL'

export interface OfferFilters {
  text: string
  status: StatusFilter
  availability: Availability | 'any'
  country: string | 'any'
  minPrice: string // per-pack price in the results currency; '' = no limit
  maxPrice: string
}

export const DEFAULT_FILTERS: OfferFilters = {
  text: '',
  status: 'ALL',
  availability: 'any',
  country: 'any',
  minPrice: '',
  maxPrice: '',
}

export const TIERS: VerificationStatus[] = ['VERIFIED', 'PARTIALLY_VERIFIED', 'UNVERIFIED', 'REJECTED']

export function countByTier(offers: Offer[]): Record<VerificationStatus, number> {
  const out: Record<VerificationStatus, number> = { VERIFIED: 0, PARTIALLY_VERIFIED: 0, UNVERIFIED: 0, REJECTED: 0 }
  for (const o of offers) out[o.tier] += 1
  return out
}

export function filterOffers(offers: Offer[], f: OfferFilters): Offer[] {
  const text = f.text.trim().toLowerCase()
  const min = f.minPrice.trim() === '' ? null : Number(f.minPrice)
  const max = f.maxPrice.trim() === '' ? null : Number(f.maxPrice)
  const hasMin = min !== null && !Number.isNaN(min)
  const hasMax = max !== null && !Number.isNaN(max)
  return offers.filter((o) => {
    if (f.status === 'ALL' ? o.tier === 'REJECTED' : o.tier !== f.status) return false
    if (text && !`${o.supplier_name} ${o.title}`.toLowerCase().includes(text)) return false
    if (f.availability !== 'any' && o.availability !== f.availability) return false
    if (f.country !== 'any' && (o.supplier_country ?? 'Unknown') !== f.country) return false
    if (hasMin || hasMax) {
      const price = o.pricing.pack_price // converted price; unconverted offers cannot be compared
      if (price === null) return false
      if (hasMin && price < (min as number)) return false
      if (hasMax && price > (max as number)) return false
    }
    return true
  })
}

function sortValue(o: Offer, key: SortKey): number | string | null {
  switch (key) {
    case 'rank':
      return o.rank
    case 'supplier':
      return o.supplier_name.toLowerCase()
    case 'unit_price':
      return o.pricing.unit_price
    case 'requested_cost':
      return o.pricing.requested_cost
    case 'known_total':
      return o.pricing.estimated_known_total
    case 'price':
      return o.pricing.pack_price
    case 'observed':
      return o.source_retrieved_at ? new Date(o.source_retrieved_at).getTime() : null
  }
}

/** Eligible (rankable) offers always precede non-comparable ones; missing values sort last. */
export function sortOffers(offers: Offer[], key: SortKey, dir: SortDir): Offer[] {
  const sign = dir === 'asc' ? 1 : -1
  return [...offers].sort((a, b) => {
    if (a.eligible !== b.eligible) return a.eligible ? -1 : 1
    const av = sortValue(a, key)
    const bv = sortValue(b, key)
    if (av === null && bv === null) return a.supplier_name.localeCompare(b.supplier_name)
    if (av === null) return 1
    if (bv === null) return -1
    if (av < bv) return -1 * sign
    if (av > bv) return 1 * sign
    return a.supplier_name.localeCompare(b.supplier_name)
  })
}

export function countries(offers: Offer[]): string[] {
  return [...new Set(offers.map((o) => o.supplier_country ?? 'Unknown'))].sort()
}
