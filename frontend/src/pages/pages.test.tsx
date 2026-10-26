import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/lib/api'
import type { AppConfig } from '@/lib/types'
import { DEFAULT_OPTIONS, useDiscovery } from '@/store/discovery'
import { makeDetail, makeIdentity, makeOffer, makeProgress } from '@/test/fixtures'
import { DiscoverPage } from './DiscoverPage'
import { SearchPage } from './SearchPage'

vi.mock('@/lib/api', async (orig) => {
  const actual = await orig<typeof import('@/lib/api')>()
  return {
    ...actual,
    api: {
      config: vi.fn(),
      identify: vi.fn(),
      createSearch: vi.fn(),
      getSearch: vi.fn(),
      listSearches: vi.fn(),
      getOffer: vi.fn(),
      deleteSearch: vi.fn(),
    },
  }
})
import { api } from '@/lib/api'

const CONFIG: AppConfig = {
  app_name: 'PharmaSource',
  providers: [
    { provider: 'openai', configured: true, missing: [] },
    { provider: 'gemini', configured: false, missing: ['GEMINI_API_KEY', 'GEMINI_VISION_MODEL'] },
  ],
  markets: ['india', 'global'],
  modes: ['retail', 'business'],
  demo_mode: false,
  limits: { max_upload_mb: 8, allowed_mime: ['image/jpeg', 'image/png', 'image/webp'], max_quantity: 100000 },
  sources: [],
  currency: { provider: 'none', india: 'INR', global: 'USD' },
}

function renderAt(path: string, ui: React.ReactNode, routePath = '*') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={routePath} element={ui} />
          {routePath !== '/searches/:id' && <Route path="/searches/:id" element={<div>results page</div>} />}
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const png = () => new File([new Uint8Array(500)], 'pack.png', { type: 'image/png' })

beforeEach(() => {
  vi.resetAllMocks()
  useDiscovery.setState({
    file: null,
    options: DEFAULT_OPTIONS,
    priceFilter: { min: '', max: '' },
  })
  vi.mocked(api.config).mockResolvedValue(CONFIG)
  vi.mocked(api.listSearches).mockResolvedValue({ items: [], total: 0, limit: 5, offset: 0 })
})

