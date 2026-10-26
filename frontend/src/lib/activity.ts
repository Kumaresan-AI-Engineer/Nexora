import type { ActivityPhase, Progress } from './types'

export const PHASE_IDS = ['plan', 'search', 'read', 'verify', 'rank'] as const
export type StageId = (typeof PHASE_IDS)[number]
export type PhaseState = 'done' | 'active' | 'pending' | 'skipped'

/** Derives each stage's state only from events the workflow really recorded. */
export function phaseStates(progress: Progress): Record<StageId, PhaseState> {
  const seen = new Set<ActivityPhase>(progress.activity.map((e) => e.phase))
  const out = {} as Record<StageId, PhaseState>
  if (progress.finished) {
    for (const id of PHASE_IDS) out[id] = seen.has(id) ? 'done' : 'skipped'
    return out
  }
  const last = [...progress.activity].reverse().find((e) => e.phase !== 'done')?.phase ?? 'plan'
  const lastIdx = PHASE_IDS.indexOf(last as StageId)
  PHASE_IDS.forEach((id, i) => {
    out[id] = i < lastIdx ? (seen.has(id) ? 'done' : 'skipped') : i === lastIdx ? 'active' : 'pending'
  })
  return out
}

export function elapsedSeconds(progress: Progress): number | null {
  const ev = progress.activity
  const first = ev[0]
  const last = ev[ev.length - 1]
  if (ev.length < 2 || !first || !last) return null
  return Math.max(0, (new Date(last.at).getTime() - new Date(first.at).getTime()) / 1000)
}
