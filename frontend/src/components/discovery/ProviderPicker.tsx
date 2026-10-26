import { CheckCircle2, CircleAlert } from 'lucide-react'
import { cn } from '@/lib/cn'
import type { ProviderCapability, ProviderName } from '@/lib/types'

const LABEL: Record<ProviderName, { name: string; blurb: string }> = {
  openai: { name: 'OpenAI', blurb: 'Reads the image with the configured OpenAI vision model.' },
  gemini: { name: 'Google Gemini', blurb: 'Reads the image with the configured Gemini vision model.' },
}

interface Props {
  value: ProviderName
  onChange: (p: ProviderName) => void
  capabilities: ProviderCapability[] | undefined
}

/** The chosen provider is the only one used. No automatic fallback. */
export function ProviderPicker({ value, onChange, capabilities }: Props) {
  return (
    <fieldset>
      <legend className="mb-1.5 text-sm font-medium">Vision provider</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {(Object.keys(LABEL) as ProviderName[]).map((p) => {
          const cap = capabilities?.find((c) => c.provider === p)
          const selected = value === p
          return (
            <label
              key={p}
              className={cn(
                'flex gap-3 rounded-md border bg-surface p-3 text-sm has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-brand-600',
                selected ? 'border-brand-600 ring-1 ring-brand-600' : 'border-line-strong hover:bg-sunken',
              )}
            >
              <input
                type="radio"
                name="provider"
                value={p}
                checked={selected}
                onChange={() => onChange(p)}
                className="mt-1 accent-brand-700"
              />
              <span className="min-w-0">
                <span className="block font-medium">{LABEL[p].name}</span>
                <span className="block text-xs text-muted">{LABEL[p].blurb}</span>
                {cap &&
                  (cap.configured ? (
                    <span className="mt-1 inline-flex items-center gap-1 text-xs text-ok-fg">
                      <CheckCircle2 className="size-3.5" aria-hidden /> Configured
                    </span>
                  ) : (
                    <span className="mt-1 inline-flex items-start gap-1 text-xs text-warn-fg">
                      <CircleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                      <span>
                        Not configured. Set <code className="font-mono">{cap.missing.join(', ')}</code> on the server.
                      </span>
                    </span>
                  ))}
              </span>
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}