describe('DiscoverPage', () => {
  it('shows provider status and defaults to retail/India/OpenAI', async () => {
    renderAt('/', <DiscoverPage />)
    expect(await screen.findByText(/Set/)).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /OpenAI/ })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Retail' })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'India' })).toBeChecked()
    expect(screen.getByText('GEMINI_API_KEY, GEMINI_VISION_MODEL')).toBeInTheDocument()
  })

  it('requires an image before identifying', async () => {
    renderAt('/', <DiscoverPage />)
    await userEvent.click(screen.getByRole('button', { name: /Find offers/ }))
    expect(await screen.findByText('Choose a product image first.')).toBeInTheDocument()
    expect(api.identify).not.toHaveBeenCalled()
  })

  it('rejects unsupported files with a clear message', async () => {
    renderAt('/', <DiscoverPage />)
    const input = document.querySelector('input[type=file]') as HTMLInputElement
    await userEvent.upload(input, new File(['x'], 'doc.pdf', { type: 'application/pdf' }), { applyAccept: false })
    expect(await screen.findByText(/Unsupported file type/)).toBeInTheDocument()
    expect(screen.queryByAltText('Selected product')).not.toBeInTheDocument()
  })

  it('previews a valid image and lets the user remove it', async () => {
    renderAt('/', <DiscoverPage />)
    const input = document.querySelector('input[type=file]') as HTMLInputElement
    await userEvent.upload(input, png())
    expect(await screen.findByAltText('Selected product')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Remove/ }))
    expect(screen.queryByAltText('Selected product')).not.toBeInTheDocument()
  })

  const NO_AMBIGUITY = {
    needs_clarification: false,
    missing_essentials: [],
    unconfirmed_essentials: [],
    contradictions: [],
    messages: [],
  }

  it('goes straight to results when nothing is ambiguous, using the selected provider and optional settings', async () => {
    vi.mocked(api.identify).mockResolvedValue({
      identity: makeIdentity(),
      ambiguity: NO_AMBIGUITY,
      provider: 'gemini',
      model: 'm',
      duration_ms: 900,
      state: 'IDENTITY_READY',
    })
    vi.mocked(api.createSearch).mockResolvedValue({ id: 'new1', state: 'REQUEST_RECEIVED' })
    renderAt('/', <DiscoverPage />)
    await userEvent.upload(document.querySelector('input[type=file]') as HTMLInputElement, png())
    await userEvent.click(screen.getByRole('radio', { name: /Google Gemini/ }))
    await userEvent.click(screen.getByRole('radio', { name: 'Business' }))
    await userEvent.click(screen.getByRole('radio', { name: 'Global' }))
    expect(screen.getByText(/may not be legal to buy or import into India/)).toBeInTheDocument()
    const qty = screen.getByLabelText(/Packs required/)
    await userEvent.clear(qty)
    await userEvent.type(qty, '5')
    await userEvent.type(screen.getByLabelText('Maximum price'), '100')
    await userEvent.click(screen.getByRole('button', { name: /Find offers/ }))
    await waitFor(() => expect(api.identify).toHaveBeenCalledWith(expect.any(File), 'gemini'))
    expect(await screen.findByText('results page')).toBeInTheDocument()
    expect(api.createSearch).toHaveBeenCalledWith(
      expect.objectContaining({ category: 'medicine' }),
      expect.objectContaining({
        provider: 'gemini',
        mode: 'business',
        market: 'global',
        quantity: 5,
        min_price: null,
        max_price: null,
      }),
    )
    // price limits become result filters instead of a pre-search requirement
    expect(useDiscovery.getState().priceFilter).toEqual({ min: '', max: '100' })
  })

  it('needs only the image: defaults are used when no optional setting is touched', async () => {
    vi.mocked(api.identify).mockResolvedValue({
      identity: makeIdentity(),
      ambiguity: NO_AMBIGUITY,
      provider: 'openai',
      model: 'm',
      duration_ms: 1,
      state: 'IDENTITY_READY',
    })
    vi.mocked(api.createSearch).mockResolvedValue({ id: 'new2', state: 'REQUEST_RECEIVED' })
    renderAt('/', <DiscoverPage />)
    await userEvent.upload(document.querySelector('input[type=file]') as HTMLInputElement, png())
    await userEvent.click(screen.getByRole('button', { name: /Find offers/ }))
    expect(await screen.findByText('results page')).toBeInTheDocument()
    expect(api.createSearch).toHaveBeenCalledWith(expect.anything(), {
      ...DEFAULT_OPTIONS,
      min_price: null,
      max_price: null,
    })
  })

  it('still searches when the AI is unsure of details: no review step is ever shown', async () => {
    vi.mocked(api.identify).mockResolvedValue({
      identity: makeIdentity({ strength: { value: '500 mg', status: 'inferred', evidence: 'guess' } }),
      ambiguity: {
        ...NO_AMBIGUITY,
        needs_clarification: true,
        unconfirmed_essentials: ['strength'],
        messages: ['inferred'],
      },
      provider: 'openai',
      model: 'm',
      duration_ms: 1,
      state: 'NEEDS_CLARIFICATION',
    })
    vi.mocked(api.createSearch).mockResolvedValue({ id: 'u1', state: 'REQUEST_RECEIVED' })
    renderAt('/', <DiscoverPage />)
    await userEvent.upload(document.querySelector('input[type=file]') as HTMLInputElement, png())
    await userEvent.click(screen.getByRole('button', { name: /Find offers/ }))
    expect(await screen.findByText('results page')).toBeInTheDocument()
    expect(api.createSearch).toHaveBeenCalledTimes(1)
  })

  it('validates quantity and the price range', async () => {
    renderAt('/', <DiscoverPage />)
    await userEvent.upload(document.querySelector('input[type=file]') as HTMLInputElement, png())
    const qty = screen.getByLabelText(/Quantity/)
    await userEvent.clear(qty)
    await userEvent.type(qty, '0')
    await userEvent.type(screen.getByLabelText('Minimum price'), '50')
    await userEvent.type(screen.getByLabelText('Maximum price'), '10')
    await userEvent.click(screen.getByRole('button', { name: /Find offers/ }))
    expect(await screen.findByText('Quantity must be between 1 and 100,000')).toBeInTheDocument()
    expect(screen.getByText('Maximum must be at least the minimum')).toBeInTheDocument()
    expect(api.identify).not.toHaveBeenCalled()
  })

  it('explains which configuration is missing when the provider is not configured', async () => {
    vi.mocked(api.identify).mockRejectedValue(
      new ApiError(
        503,
        'provider_not_configured',
        'gemini is not configured. Set GEMINI_API_KEY, GEMINI_VISION_MODEL in the backend environment.',
        {
          missing: ['GEMINI_API_KEY', 'GEMINI_VISION_MODEL'],
        },
      ),
    )
    renderAt('/', <DiscoverPage />)
    await userEvent.upload(document.querySelector('input[type=file]') as HTMLInputElement, png())
    await userEvent.click(screen.getByRole('radio', { name: /Google Gemini/ }))
    await userEvent.click(screen.getByRole('button', { name: /Find offers/ }))
    expect(await screen.findByText('Google Gemini is not configured')).toBeInTheDocument()
    expect(screen.getByText(/Add GEMINI_API_KEY and GEMINI_VISION_MODEL to backend\/\.env/)).toBeInTheDocument()
  })

  it('shows recent searches when available', async () => {
    vi.mocked(api.listSearches).mockResolvedValue({
      items: [
        {
          id: 's1',
          created_at: new Date().toISOString(),
          product_label: 'Paracetamol',
          options: DEFAULT_OPTIONS,
          state: 'RESULTS_READY',
          is_terminal: true,
          offers_discovered: 3,
        },
      ],
      total: 1,
      limit: 5,
      offset: 0,
    })
    renderAt('/', <DiscoverPage />)
    expect(await screen.findByRole('link', { name: /Paracetamol/ })).toHaveAttribute('href', '/searches/s1')
  })
})

