import type { Availability, Offer, VerificationStatus, WorkflowState } from './types'

export function formatMoney(value: number | null | undefined, currency: string | null | undefined): string {
  if (value === null || value === undefined) return '—'
  const code = currency && /^[A-Z]{3}$/.test(currency) ? currency : undefined
  try {
    return new Intl.NumberFormat('en-IN', {
      style: code ? 'currency' : 'decimal',
      currency: code,
      maximumFractionDigits: 2,
      minimumFractionDigits: 2,
    }).format(value)
  } catch {
    return `${value.toFixed(2)} ${currency ?? ''}`.trim()
  }
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(d)
}

export function relativeAge(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return 'unknown'
  const diff = now.getTime() - new Date(iso).getTime()
  if (Number.isNaN(diff)) return 'unknown'
  const mins = Math.max(0, Math.round(diff / 60000))
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hours = Math.round(mins / 60)
  if (hours < 48) return `${hours} h ago`
  return `${Math.round(hours / 24)} d ago`
}

/** Only http(s) URLs may be rendered as outbound links. */
export function safeExternalUrl(url: string | null | undefined): string | null {
  if (!url) return null
  try {
    const u = new URL(url)
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return null
    if (u.hostname.endsWith('.invalid')) return null // reserved TLD: demonstration fixtures only
    return u.toString()
  } catch {
    return null
  }
}

export const VERIFICATION_LABEL: Record<VerificationStatus, string> = {
  VERIFIED: 'Source-verified',
  PARTIALLY_VERIFIED: 'Partially verified',
  UNVERIFIED: 'Unverified',
  REJECTED: 'Rejected',
}

export const VERIFICATION_HELP: Record<VerificationStatus, string> = {
  VERIFIED:
    'Direct source evidence supports the price and every required attribute matches. This does not guarantee the supplier or transaction is safe.',
  PARTIALLY_VERIFIED:
    'Direct evidence supports the price, but some attributes are not stated, the evidence is stale, or details differ.',
  UNVERIFIED:
    'No direct evidence of the price, conflicting evidence, or demonstration data. Treat the price as a lead only.',
  REJECTED: 'Does not match the identified product, or the data is invalid. Kept for audit only.',
}

export const AVAILABILITY_LABEL: Record<Availability, string> = {
  in_stock: 'In stock',
  out_of_stock: 'Out of stock',
  limited: 'Limited stock',
  unknown: 'Unknown',
}

export const STATE_LABEL: Record<WorkflowState, string> = {
  REQUEST_RECEIVED: 'Request received',
  IDENTIFYING_PRODUCT: 'Identifying product',
  IDENTITY_READY: 'Identity ready',
  NEEDS_CLARIFICATION: 'Needs clarification',
  SEARCHING_SUPPLIERS: 'Searching suppliers',
  VERIFYING_OFFERS: 'Verifying offers',
  PARTIAL_RESULTS: 'Partial results',
  RESULTS_READY: 'Results ready',
  NO_MATCHES: 'No matches',
  SOURCE_UNAVAILABLE: 'Sources unavailable',
  FAILED: 'Failed',
}

export function offerSourceLabel(o: Offer): string {
  if (o.is_demo) return 'Demonstration data'
  return o.supplier_domain ?? o.connector_id
}
