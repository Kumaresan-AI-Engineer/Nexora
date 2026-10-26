// Mirrors backend Pydantic schemas (docs/API.md).

export type ProviderName = 'openai' | 'gemini'
export type BuyingMode = 'retail' | 'business'
export type Market = 'india' | 'global'
export type FieldStatus = 'confirmed' | 'inferred' | 'unknown'
export type ProductCategory = 'medicine' | 'supply' | 'equipment' | 'unknown'

export interface ExtractedField {
  value: string | null
  status: FieldStatus
  evidence: string | null
}

export const FIELD_NAMES = [
  'brand_name',
  'generic_name',
  'active_ingredients',
  'strength',
  'dosage_form',
  'route',
  'pack_quantity',
  'pack_configuration',
  'manufacturer',
  'barcode',
  'product_name',
  'model_sku',
  'size_dimensions',
  'material',
  'sterile',
  'certifications',
] as const
export type FieldName = (typeof FIELD_NAMES)[number]

export type ProductIdentity = { category: ProductCategory } & Record<FieldName, ExtractedField> & {
    contradictions: string[]
    notes: string[]
    extracted_by: string | null
  }

export interface Ambiguity {
  needs_clarification: boolean
  missing_essentials: string[]
  unconfirmed_essentials: string[]
  contradictions: string[]
  messages: string[]
}

export interface IdentifyResponse {
  identity: ProductIdentity
  ambiguity: Ambiguity
  provider: string
  model: string
  duration_ms: number
  state: string
}

export interface SearchOptions {
  provider: ProviderName
  mode: BuyingMode
  market: Market
  quantity: number
  min_price: number | null
  max_price: number | null
}

export type WorkflowState =
  | 'REQUEST_RECEIVED'
  | 'IDENTIFYING_PRODUCT'
  | 'IDENTITY_READY'
  | 'NEEDS_CLARIFICATION'
  | 'SEARCHING_SUPPLIERS'
  | 'VERIFYING_OFFERS'
  | 'PARTIAL_RESULTS'
  | 'RESULTS_READY'
  | 'NO_MATCHES'
  | 'SOURCE_UNAVAILABLE'
  | 'FAILED'

export interface SourceStatus {
  connector_id: string
  name: string
  kind: string
  is_demo: boolean
  status: 'pending' | 'ok' | 'timeout' | 'error' | 'skipped'
  offers: number
  attempts: number
  duration_ms: number | null
  error: string | null
}

export type ActivityPhase = 'plan' | 'search' | 'read' | 'verify' | 'rank' | 'done'

export interface ActivityEvent {
  at: string
  phase: ActivityPhase
  level: 'info' | 'success' | 'warn' | 'error'
  message: string
}

export interface Progress {
  state: WorkflowState
  message: string
  current_node: string | null
  completed_nodes: string[]
  sources: SourceStatus[]
  offers_discovered: number
  offers_verified: number
  offers_partially_verified: number
  offers_unverified: number
  offers_rejected: number
  unresolved: string[]
  warnings: string[]
  activity: ActivityEvent[]
  error: string | null
  finished: boolean
  updated_at: string | null
}

export type VerificationStatus = 'VERIFIED' | 'PARTIALLY_VERIFIED' | 'UNVERIFIED' | 'REJECTED'
export type Availability = 'in_stock' | 'out_of_stock' | 'limited' | 'unknown'
export type Audience = 'retail' | 'business' | 'both' | 'unknown'

export interface Check {
  name: string
  result: string
  detail: string
}

export interface Verification {
  status: VerificationStatus
  reasons: string[]
  checks: Check[]
  missing: string[]
  conflicts: string[]
  supplier_verification: string
}

export interface Evidence {
  type: 'api_response' | 'page_extraction' | 'search_snippet' | 'reference_data' | 'fixture'
  source_url: string | null
  api_ref: string | null
  excerpt: string
  observed: Record<string, string>
  retrieved_at: string
  source_updated_at: string | null
}

export interface Pricing {
  currency_original: string | null
  target_currency: string
  pack_price_original: number | null
  pack_price: number | null
  mrp_original: number | null
  mrp: number | null
  fx_rate: number | null
  fx_observed_at: string | null
  fx_source: string | null
  comparability: 'same_pack' | 'pack_differs' | 'unknown_pack'
  offer_pack_units: number | null
  unit_price: number | null
  requested_units: number | null
  packs_needed: number | null
  requested_cost: number | null
  moq_packs: number | null
  moq_applied: boolean
  price_break_applied: boolean
  shipping_cost: number | null
  shipping_status: 'known' | 'unknown'
  tax_status: 'included' | 'added' | 'unknown'
  tax_amount: number | null
  estimated_known_total: number | null
  total_is_complete: boolean
  final_payable: number | null
  exclusions: string[]
  notes: string[]
}

export interface Offer {
  offer_id: string
  supplier_name: string
  supplier_country: string | null
  supplier_domain: string | null
  connector_id: string
  is_demo: boolean
  title: string
  declared: Record<string, string | null>
  product_url: string | null
  enquiry_url: string | null
  availability: Availability
  availability_source: string | null
  delivery_estimate: string | null
  audience: Audience
  prescription_required: boolean | null
  lead_time: string | null
  credit_terms: string | null
  verification: Verification
  pricing: Pricing
  tier: VerificationStatus
  eligible: boolean
  ineligible_reasons: string[]
  rank: number | null
  source_retrieved_at: string | null
  source_updated_at: string | null
  evidence: Evidence[]
  duplicates_merged: number
}

export interface SearchDetail {
  id: string
  created_at: string
  identity: ProductIdentity
  options: SearchOptions
  progress: Progress
  is_terminal: boolean
  is_demo_data_present: boolean
  offers: Offer[]
  target_currency: string | null
}

export interface SearchSummary {
  id: string
  created_at: string
  product_label: string
  options: SearchOptions
  state: WorkflowState
  is_terminal: boolean
  offers_discovered: number
}

export interface SearchPage {
  items: SearchSummary[]
  total: number
  limit: number
  offset: number
}

export interface ProviderCapability {
  provider: ProviderName
  configured: boolean
  missing: string[]
}

export interface AppConfig {
  app_name: string
  providers: ProviderCapability[]
  markets: Market[]
  modes: BuyingMode[]
  demo_mode: boolean
  limits: { max_upload_mb: number; allowed_mime: string[]; max_quantity: number }
  sources: { id: string; name: string; kind: string; is_demo: boolean; configured: boolean; hint?: string }[]
  currency: { provider: string; india: string; global: string }
}