describe('SearchPage states', () => {
  const show = (detail: ReturnType<typeof makeDetail>) => {
    vi.mocked(api.getSearch).mockResolvedValue(detail)
    return renderAt('/searches/s1', <SearchPage />, '/searches/:id')
  }

  it('shows a loading state, then the results', async () => {
    show(makeDetail({ offers: [makeOffer({ supplier_name: 'Cheap Chemist' })] }))
    expect(screen.getByText('Loading search…')).toBeInTheDocument()
    expect((await screen.findAllByText('Cheap Chemist')).length).toBeGreaterThan(0)
    expect(screen.getByText('Results ready')).toBeInTheDocument()
  })

  it('shows real progress counts and source failures for partial results', async () => {
    show(
      makeDetail({
        is_terminal: true,
        progress: makeProgress({
          state: 'PARTIAL_RESULTS',
          message: '1 of 2 sources failed; results may be incomplete.',
          offers_discovered: 4,
          offers_verified: 2,
          sources: [
            {
              connector_id: 'a',
              name: 'Source A',
              kind: 'catalogue_api',
              is_demo: false,
              status: 'ok',
              offers: 4,
              attempts: 1,
              duration_ms: 20,
              error: null,
            },
            {
              connector_id: 'b',
              name: 'Source B',
              kind: 'catalogue_api',
              is_demo: false,
              status: 'timeout',
              offers: 0,
              attempts: 2,
              duration_ms: 900,
              error: 'No response within 20s.',
            },
          ],
          unresolved: ['No verifiable price could be read from shop.example.'],
        }),
        offers: [makeOffer()],
      }),
    )
    expect(await screen.findByText('Results may be incomplete')).toBeInTheDocument()
    expect(screen.getByText('Timed out')).toBeInTheDocument()
    expect(screen.getByText('No response within 20s.')).toBeInTheDocument()
    expect(screen.getByText('No verifiable price could be read from shop.example.')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
  })

  it('shows a running search as in progress without claiming completion', async () => {
    show(
      makeDetail({
        is_terminal: false,
        progress: makeProgress({
          state: 'SEARCHING_SUPPLIERS',
          message: 'Searching supplier sources.',
          finished: false,
          offers_discovered: 0,
          offers_verified: 0,
          offers_unverified: 0,
        }),
      }),
    )
    expect(await screen.findByText('Searching supplier sources.')).toBeInTheDocument()
    expect(screen.queryByText('Results ready')).not.toBeInTheDocument()
    expect(screen.getByText(/Refreshing every 2 s|Live updates/)).toBeInTheDocument()
  })

  it('explains no-match, unavailable-source and failed states', async () => {
    const { unmount } = show(
      makeDetail({
        progress: makeProgress({ state: 'NO_MATCHES', message: 'No offers matched the identified product.' }),
      }),
    )
    expect(await screen.findByText('No matching offers found')).toBeInTheDocument()
    unmount()
    const r2 = show(
      makeDetail({
        progress: makeProgress({ state: 'SOURCE_UNAVAILABLE', message: 'No supplier source returned results.' }),
      }),
    )
    expect(await screen.findByText('No supplier source could be searched')).toBeInTheDocument()
    r2.unmount()
    show(
      makeDetail({ progress: makeProgress({ state: 'FAILED', message: 'x', error: 'Search timed out after 120s.' }) }),
    )
    expect(await screen.findByText('The search failed')).toBeInTheDocument()
    expect(screen.getByText('Search timed out after 120s.')).toBeInTheDocument()
  })

  it('explains when nothing could be identified and offers the details panel open', async () => {
    show(
      makeDetail({
        progress: makeProgress({
          state: 'NEEDS_CLARIFICATION',
          message: 'The product could not be identified from the image.',
        }),
      }),
    )
    expect(await screen.findByText('We could not identify the product')).toBeInTheDocument()
    expect(screen.getByText('What we identified').closest('details')).toHaveAttribute('open')
    expect(screen.queryByRole('button', { name: /Update results/ })).not.toBeInTheDocument()
  })

  it('flags demonstration data prominently', async () => {
    show(
      makeDetail({
        is_demo_data_present: true,
        offers: [makeOffer({ is_demo: true, tier: 'UNVERIFIED', supplier_name: 'DEMO Alpha (fictional)' })],
      }),
    )
    expect(await screen.findByText('Demonstration data present')).toBeInTheDocument()
  })

  it('handles a missing search and server errors', { timeout: 15000 }, async () => {
    vi.mocked(api.getSearch).mockRejectedValue(new ApiError(404, 'not_found', 'Search not found.'))
    const { unmount } = renderAt('/searches/zzz', <SearchPage />, '/searches/:id')
    expect(await screen.findByText('Search not found')).toBeInTheDocument()
    unmount()
    vi.mocked(api.getSearch).mockRejectedValue(new ApiError(500, 'internal_error', 'Unexpected server error.'))
    renderAt('/searches/zzz', <SearchPage />, '/searches/:id')
    expect(await screen.findByText('Could not load this search', {}, { timeout: 6000 })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })
})

describe('SearchPage live updates (SSE)', () => {
  class FakeEventSource {
    static instances: FakeEventSource[] = []
    listeners = new Map<string, ((e: MessageEvent) => void)[]>()
    onerror: (() => void) | null = null
    closed = false
    url: string
    constructor(url: string) {
      this.url = url
      FakeEventSource.instances.push(this)
    }
    addEventListener(type: string, fn: (e: MessageEvent) => void) {
      this.listeners.set(type, [...(this.listeners.get(type) ?? []), fn])
    }
    emit(type: string, data?: unknown) {
      for (const fn of this.listeners.get(type) ?? []) fn({ data: JSON.stringify(data) } as MessageEvent)
    }
    close() {
      this.closed = true
    }
  }

  it('streams partial results into the table and closes when done', async () => {
    FakeEventSource.instances = []
    vi.stubGlobal('EventSource', FakeEventSource)
    const running = makeDetail({
      is_terminal: false,
      progress: makeProgress({
        state: 'SEARCHING_SUPPLIERS',
        message: 'Searching supplier sources.',
        finished: false,
        offers_discovered: 0,
        offers_verified: 0,
        offers_unverified: 0,
      }),
    })
    vi.mocked(api.getSearch).mockResolvedValue(running)
    renderAt('/searches/s1', <SearchPage />, '/searches/:id')
    expect(await screen.findByText('Searching supplier sources.')).toBeInTheDocument()
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1))
    const es = FakeEventSource.instances[0]!
    expect(es.url).toBe('/api/searches/s1/events')

    act(() => es.emit('open'))
    expect(await screen.findByText('Live updates')).toBeInTheDocument()

    const partial = makeDetail({
      is_terminal: false,
      progress: makeProgress({
        state: 'PARTIAL_RESULTS',
        message: '1 candidate offers from 1 of 2 sources so far.',
        finished: false,
        offers_discovered: 1,
      }),
      offers: [makeOffer({ supplier_name: 'Early Bird Pharmacy' })],
    })
    act(() => es.emit('update', partial))
    expect((await screen.findAllByText('Early Bird Pharmacy')).length).toBeGreaterThan(0)
    expect(screen.getByText('1 candidate offers from 1 of 2 sources so far.')).toBeInTheDocument()

    vi.mocked(api.getSearch).mockResolvedValue(makeDetail({ offers: partial.offers }))
    act(() => es.emit('done', { state: 'RESULTS_READY' }))
    expect(await screen.findByText('Results ready')).toBeInTheDocument()
    expect(es.closed).toBe(true)
    vi.unstubAllGlobals()
  })
})

