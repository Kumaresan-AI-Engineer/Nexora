import type { ExtractedField, FieldName, ProductCategory, ProductIdentity } from './types'
import { FIELD_NAMES } from './types'

export interface FieldSpec {
  name: FieldName
  label: string
  hint?: string
  multiline?: boolean
}

export const FIELD_SPECS: Record<FieldName, FieldSpec> = {
  brand_name: { name: 'brand_name', label: 'Brand name' },
  generic_name: { name: 'generic_name', label: 'Generic name' },
  active_ingredients: { name: 'active_ingredients', label: 'Active ingredient(s)', hint: 'Separate multiple with +' },
  strength: { name: 'strength', label: 'Strength', hint: 'e.g. 500 mg' },
  dosage_form: { name: 'dosage_form', label: 'Dosage form', hint: 'e.g. Tablet, Extended release tablet' },
  route: { name: 'route', label: 'Route' },
  pack_quantity: { name: 'pack_quantity', label: 'Units per pack', hint: 'Whole number, e.g. 10' },
  pack_configuration: { name: 'pack_configuration', label: 'Pack configuration', hint: 'e.g. 10 tablets x 10 strips' },
  manufacturer: { name: 'manufacturer', label: 'Manufacturer' },
  barcode: { name: 'barcode', label: 'Barcode / GTIN' },
  product_name: { name: 'product_name', label: 'Product name' },
  model_sku: { name: 'model_sku', label: 'Model / SKU' },
  size_dimensions: { name: 'size_dimensions', label: 'Size / dimensions' },
  material: { name: 'material', label: 'Material' },
  sterile: { name: 'sterile', label: 'Sterile', hint: 'yes / no' },
  certifications: { name: 'certifications', label: 'Certifications / specifications' },
}

export const CATEGORY_FIELDS: Record<ProductCategory, FieldName[]> = {
  medicine: [
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
  ],
  supply: [
    'product_name',
    'brand_name',
    'manufacturer',
    'model_sku',
    'size_dimensions',
    'material',
    'sterile',
    'pack_quantity',
    'pack_configuration',
    'certifications',
    'barcode',
  ],
  equipment: [
    'product_name',
    'brand_name',
    'manufacturer',
    'model_sku',
    'size_dimensions',
    'material',
    'sterile',
    'pack_quantity',
    'certifications',
    'barcode',
  ],
  unknown: ['product_name', 'brand_name', 'generic_name', 'manufacturer', 'pack_quantity'],
}

export const CATEGORY_LABEL: Record<ProductCategory, string> = {
  medicine: 'Medicine',
  supply: 'Pharmacy supply',
  equipment: 'Medical equipment',
  unknown: 'Not determined',
}

export const USER_EVIDENCE = 'Provided by user'
export const USER_CONFIRMED = 'Confirmed by user'

export function editField(identity: ProductIdentity, name: FieldName, value: string): ProductIdentity {
  const trimmed = value.trim()
  const next: ExtractedField = trimmed
    ? { value, status: 'confirmed', evidence: USER_EVIDENCE }
    : { value: null, status: 'unknown', evidence: null }
  return { ...identity, [name]: next }
}

export function confirmField(identity: ProductIdentity, name: FieldName): ProductIdentity {
  const f = identity[name]
  if (!f.value) return identity
  return { ...identity, [name]: { ...f, status: 'confirmed', evidence: f.evidence ?? USER_CONFIRMED } }
}

export function normalizeForSubmit(identity: ProductIdentity): ProductIdentity {
  const out = { ...identity }
  for (const n of FIELD_NAMES) {
    const f = out[n]
    if (f.value !== null && f.value.trim() === '') out[n] = { value: null, status: 'unknown', evidence: null }
    else if (f.value !== null) out[n] = { ...f, value: f.value.trim() }
  }
  return out
}

export function emptyIdentity(category: ProductCategory = 'unknown'): ProductIdentity {
  const blank: ExtractedField = { value: null, status: 'unknown', evidence: null }
  const fields = Object.fromEntries(FIELD_NAMES.map((n) => [n, { ...blank }])) as Record<FieldName, ExtractedField>
  return { category, ...fields, contradictions: [], notes: [], extracted_by: null }
}

export function identityLabel(identity: ProductIdentity): string {
  const pick = (n: FieldName) => (identity[n].value ?? '').trim() || null
  return (
    pick('brand_name') ??
    pick('product_name') ??
    pick('generic_name') ??
    pick('active_ingredients') ??
    'Unidentified product'
  )
}
