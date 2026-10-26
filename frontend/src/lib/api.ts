import type {
  AppConfig,
  IdentifyResponse,
  Offer,
  ProductIdentity,
  ProviderName,
  SearchDetail,
  SearchOptions,
  SearchPage,
} from './types'

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly details: Record<string, unknown>

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api${path}`, { credentials: 'include', ...init })
  } catch {
    throw new ApiError(0, 'network_error', 'Could not reach the PharmaSource server. Is the backend running?')
  }
  if (res.status === 204) return undefined as T
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    // non-JSON body
  }
  if (!res.ok) {
    const err = (body as { error?: { code?: string; message?: string; details?: Record<string, unknown> } } | null)
      ?.error
    throw new ApiError(
      res.status,
      err?.code ?? 'http_error',
      err?.message ?? `Request failed (HTTP ${res.status}).`,
      err?.details,
    )
  }
  return body as T
}

const json = (data: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data),
})

export const api = {
  config: () => request<AppConfig>('/config'),
  identify(image: File, provider: ProviderName) {
    const form = new FormData()
    form.append('image', image)
    form.append('provider', provider)
    return request<IdentifyResponse>('/identify', { method: 'POST', body: form })
  },
  createSearch: (identity: ProductIdentity, options: SearchOptions) =>
    request<{ id: string; state: string }>('/searches', json({ identity, options })),
  getSearch: (id: string) => request<SearchDetail>(`/searches/${id}`),
  listSearches: (limit = 20, offset = 0) => request<SearchPage>(`/searches?limit=${limit}&offset=${offset}`),
  getOffer: (searchId: string, offerId: string) => request<Offer>(`/searches/${searchId}/offers/${offerId}`),
  deleteSearch: (id: string) => request<void>(`/searches/${id}`, { method: 'DELETE' }),
}