describe('Refine settings on results', () => {
  it('re-runs the same product with changed settings and opens the new search', async () => {
    vi.mocked(api.getSearch).mockResolvedValue(makeDetail({ offers: [makeOffer()] }))
    vi.mocked(api.createSearch).mockResolvedValue({ id: 'rerun', state: 'REQUEST_RECEIVED' })
    renderAt('/searches/s1', <SearchPage />, '/searches/:id')
    const update = await screen.findByRole('button', { name: /Update results/ })
    expect(update).toBeDisabled()
    const qty = screen.getByLabelText('Quantity (packs)')
    await userEvent.clear(qty)
    await userEvent.type(qty, '12')
    await userEvent.click(screen.getByRole('radio', { name: 'Business' }))
    expect(update).toBeEnabled()
    await userEvent.click(update)
    await waitFor(() => expect(api.createSearch).toHaveBeenCalled())
    const [ident, opts] = vi.mocked(api.createSearch).mock.calls[0]!
    expect(ident.category).toBe('medicine')
    expect(opts).toMatchObject({ quantity: 12, mode: 'business', market: 'india' })
  })

  it('rejects an invalid quantity', async () => {
    vi.mocked(api.getSearch).mockResolvedValue(makeDetail({ offers: [makeOffer()] }))
    renderAt('/searches/s1', <SearchPage />, '/searches/:id')
    const qty = await screen.findByLabelText('Quantity (packs)')
    await userEvent.clear(qty)
    await userEvent.type(qty, '0')
    expect(await screen.findByText(/whole number from 1 to 100,000/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Update results/ })).toBeDisabled()
  })
})

