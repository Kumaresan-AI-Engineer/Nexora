import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { OffersSection } from './OffersSection'
import { makeOffer, OPTIONS } from '@/test/fixtures'
import type { Offer } from '@/lib/types'

const cheap = makeOffer({
  offer_id: 'o1',
  supplier_name: 'Cheap Chemist',
  rank: 1,
  pricing: { requested_cost: 20, pack_price: 20, unit_price: 2 },
})
const dear = makeOffer({
  offer_id: 'o2',
  supplier_name: 'Dear Dispensary',
  rank: 2,
  availability: 'out_of_stock',
  supplier_country: 'Germany',
  pricing: { requested_cost: 30, pack_price: 30, unit_price: 3 },
})
const partial = makeOffer({ offer_id: 'o3', supplier_name: 'Partial Pharma', tier: 'PARTIALLY_VERIFIED', rank: 3 })
const unverified = makeOffer({
  offer_id: 'o4',
  supplier_name: 'Snippet Store',
  tier: 'UNVERIFIED',
  rank: 4,
  product_url: 'https://snippet.example/x',
})
const rejected = makeOffer({
  offer_id: 'o5',
  supplier_name: 'Wrong Strength Ltd',
  tier: 'REJECTED',
  eligible: false,
  rank: null,
  ineligible_reasons: ['Rejected: does not match'],
})

function setup(offers: Offer[], finished = true, options = OPTIONS) {
  return render(<OffersSection offers={offers} options={options} finished={finished} />)
}

const rowNames = () =>
  screen
    .getAllByRole('row')
    .slice(1)
    .map((r) => within(r).getAllByRole('button')[0]?.textContent ?? '')

