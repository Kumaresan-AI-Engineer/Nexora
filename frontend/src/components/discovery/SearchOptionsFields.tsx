import { Controller, useWatch, type Control, type FieldErrors, type UseFormRegister } from 'react-hook-form'
import { Field, Input, Segmented } from '@/components/ui/form'
import { Alert } from '@/components/ui/feedback'
import type { OptionsFormValues } from '@/lib/schemas'
import type { ProviderCapability } from '@/lib/types'
import { ProviderPicker } from './ProviderPicker'

interface Props {
  control: Control<OptionsFormValues>
  register: UseFormRegister<OptionsFormValues>
  errors: FieldErrors<OptionsFormValues>
  capabilities: ProviderCapability[] | undefined
  disabled?: boolean
}

export function SearchOptionsFields({ control, register, errors, capabilities, disabled }: Props) {
  const mode = useWatch({ control, name: 'mode' })
  const market = useWatch({ control, name: 'market' })
  return (
    <div className="flex flex-col gap-5">
      <Controller
        control={control}
        name="provider"
        render={({ field }) => (
          <ProviderPicker value={field.value} onChange={field.onChange} capabilities={capabilities} />
        )}
      />

      <div className="grid gap-5 sm:grid-cols-2">
        <Controller
          control={control}
          name="mode"
          render={({ field }) => (
            <Segmented
              label="Buying mode"
              name="mode"
              value={field.value}
              onChange={field.onChange}
              options={[
                {
                  value: 'retail',
                  label: 'Retail',
                  description: 'Compare single packs with delivery details where stated.',
                },
                {
                  value: 'business',
                  label: 'Business',
                  description: 'Wholesale view: minimum orders and quantity breaks, only where suppliers provide them.',
                },
              ]}
            />
          )}
        />
        <Controller
          control={control}
          name="market"
          render={({ field }) => (
            <Segmented
              label="Market"
              name="market"
              value={field.value}
              onChange={field.onChange}
              options={[
                { value: 'india', label: 'India' },
                { value: 'global', label: 'Global' },
              ]}
            />
          )}
        />
      </div>

      {market === 'global' && (
        <Alert tone="warn" title="Global listings need extra care">
          A product sold on an overseas site may not be legal to buy or import into India. Check local rules before
          ordering.
        </Alert>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <Field
          label={mode === 'business' ? 'Packs required' : 'Quantity (packs)'}
          error={errors.quantity?.message}
          hint="Optional; defaults to 1 pack"
        >
          {(p) => <Input {...p} inputMode="numeric" disabled={disabled} {...register('quantity')} />}
        </Field>
        <Field label="Minimum price" error={errors.minPrice?.message} hint="Per pack. Leave blank for no minimum">
          {(p) => (
            <Input {...p} inputMode="decimal" placeholder="No minimum" disabled={disabled} {...register('minPrice')} />
          )}
        </Field>
        <Field label="Maximum price" error={errors.maxPrice?.message} hint="Per pack. Leave blank for no maximum">
          {(p) => (
            <Input {...p} inputMode="decimal" placeholder="No maximum" disabled={disabled} {...register('maxPrice')} />
          )}
        </Field>
      </div>
    </div>
  )
}
