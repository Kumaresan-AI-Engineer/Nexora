import { Check } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Alert, Badge } from '@/components/ui/feedback'
import { Field, Input, Select } from '@/components/ui/form'
import { CATEGORY_FIELDS, CATEGORY_LABEL, confirmField, editField, FIELD_SPECS, USER_EVIDENCE } from '@/lib/identity'
import type { ExtractedField, FieldName, ProductCategory, ProductIdentity } from '@/lib/types'

function StatusBadge({ field }: { field: ExtractedField }) {
  if (field.status === 'unknown') return <Badge tone="neutral">Not found</Badge>
  if (field.status === 'inferred') return <Badge tone="warn">Inferred: please confirm</Badge>
  return <Badge tone="ok">{field.evidence === USER_EVIDENCE ? 'Provided by you' : 'Read from pack'}</Badge>
}

interface Props {
  identity: ProductIdentity
  onChange: (next: ProductIdentity) => void
}

export function IdentityForm({ identity, onChange }: Props) {
  const fields = CATEGORY_FIELDS[identity.category]

  return (
    <div className="flex flex-col gap-5">
      <Field label="Product category">
        {(p) => (
          <Select
            {...p}
            value={identity.category}
            onChange={(e) => onChange({ ...identity, category: e.target.value as ProductCategory })}
          >
            {(Object.keys(CATEGORY_LABEL) as ProductCategory[]).map((c) => (
              <option key={c} value={c}>
                {CATEGORY_LABEL[c]}
              </option>
            ))}
          </Select>
        )}
      </Field>

      {identity.contradictions.length > 0 && (
        <Alert tone="warn" title="The pack shows contradictory information">
          <ul className="list-disc pl-4">
            {identity.contradictions.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
          <Button
            variant="secondary"
            size="sm"
            className="mt-2"
            onClick={() => onChange({ ...identity, contradictions: [] })}
          >
            <Check className="size-4" aria-hidden /> I have checked this and corrected the fields below
          </Button>
        </Alert>
      )}

      <div className="grid gap-x-5 gap-y-4 sm:grid-cols-2">
        {fields.map((name: FieldName) => {
          const spec = FIELD_SPECS[name]
          const field = identity[name]
          return (
            <div key={name} className="flex flex-col gap-1.5">
              <Field label={spec.label} hint={field.status === 'unknown' ? spec.hint : undefined}>
                {(p) => (
                  <Input
                    {...p}
                    value={field.value ?? ''}
                    onChange={(e) => onChange(editField(identity, name, e.target.value))}
                  />
                )}
              </Field>
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge field={field} />
                {field.status === 'inferred' && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-xs"
                    onClick={() => onChange(confirmField(identity, name))}
                  >
                    Confirm value
                  </Button>
                )}
              </div>
              {field.evidence && field.evidence !== USER_EVIDENCE && (
                <p className="text-xs text-muted">Evidence: {field.evidence}</p>
              )}
            </div>
          )
        })}
      </div>

      {identity.notes.length > 0 && (
        <ul className="list-disc pl-5 text-xs text-muted">
          {identity.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
