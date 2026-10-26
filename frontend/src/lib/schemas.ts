import { z } from 'zod'
import type { SearchOptions } from './types'

const optionalMoney = z
  .string()
  .trim()
  .refine((v) => v === '' || (/^\d+(\.\d{1,2})?$/.test(v) && Number(v) >= 0), 'Enter a valid amount (up to 2 decimals)')

export const optionsFormSchema = z
  .object({
    provider: z.enum(['openai', 'gemini']),
    mode: z.enum(['retail', 'business']),
    market: z.enum(['india', 'global']),
    quantity: z
      .string()
      .trim()
      .regex(/^\d+$/, 'Enter a whole number')
      .refine((v) => Number(v) >= 1 && Number(v) <= 100000, 'Quantity must be between 1 and 100,000'),
    minPrice: optionalMoney,
    maxPrice: optionalMoney,
  })
  .superRefine((v, ctx) => {
    if (v.minPrice !== '' && v.maxPrice !== '' && Number(v.minPrice) > Number(v.maxPrice)) {
      ctx.addIssue({ code: 'custom', path: ['maxPrice'], message: 'Maximum must be at least the minimum' })
    }
  })

export type OptionsFormValues = z.infer<typeof optionsFormSchema>

export function toFormValues(o: SearchOptions): OptionsFormValues {
  return {
    provider: o.provider,
    mode: o.mode,
    market: o.market,
    quantity: String(o.quantity),
    minPrice: o.min_price === null ? '' : String(o.min_price),
    maxPrice: o.max_price === null ? '' : String(o.max_price),
  }
}

export function toSearchOptions(v: OptionsFormValues): SearchOptions {
  return {
    provider: v.provider,
    mode: v.mode,
    market: v.market,
    quantity: Number(v.quantity),
    min_price: v.minPrice === '' ? null : Number(v.minPrice),
    max_price: v.maxPrice === '' ? null : Number(v.maxPrice),
  }
}
