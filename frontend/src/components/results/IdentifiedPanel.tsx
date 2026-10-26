import { useMutation } from '@tanstack/react-query'
import { ChevronDown, Search } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { IdentityForm } from '@/components/review/IdentityForm'
import { Button } from '@/components/ui/Button'
import { Alert } from '@/components/ui/feedback'
import { api, ApiError } from '@/lib/api'
import { normalizeForSubmit } from '@/lib/identity'
import type { SearchDetail } from '@/lib/types'

/**
 * Optional, never required: shows what was read from the pack, flags unclear details, and lets the user
 * add or correct details and search again. Unknown details are never filled in automatically.
 */
export function IdentifiedPanel({ detail }: { detail: SearchDetail }) {
  const navigate = useNavigate()
  const [identity, setIdentity] = useState(detail.identity)
  const warnings = detail.progress.warnings
  const needsInput = detail.progress.state === 'NEEDS_CLARIFICATION'
  const changed = JSON.stringify(identity) !== JSON.stringify(detail.identity)

  const again = useMutation({
    mutationFn: () => api.createSearch(normalizeForSubmit(identity), detail.options),
    onSuccess: (r) => void navigate(`/searches/${r.id}`),
  })
  const err = again.error instanceof ApiError ? again.error : null

  return (
    <details open={needsInput} className="group">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-3.5">
        <span className="text-sm font-semibold">
          What we identified
          <span className="ml-2 font-normal text-ink-soft">
            {warnings.length > 0 || needsInput
              ? 'Some details were unclear. Add them to refine the results'
              : 'Check or correct the details read from the pack'}
          </span>
        </span>
        <ChevronDown className="size-4 shrink-0 text-muted transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <div className="flex flex-col gap-4 border-t border-line p-5">
        {warnings.length > 0 && (
          <Alert tone="info" title="Unclear on the pack">
            <ul className="list-disc pl-4">
              {warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
            <p className="mt-1">
              The search still ran with what was readable. Offers cannot be marked fully source-verified until the
              details they depend on are known.
            </p>
          </Alert>
        )}
        <IdentityForm identity={identity} onChange={setIdentity} />
        {err && (
          <Alert tone="danger" title="Could not start the search">
            {err.message}
          </Alert>
        )}
        <div>
          <Button disabled={!changed} loading={again.isPending} onClick={() => again.mutate()}>
            <Search className="size-4" aria-hidden /> Search again with these details
          </Button>
        </div>
      </div>
    </details>
  )
}
