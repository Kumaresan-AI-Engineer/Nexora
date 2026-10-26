import { useMutation } from '@tanstack/react-query'
import { ChevronDown, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/Button'
import { Alert } from '@/components/ui/feedback'
import { Field, Input, Segmented } from '@/components/ui/form'
import { api, ApiError } from '@/lib/api'
import { normalizeForSubmit } from '@/lib/identity'
import type { BuyingMode, Market, SearchDetail } from '@/lib/types'

/**
 * Settings that change how offers are priced and which sources are relevant (mode, market, quantity).
 * Applying them runs a fresh search for the same product; price/stock/country are instant filters below.
 */
export function RefinePanel({ detail }: { detail: SearchDetail }) {
  const navigate = useNavigate()
  const o = detail.options
  const [mode, setMode] = useState<BuyingMode>(o.mode)
  const [market, setMarket] = useState<Market>(o.market)
  const [quantity, setQuantity] = useState(String(o.quantity))

  const qty = Number(quantity)
  const qtyValid = /^\d+$/.test(quantity) && qty >= 1 && qty <= 100000
  const changed = mode !== o.mode || market !== o.market || qty !== o.quantity

  const rerun = useMutation({
    mutationFn: () => api.createSearch(normalizeForSubmit(detail.identity), { ...o, mode, market, quantity: qty }),
    onSuccess: (r) => void navigate(`/searches/${r.id}`),
  })
  const err = rerun.error instanceof ApiError ? rerun.error : null

  return (
    <details className="group">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-3.5">
        <span className="text-sm font-semibold">
          Change quantity, buying mode or market
          <span className="ml-2 font-normal text-ink-soft">Runs a new search with your changes</span>
        </span>
        <ChevronDown className="size-4 shrink-0 text-muted transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <div className="flex flex-col gap-4 border-t border-line p-5">
        <div className="grid gap-4 sm:grid-cols-3">
          <Segmented
            label="Buying mode"
            name="refine-mode"
            value={mode}
            onChange={setMode}
            options={[
              { value: 'retail', label: 'Retail' },
              { value: 'business', label: 'Business' },
            ]}
          />
          <Segmented
            label="Market"
            name="refine-market"
            value={market}
            onChange={setMarket}
            options={[
              { value: 'india', label: 'India' },
              { value: 'global', label: 'Global' },
            ]}
          />
          <Field
            label="Quantity (packs)"
            error={quantity !== '' && !qtyValid ? 'Enter a whole number from 1 to 100,000' : undefined}
          >
            {(p) => <Input {...p} inputMode="numeric" value={quantity} onChange={(e) => setQuantity(e.target.value)} />}
          </Field>
        </div>
        {err && (
          <Alert tone="danger" title="Could not start the search">
            {err.message}
          </Alert>
        )}
        <div>
          <Button disabled={!changed || !qtyValid} loading={rerun.isPending} onClick={() => rerun.mutate()}>
            <RefreshCw className="size-4" aria-hidden /> Update results
          </Button>
        </div>
      </div>
    </details>
  )
}
