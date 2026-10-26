import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { EmptyState, Spinner } from '@/components/ui/feedback'
import { DiscoverPage } from '@/pages/DiscoverPage'

const SearchPage = lazy(() => import('@/pages/SearchPage').then((m) => ({ default: m.SearchPage })))
const HistoryPage = lazy(() => import('@/pages/HistoryPage').then((m) => ({ default: m.HistoryPage })))

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
})

function NotFound() {
  return (
    <EmptyState
      title="Page not found"
      action={
        <Link to="/" className="text-sm font-medium text-brand-700 underline">
          Go to Discover
        </Link>
      }
    />
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Suspense
          fallback={
            <div className="p-8 text-center">
              <Spinner />
            </div>
          }
        >
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<DiscoverPage />} />
              <Route path="searches/:id" element={<SearchPage />} />
              <Route path="history" element={<HistoryPage />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
