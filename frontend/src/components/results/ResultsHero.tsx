import { ExternalLink } from 'lucide-react'
import { Badge } from '@/components/ui/feedback'
import { elapsedSeconds } from '@/lib/activity'
import { formatMoney, safeExternalUrl, STATE_LABEL } from '@/lib/format'
import { identityLabel } from '@/lib/identity'
import { countByTier } from '@/lib/offers'
import { STATE_TONE } from '@/lib/stateTone'
import type { SearchDetail } from '@/lib/types'
import { VerificationBadge } from './VerificationBadge'

function Kpi({ label, children, sub }: { label: string; children: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="rounded-xl bg-white/10 p-4 ring-1 ring-white/15 backdrop-blur-sm">
      <p className="text-xs font-medium uppercase tracking-wider text-white/60">{label}</p>
      <div className="mt-1.5 text-3xl font-semibold tabular-nums leading-none">{children}</div>
      {sub && <div className="mt-2 text-xs text-white/70">{sub}</div>}
    </div>
  )
}

/** Summary band: what was identified, how the search is going, and the top-ranked offer. */
export function ResultsHero({ detail }: { detail: SearchDetail }) {
  const { identity: ident, options: o, progress, offers } = detail
  const counts = countByTier(offers)
  const priced = offers.filter((x) => x.tier !== 'REJECTED' && x.pricing.pack_price_original !== null)
  const best = offers.find((x) => x.rank === 1)
  const bestUrl = best ? safeExternalUrl(best.product_url) : null
  const activeSources = progress.sources.filter((s) => s.status !== 'skipped')
  const doneSources = activeSources.filter((s) => s.status !== 'pending').length
  const secs = elapsedSeconds(progress)
  const running = !progress.finished

  const productChips = [
    ident.strength.value,
    ident.dosage_form.value,
    ident.pack_configuration.value ?? (ident.pack_quantity.value ? `${ident.pack_quantity.value} per pack` : null),
    ident.manufacturer.value,
  ].filter((c): c is string => Boolean(c))
  const searchChips = [
    o.mode === 'business' ? 'Business' : 'Retail',
    o.market === 'india' ? 'India' : 'Global',
    `${o.quantity} pack${o.quantity === 1 ? '' : 's'}`,
    detail.target_currency ? `Amounts in ${detail.target_currency}` : null,
  ].filter((c): c is string => Boolean(c))

  return (
    <section
      aria-label="Search summary"
      className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-brand-950 via-brand-900 to-brand-700 text-white shadow-lg"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(rgba(255,255,255,0.08)_1px,transparent_1px)] [background-size:22px_22px]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -right-20 -top-20 size-80 rounded-full bg-accent/15 blur-3xl"
      />
      <div className="relative p-6 sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-widest text-accent">Search results</p>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">{identityLabel(ident)}</h1>
          <Badge tone={STATE_TONE[progress.state]}>{STATE_LABEL[progress.state]}</Badge>
        </div>
        <ul className="mt-4 flex flex-wrap gap-2 text-xs">
          {productChips.map((c) => (
            <li key={c} className="rounded-md bg-white/10 px-2.5 py-1 font-medium ring-1 ring-white/15">
              {c}
            </li>
          ))}
          {searchChips.map((c) => (
            <li key={c} className="rounded-md bg-accent/15 px-2.5 py-1 font-medium text-accent ring-1 ring-accent/25">
              {c}
            </li>
          ))}
        </ul>

        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <Kpi
            label="Top-ranked offer"
            sub={
              best ? (
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-white">{best.supplier_name}</span>
                  <VerificationBadge status={best.tier} />
                  {bestUrl && (
                    <a
                      href={bestUrl}
                      target="_blank"
                      rel="noopener noreferrer nofollow"
                      className="inline-flex items-center gap-1 font-medium text-accent hover:underline"
                    >
                      Open supplier page <ExternalLink className="size-3" aria-hidden />
                    </a>
                  )}
                </span>
              ) : running ? (
                'Waiting for the first priced offer'
              ) : (
                'No comparable offer'
              )
            }
          >
            {best ? formatMoney(best.pricing.requested_cost, best.pricing.target_currency) : '—'}
          </Kpi>
          <Kpi
            label="Offers with a price"
            sub={
              offers.length - priced.length - counts.REJECTED > 0
                ? `${offers.length - priced.length - counts.REJECTED} more listing(s) without a price`
                : 'Ranked by cost for your quantity'
            }
          >
            {priced.length}
          </Kpi>
          <Kpi label="Source-verified" sub={`${counts.PARTIALLY_VERIFIED} partially verified`}>
            {counts.VERIFIED}
          </Kpi>
          <Kpi
            label="Sources searched"
            sub={
              secs !== null
                ? `${secs.toFixed(1)} s ${running ? 'so far' : 'in total'}`
                : running
                  ? 'Starting…'
                  : undefined
            }
          >
            {doneSources}
            <span className="text-lg text-white/60"> of {activeSources.length}</span>
          </Kpi>
        </div>
      </div>
    </section>
  )
}
