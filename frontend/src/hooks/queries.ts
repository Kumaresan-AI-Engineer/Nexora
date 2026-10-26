import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { SearchDetail } from '@/lib/types'

export function useConfig() {
  return useQuery({ queryKey: ['config'], queryFn: api.config, staleTime: 60_000 })
}

export function useSearches(limit = 20) {
  return useQuery({ queryKey: ['searches', limit], queryFn: () => api.listSearches(limit) })
}

export function useDeleteSearch() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.deleteSearch,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['searches'] }),
  })
}

/**
 * Loads a search and keeps it live. Uses Server-Sent Events when available and falls back to
 * polling, so progress shown is always the persisted server state, never a client-side guess.
 */
export function useSearchLive(id: string) {
  const qc = useQueryClient()
  const [streaming, setStreaming] = useState(false)
  const key = ['search', id]

  const query = useQuery({
    queryKey: key,
    queryFn: () => api.getSearch(id),
    retry: (count, err) => (err as { status?: number }).status !== 404 && count < 2,
    refetchInterval: (q) => (q.state.data?.is_terminal || streaming ? false : 2000),
  })

  const terminal = query.data?.is_terminal ?? false
  const started = useRef(false)

  useEffect(() => {
    if (terminal || query.isError || typeof EventSource === 'undefined') return
    const es = new EventSource(`/api/searches/${id}/events`, { withCredentials: true })
    started.current = true
    es.addEventListener('open', () => setStreaming(true))
    es.addEventListener('update', (e) => {
      qc.setQueryData<SearchDetail>(['search', id], JSON.parse((e as MessageEvent).data) as SearchDetail)
    })
    es.addEventListener('done', () => {
      es.close()
      setStreaming(false)
      void qc.invalidateQueries({ queryKey: ['search', id] })
      void qc.invalidateQueries({ queryKey: ['searches'] })
    })
    es.onerror = () => {
      es.close()
      setStreaming(false) // polling takes over
    }
    return () => {
      es.close()
      setStreaming(false)
    }
  }, [id, terminal, query.isError, qc])

  return { ...query, streaming }
}
