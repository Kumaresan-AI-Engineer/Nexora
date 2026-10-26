import type { Tone } from '@/components/ui/feedback'
import type { WorkflowState } from './types'

export const STATE_TONE: Record<WorkflowState, Tone> = {
  REQUEST_RECEIVED: 'info',
  IDENTIFYING_PRODUCT: 'info',
  IDENTITY_READY: 'info',
  NEEDS_CLARIFICATION: 'warn',
  SEARCHING_SUPPLIERS: 'info',
  VERIFYING_OFFERS: 'info',
  PARTIAL_RESULTS: 'warn',
  RESULTS_READY: 'ok',
  NO_MATCHES: 'neutral',
  SOURCE_UNAVAILABLE: 'danger',
  FAILED: 'danger',
}
