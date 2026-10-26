import { describe, expect, it } from 'vitest'
import { elapsedSeconds, phaseStates } from './activity'
import { formatMoney, relativeAge, safeExternalUrl } from './format'
import { confirmField, editField, normalizeForSubmit, USER_EVIDENCE } from './identity'
import { countByTier, DEFAULT_FILTERS, filterOffers, sortOffers } from './offers'
import { optionsFormSchema } from './schemas'
import { validateImageFile } from './upload'
import { makeIdentity, makeOffer, makeProgress } from '@/test/fixtures'

const file = (name: string, type: string, size = 100) => new File([new Uint8Array(size)], name, { type })

describe('validateImageFile', () => {
  it('accepts jpeg/png/webp', () => {
    for (const t of ['image/jpeg', 'image/png', 'image/webp']) expect(validateImageFile(file('a', t))).toBeNull()
  })
  it('rejects other types, empty and oversize files', () => {
    expect(validateImageFile(file('a.gif', 'image/gif'))).toMatch(/Unsupported/)
    expect(validateImageFile(file('a.pdf', 'application/pdf'))).toMatch(/Unsupported/)
    expect(validateImageFile(file('a.png', 'image/png', 0))).toMatch(/empty/)
    expect(validateImageFile(file('a.png', 'image/png', 3 * 1024 * 1024), undefined, 2)).toMatch(/larger than 2 MB/)
  })
})

describe('safeExternalUrl', () => {
  it('only allows http(s) and never demo .invalid hosts', () => {
    expect(safeExternalUrl('https://shop.example/p?x=1')).toBe('https://shop.example/p?x=1')
    expect(safeExternalUrl('javascript:alert(1)')).toBeNull()
    expect(safeExternalUrl('data:text/html,hi')).toBeNull()
    expect(safeExternalUrl('not a url')).toBeNull()
    expect(safeExternalUrl('https://alpha.demo.invalid/x')).toBeNull()
    expect(safeExternalUrl(null)).toBeNull()
  })
})

describe('format', () => {
  it('formats money and missing values', () => {
    expect(formatMoney(24, 'INR')).toContain('24.00')
    expect(formatMoney(null, 'INR')).toBe('—')
    expect(formatMoney(5, 'not-a-code')).toContain('5.00')
  })
  it('describes age', () => {
    const now = new Date('2026-10-24T12:00:00Z')
    expect(relativeAge('2026-10-24T11:30:00Z', now)).toBe('30 min ago')
    expect(relativeAge('2026-10-24T08:00:00Z', now)).toBe('4 h ago')
    expect(relativeAge(null, now)).toBe('unknown')
  })
})

describe('identity editing', () => {
  it('marks user edits confirmed and clearing as unknown', () => {
    const id = editField(makeIdentity(), 'strength', '650 mg')
    expect(id.strength).toEqual({ value: '650 mg', status: 'confirmed', evidence: USER_EVIDENCE })
    expect(editField(id, 'strength', '  ').strength.status).toBe('unknown')
  })
  it('confirm only upgrades inferred values that exist', () => {
    const base = makeIdentity({ strength: { value: '500 mg', status: 'inferred', evidence: 'guess' } })
    expect(confirmField(base, 'strength').strength.status).toBe('confirmed')
    expect(confirmField(base, 'route').route.status).toBe('unknown')
  })
  it('normalizeForSubmit trims and drops blank values', () => {
    const id = makeIdentity({ route: { value: '   ', status: 'confirmed', evidence: null } })
    expect(normalizeForSubmit(id).route).toEqual({ value: null, status: 'unknown', evidence: null })
  })
})

