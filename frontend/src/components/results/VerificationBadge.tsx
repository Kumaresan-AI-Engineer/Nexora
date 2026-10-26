import { BadgeCheck, CircleDashed, CircleHelp, Ban } from 'lucide-react'
import { Badge, type Tone } from '@/components/ui/feedback'
import { VERIFICATION_HELP, VERIFICATION_LABEL } from '@/lib/format'
import type { VerificationStatus } from '@/lib/types'

const TONE: Record<VerificationStatus, Tone> = {
  VERIFIED: 'ok',
  PARTIALLY_VERIFIED: 'warn',
  UNVERIFIED: 'neutral',
  REJECTED: 'danger',
}
const ICON = { VERIFIED: BadgeCheck, PARTIALLY_VERIFIED: CircleDashed, UNVERIFIED: CircleHelp, REJECTED: Ban }

export function VerificationBadge({ status }: { status: VerificationStatus }) {
  const Icon = ICON[status]
  return (
    <Badge tone={TONE[status]} title={VERIFICATION_HELP[status]}>
      <Icon className="size-3.5" aria-hidden />
      {VERIFICATION_LABEL[status]}
    </Badge>
  )
}
