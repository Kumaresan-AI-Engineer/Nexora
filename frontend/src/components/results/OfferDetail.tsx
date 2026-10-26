import { Check, ExternalLink, Minus, X } from 'lucide-react'
import { formatDateTime, formatMoney, safeExternalUrl } from '@/lib/format'
import type { BuyingMode, Evidence, Offer } from '@/lib/types'

const EVIDENCE_LABEL: Record<Evidence['type'], string> = {
  api_response: 'Supplier API response (direct)',
  page_extraction: 'Product page structured data (direct)',
  search_snippet: 'Search snippet (not sufficient on its own)',
  reference_data: 'Reference data',
  fixture: 'Demonstration fixture (fictional)',
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-1">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right tabular-nums">{children}</dd>
    </div>
  )
}

function CheckIcon({ result }: { result: string }) {
  if (result === 'pass') return <Check className="size-4 text-ok-fg" aria-label="passed" />
  if (result === 'fail' || result === 'conflict') return <X className="size-4 text-danger-fg" aria-label="failed" />
  return <Minus className="size-4 text-muted" aria-label={result === 'missing' ? 'not stated' : 'note'} />
}

export function OfferDetail({ offer, mode }: { offer: Offer; mode: BuyingMode }) {
  const p = offer.pricing
  const cur = p.target_currency
  const v = offer.verification
  return (
    <div className="grid gap-6 bg-sunken/60 p-4 text-sm lg:grid-cols-3">
      <section aria-label="Verification">
        <h4 className="mb-2 font-semibold">Verification</h4>
        <ul className="list-disc pl-4 text-ink-soft">
          {v.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
        {v.conflicts.length > 0 && (
          <div className="mt-2">
            <p className="font-medium text-danger-fg">Conflicting evidence</p>
            <ul className="list-disc pl-4">
              {v.conflicts.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>
        )}
        {v.missing.length > 0 && <p className="mt-2 text-muted">Not established: {v.missing.join(', ')}</p>}
        <ul className="mt-3 space-y-1">
          {v.checks.map((c) => (
            <li key={`${c.name}-${c.detail}`} className="flex gap-2">
              <span className="mt-0.5 shrink-0">
                <CheckIcon result={c.result} />
              </span>
              <span>
                <span className="font-medium">{c.name.replace('match:', '').replaceAll('_', ' ')}</span>
                {c.detail && <span className="text-muted">: {c.detail}</span>}
              </span>
            </li>
          ))}
        </ul>
        {offer.ineligible_reasons.length > 0 && (
          <div className="mt-3 rounded border border-line bg-surface p-2">
            <p className="font-medium">Not ranked</p>
            <ul className="list-disc pl-4 text-ink-soft">
              {offer.ineligible_reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section aria-label="Cost breakdown">
        <h4 className="mb-2 font-semibold">Cost breakdown</h4>
        <dl className="divide-y divide-line">
          <Row label="Supplier price per pack">
            {p.pack_price !== null
              ? formatMoney(p.pack_price, cur)
              : `${formatMoney(p.pack_price_original, p.currency_original)} (not converted)`}
          </Row>
          {p.fx_rate !== null && p.fx_source !== 'same currency' && (
            <Row label="Exchange rate">
              {p.fx_rate} ({p.fx_source}, {formatDateTime(p.fx_observed_at)})
            </Row>
          )}
          <Row label="MRP / list price (separate)">{p.mrp !== null ? formatMoney(p.mrp, cur) : 'Not stated'}</Row>
          <Row label="Units per offer pack">{p.offer_pack_units ?? 'Unknown'}</Row>
          <Row label="Requested units">{p.requested_units ?? '—'}</Row>
          <Row label="Packs billed">
            {p.packs_needed !== null ? (p.moq_applied && p.moq_packs ? p.moq_packs : p.packs_needed) : '—'}
          </Row>
          <Row label="Product cost (requested qty)">{formatMoney(p.requested_cost, cur)}</Row>
          <Row label="Shipping">{p.shipping_status === 'known' ? formatMoney(p.shipping_cost, cur) : 'Not stated'}</Row>
          <Row label="Tax">
            {p.tax_status === 'included'
              ? 'Included in price'
              : p.tax_status === 'added'
                ? formatMoney(p.tax_amount, cur)
                : 'Not stated'}
          </Row>
          <Row label={p.total_is_complete ? 'Estimated total' : 'Estimated total (known costs only)'}>
            {formatMoney(p.estimated_known_total, cur)}
          </Row>
          <Row label="Final payable (stated by source)">
            {p.final_payable !== null ? formatMoney(p.final_payable, cur) : 'Not stated'}
          </Row>
        </dl>
        {p.exclusions.length > 0 && (
          <ul className="mt-2 list-disc pl-4 text-warn-fg">
            {p.exclusions.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        )}
        {p.notes.length > 0 && (
          <ul className="mt-2 list-disc pl-4 text-ink-soft">
            {p.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        )}
        <p className="mt-3 text-xs text-muted">
          Listed prices are as observed at the source. The checkout price may differ, and is only shown as final when
          the source states it.
        </p>
      </section>

      <section aria-label="Evidence">
        <h4 className="mb-2 font-semibold">Source evidence</h4>
        <ul className="space-y-3">
          {offer.evidence.map((e, i) => {
            const url = safeExternalUrl(e.source_url)
            return (
              <li key={`${e.type}-${i}`} className="rounded border border-line bg-surface p-2">
                <p className="font-medium">{EVIDENCE_LABEL[e.type]}</p>
                {url ? (
                  <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer nofollow"
                    className="inline-flex items-center gap-1 break-all text-brand-700 underline-offset-2 hover:underline"
                  >
                    {url} <ExternalLink className="size-3 shrink-0" aria-hidden />
                  </a>
                ) : (
                  e.source_url && <p className="break-all text-muted">{e.source_url} (link not shown)</p>
                )}
                {e.excerpt && <p className="mt-1 text-ink-soft">“{e.excerpt}”</p>}
                {Object.keys(e.observed).length > 0 && (
                  <p className="mt-1 text-xs text-muted">
                    Observed:{' '}
                    {Object.entries(e.observed)
                      .map(([k, val]) => `${k} ${val}`)
                      .join(', ')}
                  </p>
                )}
                <p className="text-xs text-muted">
                  Retrieved {formatDateTime(e.retrieved_at)}
                  {e.source_updated_at && ` · source updated ${formatDateTime(e.source_updated_at)}`}
                </p>
              </li>
            )
          })}
        </ul>
        <dl className="mt-3 divide-y divide-line">
          <Row label="Prescription requirement">
            {offer.prescription_required === null
              ? 'Not stated by source'
              : offer.prescription_required
                ? 'Required (per source)'
                : 'Not required (per source)'}
          </Row>
          <Row label="Availability source">{offer.availability_source ?? 'Not stated'}</Row>
          {mode === 'business' && <Row label="Lead time">{offer.lead_time ?? 'Not stated'}</Row>}
          {mode === 'business' && <Row label="Credit terms">{offer.credit_terms ?? 'Not stated'}</Row>}
          <Row label="Supplier legitimacy">Not independently verified</Row>
          {offer.duplicates_merged > 0 && <Row label="Duplicate listings merged">{offer.duplicates_merged}</Row>}
        </dl>
      </section>
    </div>
  )
}
