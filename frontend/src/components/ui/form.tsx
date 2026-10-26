import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

const control =
  'h-10 w-full rounded-lg border border-line-strong bg-surface px-3 text-sm text-ink placeholder:text-muted/70 disabled:bg-sunken disabled:text-muted aria-[invalid=true]:border-danger-fg'

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...rest },
  ref,
) {
  return <input ref={ref} className={cn(control, className)} {...rest} />
})

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select(
  { className, children, ...rest },
  ref,
) {
  return (
    <select ref={ref} className={cn(control, 'pr-8', className)} {...rest}>
      {children}
    </select>
  )
})

interface FieldProps {
  label: string
  hint?: string
  error?: string
  children: (props: { id: string; 'aria-describedby'?: string; 'aria-invalid'?: boolean }) => ReactNode
  className?: string
}

/** Label + control + hint/error wiring. Keeps every form field labelled and described. */
export function Field({ label, hint, error, children, className }: FieldProps) {
  const id = useId()
  const describedBy = error ? `${id}-err` : hint ? `${id}-hint` : undefined
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      <label htmlFor={id} className="text-sm font-medium text-ink">
        {label}
      </label>
      {children({ id, 'aria-describedby': describedBy, 'aria-invalid': error ? true : undefined })}
      {error ? (
        <p id={`${id}-err`} role="alert" className="text-xs text-danger-fg">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-xs text-muted">
          {hint}
        </p>
      ) : null}
    </div>
  )
}

interface SegmentedProps<T extends string> {
  label: string
  name: string
  value: T
  onChange: (v: T) => void
  options: { value: T; label: string; description?: string }[]
}

/** Accessible radio group rendered as a segmented control. */
export function Segmented<T extends string>({ label, name, value, onChange, options }: SegmentedProps<T>) {
  return (
    <fieldset className="flex flex-col gap-1.5">
      <legend className="mb-1.5 text-sm font-medium text-ink">{label}</legend>
      <div className="inline-flex w-full rounded-md border border-line-strong bg-sunken p-0.5">
        {options.map((o) => (
          <label
            key={o.value}
            className={cn(
              'flex-1 rounded px-3 py-1.5 text-center text-sm transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-brand-600',
              value === o.value ? 'bg-surface font-medium text-ink shadow-sm' : 'text-ink-soft hover:text-ink',
            )}
          >
            <input
              type="radio"
              className="sr-only"
              name={name}
              value={o.value}
              checked={value === o.value}
              onChange={() => onChange(o.value)}
            />
            {o.label}
          </label>
        ))}
      </div>
      {options.find((o) => o.value === value)?.description && (
        <p className="text-xs text-muted">{options.find((o) => o.value === value)?.description}</p>
      )}
    </fieldset>
  )
}