describe('OffersSection', () => {
  it('lists every status together in one table, each row tagged', () => {
    setup([cheap, dear, partial, unverified])
    const table = screen.getByRole('table')
    for (const name of ['Cheap Chemist', 'Partial Pharma', 'Snippet Store']) {
      expect(within(table).getByText(name)).toBeInTheDocument()
    }
    expect(within(table).getAllByText('Source-verified')).toHaveLength(2)
    expect(within(table).getByText('Partially verified')).toBeInTheDocument()
    expect(within(table).getByText('Unverified')).toBeInTheDocument()
    expect(screen.queryByRole('tab')).not.toBeInTheDocument()
  })

  it('summarises counts per status in the header', () => {
    setup([cheap, dear, partial, unverified, rejected])
    const summary = screen.getByRole('list', { name: 'Offers by status' })
    expect(within(summary).getByText('Source-verified').closest('li')).toHaveTextContent('2')
    expect(within(summary).getByText('Partially verified').closest('li')).toHaveTextContent('1')
    expect(screen.getByText(/4 listings, 4 with a price/)).toBeInTheDocument()
  })

  it('keeps rejected offers out of the list until asked for in the status filter', async () => {
    setup([cheap, rejected])
    expect(screen.queryByText('Wrong Strength Ltd')).not.toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Status'), 'REJECTED')
    expect(screen.getByText('Wrong Strength Ltd')).toBeInTheDocument()
    expect(screen.queryByText('Cheap Chemist')).not.toBeInTheDocument()
  })

  it('filters by status', async () => {
    setup([cheap, partial, unverified])
    await userEvent.selectOptions(screen.getByLabelText('Status'), 'UNVERIFIED')
    expect(screen.getByText('Snippet Store')).toBeInTheDocument()
    expect(screen.queryByText('Cheap Chemist')).not.toBeInTheDocument()
    expect(screen.queryByText('Partial Pharma')).not.toBeInTheDocument()
  })

  it('explains what each tag means', () => {
    setup([cheap])
    expect(
      screen.getByText(/Direct source evidence supports the price and every required attribute/),
    ).toBeInTheDocument()
    expect(screen.getByText(/does not guarantee the supplier/)).toBeInTheDocument()
  })

  it('sorts by cost when the header is clicked and toggles direction', async () => {
    setup([dear, cheap])
    expect(rowNames()[0]).toContain('Cheap Chemist')
    await userEvent.click(screen.getByRole('button', { name: /Cost for 1 pack/ }))
    expect(rowNames()[0]).toContain('Cheap Chemist')
    await userEvent.click(screen.getByRole('button', { name: /Cost for 1 pack/ }))
    expect(rowNames()[0]).toContain('Dear Dispensary')
    expect(screen.getByRole('columnheader', { name: /Cost for 1 pack/ })).toHaveAttribute('aria-sort', 'descending')
  })

  it('filters by supplier text, availability and country', async () => {
    setup([cheap, dear])
    await userEvent.type(screen.getByLabelText('Search suppliers or products'), 'dear')
    expect(screen.queryByText('Cheap Chemist')).not.toBeInTheDocument()
    expect(screen.getByText('Dear Dispensary')).toBeInTheDocument()
    await userEvent.clear(screen.getByLabelText('Search suppliers or products'))
    await userEvent.selectOptions(screen.getByLabelText('Availability'), 'out_of_stock')
    expect(screen.queryByText('Cheap Chemist')).not.toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Availability'), 'any')
    await userEvent.selectOptions(screen.getByLabelText('Supplier country'), 'Germany')
    expect(screen.queryByText('Cheap Chemist')).not.toBeInTheDocument()
    expect(screen.getByText('Dear Dispensary')).toBeInTheDocument()
  })

  it('only offers a country filter when suppliers span several countries', () => {
    setup([cheap])
    expect(screen.queryByLabelText('Supplier country')).not.toBeInTheDocument()
  })

  it('shows an empty state with a way to clear filters', async () => {
    setup([cheap])
    await userEvent.type(screen.getByLabelText('Search suppliers or products'), 'zzz')
    expect(screen.getByText('No offers match the filters')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(screen.getByText('Cheap Chemist')).toBeInTheDocument()
  })

  it('explains when nothing was found, and waits while a search is running', () => {
    const { unmount } = setup([], true)
    expect(screen.getByText('No offers found')).toBeInTheDocument()
    unmount()
    setup([], false)
    expect(screen.getByText('Nothing here yet')).toBeInTheDocument()
  })

  it('renders supplier links safely and omits links that are not http(s)', () => {
    const bad = makeOffer({ offer_id: 'bad', supplier_name: 'Bad Link', product_url: 'javascript:alert(1)' })
    setup([cheap, bad])
    const link = screen.getByRole('link', { name: /View at supplier/ })
    expect(link).toHaveAttribute('href', 'https://acme.example/p')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link.getAttribute('rel')).toContain('noopener')
    expect(screen.getAllByRole('link')).toHaveLength(1)
    expect(screen.getByText('No link available')).toBeInTheDocument()
  })

  it('marks demonstration rows and never links them', () => {
    const demo = makeOffer({
      offer_id: 'd',
      is_demo: true,
      tier: 'UNVERIFIED',
      supplier_name: 'DEMO Pharmacy (fictional)',
      product_url: 'https://alpha.demo.invalid/x',
    })
    setup([demo])
    expect(screen.getByText('Demonstration data', { selector: 'span' })).toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.getByText('No link (demo)')).toBeInTheDocument()
  })

  it('shows unconverted currency and non-comparable cost explicitly', () => {
    const odd = makeOffer({
      offer_id: 'x',
      supplier_name: 'Overseas',
      eligible: false,
      rank: null,
      ineligible_reasons: ['Price in USD could not be converted'],
      pricing: {
        currency_original: 'USD',
        pack_price: null,
        pack_price_original: 1.5,
        requested_cost: null,
        unit_price: null,
        estimated_known_total: null,
      },
    })
    setup([odd])
    expect(screen.getByText('Not converted')).toBeInTheDocument()
    expect(screen.getByText('Not comparable')).toBeInTheDocument()
    expect(screen.getByText(/Not ranked: Price in USD/)).toBeInTheDocument()
  })

  it('separates MRP from the selling price and never calls an incomplete total final', () => {
    setup([makeOffer({ pricing: { mrp: 30, pack_price: 24 } })])
    expect(screen.getByText(/MRP/)).toBeInTheDocument()
    expect(screen.getByText(/Excludes: 2 item\(s\)/)).toBeInTheDocument()
    expect(screen.queryByText(/payable/i)).not.toBeInTheDocument()
  })

  it('business mode shows MOQ and quote links; retail does not', () => {
    const o = makeOffer({ enquiry_url: 'https://acme.example/enquiry', pricing: { moq_packs: 5 } })
    const { unmount } = setup([o], true, { ...OPTIONS, mode: 'business' })
    expect(screen.getByRole('columnheader', { name: 'MOQ (packs)' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Request quote/ })).toBeInTheDocument()
    unmount()
    setup([o], true, { ...OPTIONS, mode: 'retail' })
    expect(screen.queryByRole('columnheader', { name: /MOQ/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Request quote/ })).not.toBeInTheDocument()
  })

  it('expands a row to show evidence and the cost breakdown', async () => {
    setup([cheap])
    await userEvent.click(screen.getByRole('button', { name: /Cheap Chemist/ }))
    expect(screen.getByText('Source evidence')).toBeInTheDocument()
    expect(screen.getByText('Supplier API response (direct)')).toBeInTheDocument()
    expect(screen.getByText('Final payable (stated by source)')).toBeInTheDocument()
    expect(screen.getAllByText('Not stated').length).toBeGreaterThan(0)
    expect(screen.getByText('Supplier legitimacy')).toBeInTheDocument()
  })

  it('applies the price range chosen before the search and lets the user change it', async () => {
    render(<OffersSection offers={[cheap, dear]} options={OPTIONS} finished initialPrice={{ min: '25', max: '' }} />)
    expect(screen.queryByText('Cheap Chemist')).not.toBeInTheDocument()
    expect(screen.getByText('Dear Dispensary')).toBeInTheDocument()
    expect(screen.getByLabelText('Minimum price per pack')).toHaveValue('25')
    await userEvent.clear(screen.getByLabelText('Minimum price per pack'))
    expect(screen.getByText('Cheap Chemist')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Maximum price per pack'), '25')
    expect(screen.queryByText('Dear Dispensary')).not.toBeInTheDocument()
  })

  it('"All statuses" really shows every non-rejected offer, priced ones first, so the table matches the header counts', () => {
    const noPrice = (n: number) =>
      makeOffer({
        offer_id: `np${n}`,
        supplier_name: `Lead ${n}`,
        tier: 'UNVERIFIED',
        eligible: false,
        rank: null,
        pricing: { pack_price: null, pack_price_original: null, requested_cost: null, unit_price: null },
      })
    setup([noPrice(1), partial, noPrice(2), noPrice(3), rejected])
    const names = rowNames()
    expect(names).toHaveLength(4) // 1 priced + 3 priceless leads; the rejected offer stays out
    expect(names[0]).toContain('Partial Pharma')
    expect(names.slice(1).join(' ')).toMatch(/Lead 1.*Lead 2.*Lead 3|Lead \d/)
    const summary = screen.getByRole('list', { name: 'Offers by status' })
    expect(within(summary).getByText('Partially verified').closest('li')).toHaveTextContent('1')
    expect(within(summary).getByText('Unverified').closest('li')).toHaveTextContent('3')
    expect(screen.queryByText('Wrong Strength Ltd')).not.toBeInTheDocument()
  })

  it('every status option shows exactly as many rows as its count says', async () => {
    const lead = makeOffer({
      offer_id: 'l',
      supplier_name: 'Lead Only',
      tier: 'UNVERIFIED',
      eligible: false,
      rank: null,
      pricing: { pack_price: null, pack_price_original: null, requested_cost: null },
    })
    setup([cheap, partial, unverified, lead, rejected])
    const status = screen.getByLabelText('Status')
    const expected: Record<string, number> = {
      ALL: 4,
      VERIFIED: 1,
      PARTIALLY_VERIFIED: 1,
      UNVERIFIED: 2,
      REJECTED: 1,
    }
    for (const [value, count] of Object.entries(expected)) {
      await userEvent.selectOptions(status, value)
      expect(screen.getAllByRole('row').length - 1, value).toBe(count)
    }
  })

  it('tells the user how many non-matching listings are hidden and lets them show them', async () => {
    setup([cheap, rejected])
    expect(screen.getByText(/1 listing hidden: not the same product/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Show them' }))
    expect(screen.getByText('Wrong Strength Ltd')).toBeInTheDocument()
    expect(screen.queryByText(/listing hidden/)).not.toBeInTheDocument()
  })
})