describe('Identified details panel (optional)', () => {
  it('flags unclear details but never blocks: results are shown alongside', async () => {
    vi.mocked(api.getSearch).mockResolvedValue(
      makeDetail({
        progress: makeProgress({
          warnings: ['Missing essential details: pack quantity.'],
        }),
        offers: [makeOffer({ supplier_name: 'Visible Chemist' })],
      }),
    )
    renderAt('/searches/s1', <SearchPage />, '/searches/:id')
    expect((await screen.findAllByText('Visible Chemist')).length).toBeGreaterThan(0)
    expect(screen.getByText('Unclear on the pack')).toBeInTheDocument()
    expect(screen.getByText('Missing essential details: pack quantity.')).toBeInTheDocument()
    expect(screen.getByText(/cannot be marked fully source-verified/)).toBeInTheDocument()
  })

  it('lets the user add a missing detail and search again with it marked as theirs', async () => {
    vi.mocked(api.getSearch).mockResolvedValue(
      makeDetail({
        identity: makeIdentity({ pack_quantity: { value: null, status: 'unknown', evidence: null } }),
        progress: makeProgress({ warnings: ['Missing essential details: pack quantity.'] }),
        offers: [makeOffer()],
      }),
    )
    vi.mocked(api.createSearch).mockResolvedValue({ id: 'again', state: 'REQUEST_RECEIVED' })
    renderAt('/searches/s1', <SearchPage />, '/searches/:id')
    const again = await screen.findByRole('button', { name: /Search again with these details/ })
    expect(again).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Units per pack'), '10')
    expect(again).toBeEnabled()
    await userEvent.click(again)
    await waitFor(() => expect(api.createSearch).toHaveBeenCalled())
    expect(vi.mocked(api.createSearch).mock.calls[0]![0].pack_quantity).toEqual({
      value: '10',
      status: 'confirmed',
      evidence: 'Provided by user',
    })
  })
})

