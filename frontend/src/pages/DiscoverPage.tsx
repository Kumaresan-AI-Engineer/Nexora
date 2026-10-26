import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import {
  BadgeCheck,
  ChevronDown,
  ExternalLink,
  FileSearch,
  Scale,
  ScanLine,
  Search,
  ShieldCheck,
  Sparkles,
  Store,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { ImageDropzone } from '@/components/discovery/ImageDropzone'
import { RecentSearches } from '@/components/discovery/RecentSearches'
import { RunProgress, type IdentifiedSummary } from '@/components/discovery/RunProgress'
import { SearchOptionsFields } from '@/components/discovery/SearchOptionsFields'
import { Button } from '@/components/ui/Button'
import { Alert } from '@/components/ui/feedback'
import { useConfig } from '@/hooks/queries'
import { api, ApiError } from '@/lib/api'
import { identityLabel, normalizeForSubmit } from '@/lib/identity'
import { optionsFormSchema, toFormValues, toSearchOptions, type OptionsFormValues } from '@/lib/schemas'
import { useDiscovery } from '@/store/discovery'

const PROVIDER_NAME = { openai: 'OpenAI', gemini: 'Google Gemini' } as const

const FEATURES = [
  {
    icon: ScanLine,
    title: 'Reads the pack for you',
    text: 'Upload one photo. The name, strength and pack size are read automatically.',
  },
  {
    icon: Store,
    title: 'Searches suppliers live',
    text: 'Watch the agent query sources and open supplier pages in real time.',
  },
  {
    icon: BadgeCheck,
    title: 'Verifies every price',
    text: 'Each offer is tagged by how much direct evidence supports it.',
  },
]

const STEPS = [
  {
    icon: ScanLine,
    title: 'Upload a photo',
    text: 'The AI reads the product. Nothing is guessed: unreadable details stay blank and are flagged.',
  },
  {
    icon: Search,
    title: 'Agent searches suppliers',
    text: 'Sources are queried and supplier pages are read. Every step is shown live.',
  },
  {
    icon: Scale,
    title: 'Compare with confidence',
    text: 'Offers are ranked by cost, tagged by verification, and linked to the supplier.',
  },
]

export function DiscoverPage() {
  const navigate = useNavigate()
  const config = useConfig()
  const { file, options, priceFilter, setFile, setOptions, setPriceFilter } = useDiscovery()
  const [noFile, setNoFile] = useState(false)
  const [stage, setStage] = useState<'idle' | 'reading' | 'searching'>('idle')
  const [identified, setIdentified] = useState<IdentifiedSummary | null>(null)

  const form = useForm<OptionsFormValues>({
    resolver: zodResolver(optionsFormSchema),
    defaultValues: { ...toFormValues(options), minPrice: priceFilter.min, maxPrice: priceFilter.max },
    mode: 'onBlur',
  })
  const provider = useWatch({ control: form.control, name: 'provider' })

  // Pick a configured provider automatically so the user never has to think about it.
  const providers = config.data?.providers
  useEffect(() => {
    if (!providers || form.formState.dirtyFields.provider) return
    const current = providers.find((p) => p.provider === form.getValues('provider'))
    if (current && !current.configured) {
      const alt = providers.find((p) => p.configured)
      if (alt) form.setValue('provider', alt.provider)
    }
  }, [providers, form])

  const run = useMutation({
    mutationFn: async (v: { file: File; values: OptionsFormValues }) => {
      const opts = toSearchOptions(v.values)
      setIdentified(null)
      setStage('reading')
      const res = await api.identify(v.file, opts.provider)
      const ident = res.identity
      setIdentified({
        name: identityLabel(ident),
        chips: [
          ident.strength.value,
          ident.dosage_form.value,
          ident.pack_configuration.value ??
            (ident.pack_quantity.value ? `${ident.pack_quantity.value} per pack` : null),
          ident.manufacturer.value,
        ].filter((c): c is string => Boolean(c)),
        seconds: res.duration_ms / 1000,
      })
      // Always search with what was readable. Unclear details are shown on the results, not asked up front.
      // Price limits are applied as result filters.
      setStage('searching')
      const created = await api.createSearch(normalizeForSubmit(ident), { ...opts, min_price: null, max_price: null })
      return created.id
    },
    onSuccess: (id) => void navigate(`/searches/${id}`),
    onSettled: () => setStage('idle'),
  })

  const onSubmit = form.handleSubmit((values) => {
    if (!file) {
      setNoFile(true)
      return
    }
    setNoFile(false)
    const opts = toSearchOptions(values)
    setOptions({ ...opts, min_price: null, max_price: null })
    setPriceFilter({ min: values.minPrice, max: values.maxPrice })
    run.mutate({ file, values })
  })

  const err =
    run.error instanceof ApiError ? run.error : run.error ? new ApiError(0, 'unknown', 'Something went wrong.') : null
  const missing = err?.code === 'provider_not_configured' ? (err.details.missing as string[] | undefined) : undefined
  const busy = stage !== 'idle'

  return (
    <div className="flex flex-col gap-12">
      <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-brand-950 via-brand-900 to-brand-700 text-white shadow-xl">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(rgba(255,255,255,0.09)_1px,transparent_1px)] [background-size:22px_22px]"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -right-24 -top-24 size-96 rounded-full bg-accent/20 blur-3xl"
        />
        <div className="relative grid items-center gap-10 p-6 sm:p-10 lg:grid-cols-[1.05fr_1fr] lg:p-14">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-medium text-accent">
              <Sparkles className="size-3.5" aria-hidden /> AI-assisted pharmacy procurement
            </span>
            <h1 className="mt-5 text-4xl font-semibold leading-[1.1] tracking-tight sm:text-5xl">
              Find the best <span className="text-accent">verified price</span> for any pharmacy product
            </h1>
            <p className="mt-4 max-w-xl text-base text-white/75">
              Upload a photo of the pack. That is all you need: we identify the product, search suppliers and show you
              every step. Anything you add under optional settings is used.
            </p>
            <ul className="mt-8 flex flex-col gap-4">
              {FEATURES.map(({ icon: Icon, title, text }) => (
                <li key={title} className="flex gap-3">
                  <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-white/10 ring-1 ring-white/15">
                    <Icon className="size-[18px] text-accent" aria-hidden />
                  </span>
                  <span>
                    <span className="block text-sm font-semibold">{title}</span>
                    <span className="block text-sm text-white/65">{text}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <form
            onSubmit={onSubmit}
            noValidate
            aria-label="Find offers"
            className="flex flex-col gap-4 rounded-xl bg-surface p-5 text-ink shadow-2xl ring-1 ring-black/5 sm:p-6"
          >
            <div>
              <h2 className="text-[15px] font-semibold">{busy ? 'Working on your photo' : 'Product photo'}</h2>
              <p className="text-sm text-ink-soft">
                {busy ? 'Live status of the steps below.' : 'A clear photo of the front of the pack works best.'}
              </p>
            </div>

            {busy && file ? (
              <RunProgress
                file={file}
                stage={stage === 'searching' ? 'searching' : 'reading'}
                providerName={PROVIDER_NAME[provider]}
                identified={identified}
              />
            ) : (
              <>
                <ImageDropzone
                  file={file}
                  onFile={(f) => {
                    setNoFile(false)
                    setFile(f)
                  }}
                  allowedMime={config.data?.limits.allowed_mime}
                  maxMb={config.data?.limits.max_upload_mb}
                  disabled={run.isPending}
                />
                {noFile && (
                  <p role="alert" className="text-sm text-danger-fg">
                    Choose a product image first.
                  </p>
                )}
              </>
            )}

            <details className="group rounded-lg border border-line">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3">
                <span>
                  <span className="block text-sm font-semibold">Optional settings</span>
                  <span className="block text-xs text-ink-soft">
                    Quantity, price range, retail or business, market, AI provider
                  </span>
                </span>
                <ChevronDown
                  className="size-4 shrink-0 text-muted transition-transform group-open:rotate-180"
                  aria-hidden
                />
              </summary>
              <div className="border-t border-line p-4">
                <SearchOptionsFields
                  control={form.control}
                  register={form.register}
                  errors={form.formState.errors}
                  capabilities={config.data?.providers}
                  disabled={run.isPending}
                />
              </div>
            </details>

            {err && (
              <Alert
                tone="danger"
                title={missing ? `${PROVIDER_NAME[provider]} is not configured` : 'Could not complete the request'}
              >
                {err.message}
                {missing && (
                  <span> Add {missing.map((m) => m).join(' and ')} to backend/.env and restart the server.</span>
                )}
              </Alert>
            )}

            <Button type="submit" size="lg" loading={run.isPending} className="w-full">
              <Search className="size-4" aria-hidden />
              {stage === 'reading'
                ? `Reading image with ${PROVIDER_NAME[provider]}…`
                : stage === 'searching'
                  ? 'Starting supplier search…'
                  : 'Find offers'}
            </Button>
          </form>
        </div>
      </section>

      <section aria-labelledby="how-heading">
        <h2 id="how-heading" className="text-2xl font-semibold tracking-tight">
          How it works
        </h2>
        <ol className="mt-5 grid gap-4 md:grid-cols-3">
          {STEPS.map(({ icon: Icon, title, text }, i) => (
            <li
              key={title}
              className="relative rounded-xl border border-line bg-surface p-5 shadow-[0_1px_2px_rgba(14,35,48,0.05)]"
            >
              <span className="absolute right-4 top-3 text-5xl font-semibold text-brand-100/80" aria-hidden>
                {i + 1}
              </span>
              <span className="grid size-10 place-items-center rounded-lg bg-brand-50 text-brand-700">
                <Icon className="size-5" aria-hidden />
              </span>
              <h3 className="mt-4 text-[15px] font-semibold">{title}</h3>
              <p className="mt-1 text-sm text-ink-soft">{text}</p>
            </li>
          ))}
        </ol>
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <RecentSearches />
        <section className="rounded-xl border border-line bg-surface p-5 shadow-[0_1px_2px_rgba(14,35,48,0.05)]">
          <h2 className="text-[15px] font-semibold">Trust and safety</h2>
          <ul className="mt-3 flex flex-col gap-3 text-sm text-ink-soft">
            <li className="flex gap-2.5">
              <ShieldCheck className="mt-0.5 size-4 shrink-0 text-brand-700" aria-hidden />
              Only direct supplier evidence marks an offer source-verified.
            </li>
            <li className="flex gap-2.5">
              <FileSearch className="mt-0.5 size-4 shrink-0 text-brand-700" aria-hidden />
              Different strengths, forms or brands are never treated as the same product.
            </li>
            <li className="flex gap-2.5">
              <ExternalLink className="mt-0.5 size-4 shrink-0 text-brand-700" aria-hidden />
              You buy from the supplier directly. No payments or ordering here.
            </li>
          </ul>
        </section>
      </div>
    </div>
  )
}