describe('offer view logic', () => {
  const a = makeOffer({ supplier_name: 'A', rank: 2, pricing: { requested_cost: 30, unit_price: 3 } })
  const b = makeOffer({ supplier_name: 'B', rank: 1, pricing: { requested_cost: 20, unit_price: 2 } })
  const c = makeOffer({
    supplier_name: 'C',
    rank: null,
    eligible: false,
    pricing: { requested_cost: null, unit_price: null },
  })
  const d = makeOffer({
    supplier_name: 'D',
    tier: 'UNVERIFIED',
    availability: 'out_of_stock',
    supplier_country: 'Germany',
    rank: 3,
    pricing: { requested_cost: 10, unit_price: 1 },
  })

  it('sorts by rank, with non-comparable offers last in either direction', () => {
    expect(sortOffers([a, c, b], 'rank', 'asc').map((o) => o.supplier_name)).toEqual(['B', 'A', 'C'])
    expect(sortOffers([a, c, b], 'requested_cost', 'asc').map((o) => o.supplier_name)).toEqual(['B', 'A', 'C'])
    expect(sortOffers([a, c, b], 'requested_cost', 'desc').map((o) => o.supplier_name)).toEqual(['A', 'B', 'C'])
    expect(sortOffers([b, a], 'supplier', 'desc').map((o) => o.supplier_name)).toEqual(['B', 'A'])
  })

  it('filters by text, availability, country and stock', () => {
    const all = [a, b, d]
    expect(filterOffers(all, { ...DEFAULT_FILTERS, text: 'd' }).map((o) => o.supplier_name)).toContain('D')
    expect(filterOffers(all, { ...DEFAULT_FILTERS, availability: 'out_of_stock' })).toEqual([d])
    expect(filterOffers(all, { ...DEFAULT_FILTERS, country: 'Germany' })).toEqual([d])
    expect(filterOffers(all, { ...DEFAULT_FILTERS, availability: 'in_stock' })).toEqual([a, b])
  })

  it('filters by price per pack, excluding offers whose price cannot be compared', () => {
    const cheap = makeOffer({ supplier_name: 'P1', pricing: { pack_price: 10 } })
    const mid = makeOffer({ supplier_name: 'P2', pricing: { pack_price: 20 } })
    const unconverted = makeOffer({ supplier_name: 'P3', pricing: { pack_price: null, pack_price_original: 5 } })
    const all = [cheap, mid, unconverted]
    expect(filterOffers(all, { ...DEFAULT_FILTERS, minPrice: '15' }).map((o) => o.supplier_name)).toEqual(['P2'])
    expect(filterOffers(all, { ...DEFAULT_FILTERS, maxPrice: '15' }).map((o) => o.supplier_name)).toEqual(['P1'])
    expect(filterOffers(all, { ...DEFAULT_FILTERS, minPrice: '5', maxPrice: '25' })).toHaveLength(2)
    expect(filterOffers(all, DEFAULT_FILTERS)).toHaveLength(3)
    expect(filterOffers(all, { ...DEFAULT_FILTERS, minPrice: 'abc' })).toHaveLength(3)
  })

  it('shows every status in one list but keeps rejected offers hidden unless asked for', () => {
    const rejected = makeOffer({ supplier_name: 'R', tier: 'REJECTED', eligible: false, rank: null })
    const partial = makeOffer({ supplier_name: 'PV', tier: 'PARTIALLY_VERIFIED' })
    const all = [a, d, partial, rejected]
    expect(filterOffers(all, DEFAULT_FILTERS).map((o) => o.supplier_name)).toEqual(['A', 'D', 'PV'])
    expect(filterOffers(all, { ...DEFAULT_FILTERS, status: 'REJECTED' })).toEqual([rejected])
    expect(filterOffers(all, { ...DEFAULT_FILTERS, status: 'UNVERIFIED' })).toEqual([d])
  })

  it('counts offers per verification status', () => {
    expect(countByTier([a, d])).toEqual({ VERIFIED: 1, PARTIALLY_VERIFIED: 0, UNVERIFIED: 1, REJECTED: 0 })
  })
})

describe('optionsFormSchema', () => {
  const ok = { provider: 'openai', mode: 'retail', market: 'india', quantity: '1', minPrice: '', maxPrice: '' }
  it('accepts defaults and optional prices', () => {
    expect(optionsFormSchema.safeParse(ok).success).toBe(true)
    expect(optionsFormSchema.safeParse({ ...ok, minPrice: '10.50', maxPrice: '20' }).success).toBe(true)
  })
  it('rejects bad quantity, prices, provider and inverted ranges', () => {
    expect(optionsFormSchema.safeParse({ ...ok, quantity: '0' }).success).toBe(false)
    expect(optionsFormSchema.safeParse({ ...ok, quantity: '1.5' }).success).toBe(false)
    expect(optionsFormSchema.safeParse({ ...ok, minPrice: '-1' }).success).toBe(false)
    expect(optionsFormSchema.safeParse({ ...ok, provider: 'claude' }).success).toBe(false)
    const inverted = optionsFormSchema.safeParse({ ...ok, minPrice: '30', maxPrice: '20' })
    expect(inverted.success).toBe(false)
  })
})

describe('activity stages (derived only from recorded events)', () => {
  const ev = (phase: 'plan' | 'search' | 'read' | 'verify' | 'rank' | 'done', sec: number) => ({
    at: new Date(Date.UTC(2026, 9, 24, 12, 0, sec)).toISOString(),
    phase,
    level: 'info' as const,
    message: phase,
  })

  it('marks the current stage active and later ones pending while running', () => {
    const p = makeProgress({ finished: false, activity: [ev('plan', 0), ev('search', 1)] })
    expect(phaseStates(p)).toEqual({
      plan: 'done',
      search: 'active',
      read: 'pending',
      verify: 'pending',
      rank: 'pending',
    })
  })

  it('starts at plan before any event exists', () => {
    expect(phaseStates(makeProgress({ finished: false, activity: [] })).plan).toBe('active')
  })

  it('marks stages that never ran as skipped once finished', () => {
    const p = makeProgress({
      finished: true,
      activity: [ev('plan', 0), ev('search', 1), ev('verify', 2), ev('rank', 3), ev('done', 4)],
    })
    expect(phaseStates(p)).toEqual({ plan: 'done', search: 'done', read: 'skipped', verify: 'done', rank: 'done' })
  })

  it('measures elapsed time from the first to the last event', () => {
    expect(elapsedSeconds(makeProgress({ activity: [ev('plan', 0), ev('done', 7)] }))).toBe(7)
    expect(elapsedSeconds(makeProgress({ activity: [ev('plan', 0)] }))).toBeNull()
  })
})
