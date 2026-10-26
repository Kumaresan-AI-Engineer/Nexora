// Synthetic test fixtures. Not market data.
import { emptyIdentity } from '@/lib/identity'
import type { Offer, Pricing, Progress, ProductIdentity, SearchDetail, SearchOptions } from '@/lib/types'

export const OPTIONS: SearchOptions = {
  provider: 'openai',
  mode: 'retail',
  market: 'india',
  quantity: 1,
  min_price: null,
  max_price: null,
}

export function makeIdentity(over: Partial<ProductIdentity> = {}): ProductIdentity {
  const id = emptyIdentity('medicine')
  id.generic_name = { value: 'Paracetamol', status: 'confirmed', evidence: 'label' }
  id.active_ingredients = { value: 'Paracetamol', status: 'confirmed', evidence: 'label' }
  id.strength = { value: '500 mg', status: 'confirmed', evidence: 'label' }
  id.dosage_form = { value: 'Tablet', status: 'confirmed', evidence: 'label' }
  id.pack_quantity = { value: '10', status: 'confirmed', evidence: 'label' }
  return { ...id, ...over }
}

export function makePricing(over: Partial<Pricing> = {}): Pricing {
  return {
    currency_original: 'INR',
    target_currency: 'INR',
    pack_price_original: 24,
    pack_price: 24,
    mrp_original: null,
    mrp: null,
    fx_rate: 1,
    fx_observed_at: null,
    fx_source: 'same currency',
    comparability: 'same_pack',
    offer_pack_units: 10,
    unit_price: 2.4,
    requested_units: 10,
    packs_needed: 1,
    requested_cost: 24,
    moq_packs: null,
    moq_applied: false,
    price_break_applied: false,
    shipping_cost: null,
    shipping_status: 'unknown',
    tax_status: 'unknown',
    tax_amount: null,
    estimated_known_total: 24,
    total_is_complete: false,
    final_payable: null,
    exclusions: ['Shipping/delivery charge not stated by the source', 'Tax treatment not stated by the source'],
    notes: [],
    ...over,
  }
}

export function makeOffer(over: Omit<Partial<Offer>, 'pricing'> & { pricing?: Partial<Pricing> } = {}): Offer {
  const { pricing, ...rest } = over
  return {
    offer_id: rest.offer_id ?? `offer-${Math.random().toString(36).slice(2)}`,
    supplier_name: 'Acme Pharmacy',
    supplier_country: 'India',
    supplier_domain: 'acme.example',
    connector_id: 'test',
    is_demo: false,
    title: 'Paracetamol 500 mg Tablets x 10',
    declared: {},
    product_url: 'https://acme.example/p',
    enquiry_url: null,
    availability: 'in_stock',
    availability_source: 'api',
    delivery_estimate: '2 days',
    audience: 'retail',
    prescription_required: null,
    lead_time: null,
    credit_terms: null,
    verification: {
      status: 'VERIFIED',
      reasons: ['Direct source evidence supports the price.'],
      checks: [],
      missing: [],
      conflicts: [],
      supplier_verification: 'not_independently_verified',
    },
    pricing: makePricing(pricing),
    tier: 'VERIFIED',
    eligible: true,
    ineligible_reasons: [],
    rank: 1,
    source_retrieved_at: new Date(Date.now() - 5 * 60_000).toISOString(),
    source_updated_at: null,
    evidence: [
      {
        type: 'api_response',
        source_url: 'https://acme.example/p',
        api_ref: 'x',
        excerpt: '',
        observed: { price: '24', currency: 'INR' },
        retrieved_at: new Date().toISOString(),
        source_updated_at: null,
      },
    ],
    duplicates_merged: 0,
    ...rest,
  }
}

export function makeProgress(over: Partial<Progress> = {}): Progress {
  return {
    state: 'RESULTS_READY',
    message: '2 offers found.',
    current_node: null,
    completed_nodes: ['validate_request', 'finalize_results'],
    sources: [],
    offers_discovered: 2,
    offers_verified: 1,
    offers_partially_verified: 0,
    offers_unverified: 1,
    offers_rejected: 0,
    unresolved: [],
    warnings: [],
    activity: [],
    error: null,
    finished: true,
    updated_at: null,
    ...over,
  }
}

export function makeDetail(over: Partial<SearchDetail> = {}): SearchDetail {
  return {
    id: 's1',
    created_at: new Date().toISOString(),
    identity: makeIdentity(),
    options: OPTIONS,
    progress: makeProgress(),
    is_terminal: true,
    is_demo_data_present: false,
    offers: [],
    target_currency: 'INR',
    ...over,
  }
}
