import { create } from 'zustand'
import type { SearchOptions } from '@/lib/types'

export const DEFAULT_OPTIONS: SearchOptions = {
  provider: 'openai',
  mode: 'retail',
  market: 'india',
  quantity: 1,
  min_price: null,
  max_price: null,
}

export interface PriceFilter {
  min: string
  max: string
}

interface DiscoveryState {
  file: File | null
  options: SearchOptions
  priceFilter: PriceFilter
  setFile: (f: File | null) => void
  setOptions: (o: SearchOptions) => void
  setPriceFilter: (p: PriceFilter) => void
}

/** Draft state shared across pages (image, options, initial price filter). Server data lives in TanStack Query. */
export const useDiscovery = create<DiscoveryState>((set) => ({
  file: null,
  options: DEFAULT_OPTIONS,
  priceFilter: { min: '', max: '' },
  setFile: (file) => set({ file }),
  setOptions: (options) => set({ options }),
  setPriceFilter: (priceFilter) => set({ priceFilter }),
}))