describe('Agent activity feed', () => {
  const at = (sec: number) => new Date(Date.UTC(2026, 9, 24, 12, 0, 0, sec * 1000)).toISOString()

  it('shows the real steps, in order, with the current stage highlighted while running', async () => {
    vi.mocked(api.getSearch).mockResolvedValue(
      makeDetail({
        is_terminal: false,
        progress: makeProgress({
          state: 'SEARCHING_SUPPLIERS',
          message: 'Searching supplier sources.',
          finished: false,
          activity: [
            { at: at(0), phase: 'plan', level: 'info', message: 'Searching for Paracetamol' },
            { at: at(0.4), phase: 'plan', level: 'warn', message: 'Skipped Tavily: Set TAVILY_API_KEY' },
            { at: at(1), phase: 'search', level: 'success', message: 'Demo source: 5 candidate(s) in 0.2 s' },
            { at: at(2.5), phase: 'read', level: 'error', message: 'shop.example: no readable price on the page' },
          ],
        }),
      }),
    )
    renderAt('/searches/s1', <SearchPage />, '/searches/:id')
    const log = await screen.findByRole('list', { name: 'Activity log' })
    const items = within(log).getAllByRole('listitem')
    expect(items).toHaveLength(4)
    expect(items[0]).toHaveTextContent('Searching for Paracetamol')
    expect(items[0]).toHaveTextContent('+0.0s')
    expect(items[3]).toHaveTextContent('+2.5s')
    expect(items[3]).toHaveTextContent('no readable price')
    const stages = within(screen.getByRole('list', { name: 'Pipeline stages' })).getAllByRole('listitem')
    expect(stages.map((x) => x.getAttribute('data-state'))).toEqual(['done', 'done', 'active', 'pending', 'pending'])
  })

  it('keeps the full log available, collapsed, after the search finishes', async () => {
    vi.mocked(api.getSearch).mockResolvedValue(
      makeDetail({
        offers: [makeOffer()],
        progress: makeProgress({
          activity: [
            { at: at(0), phase: 'plan', level: 'info', message: 'Searching for Paracetamol' },
            { at: at(3), phase: 'done', level: 'success', message: '1 offers found. (3.0 s)' },
          ],
        }),
      }),
    )
    renderAt('/searches/s1', <SearchPage />, '/searches/:id')
    expect(await screen.findByText('2 steps in 3.0 s')).toBeInTheDocument()
    expect(screen.getByLabelText('Agent activity')).not.toHaveAttribute('open')
  })
})
