import { History, Pill, ScanSearch } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { cn } from '@/lib/cn'
import { useConfig } from '@/hooks/queries'
import { Alert } from '@/components/ui/feedback'

const nav = [
  { to: '/', label: 'Discover', icon: ScanSearch, end: true },
  { to: '/history', label: 'History', icon: History, end: false },
]

export function AppShell() {
  const config = useConfig()
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <header className="bg-gradient-to-r from-brand-950 to-brand-900 text-white shadow-sm">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
          <NavLink to="/" className="flex items-center gap-2.5 text-[15px] font-semibold tracking-tight">
            <span className="grid size-8 place-items-center rounded-lg bg-white/10 ring-1 ring-white/20">
              <Pill className="size-4" aria-hidden />
            </span>
            {config.data?.app_name ?? 'PharmaSource'}
            <span className="hidden rounded bg-white/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-white/70 sm:inline">
              Procurement
            </span>
          </NavLink>
          <nav aria-label="Primary" className="flex gap-1">
            {nav.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors',
                    isActive
                      ? 'bg-white/15 font-medium text-white'
                      : 'text-white/70 hover:bg-white/10 hover:text-white',
                  )
                }
              >
                <Icon className="size-4" aria-hidden />
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      {config.data?.demo_mode && (
        <div className="border-b border-line bg-warn-bg">
          <p className="mx-auto max-w-7xl px-4 py-1.5 text-xs font-medium text-warn-fg">
            Demo mode is on: fictional demonstration offers may appear. They are not real prices and are never treated
            as verified.
          </p>
        </div>
      )}
      <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:py-10">
        {config.isError && (
          <Alert tone="danger" title="Cannot reach the server" className="mb-6">
            Start the backend (see README) and reload this page.
          </Alert>
        )}
        <Outlet />
      </main>
      <footer className="border-t border-line">
        <p className="mx-auto max-w-7xl px-4 py-4 text-xs text-muted">
          PharmaSource compares supplier listings for discovery. It does not provide medical advice, dispense medicines
          or process payments. Prescription and import rules still apply; always confirm details with the supplier.
        </p>
      </footer>
    </div>
  )
}
