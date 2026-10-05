import { BarChart3, LogOut } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'

import { Button } from '@/components/ui/Button'
import { useCurrentUser, useLogout } from '@/lib/hooks/use-auth'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  {
    to: '/analytics',
    label: 'Analytics',
    icon: BarChart3,
    roles: ['admin', 'finance_manager', 'auditor'],
  },
]

export function AppShell() {
  const { data: user } = useCurrentUser()
  const logout = useLogout()
  const items = NAV_ITEMS.filter((item) => user && item.roles.includes(user.role))

  return (
    <div className="flex min-h-svh bg-slate-50">
      <aside className="hidden w-56 shrink-0 flex-col border-r border-slate-200 bg-white p-4 md:flex">
        <p className="mb-6 font-serif text-lg font-semibold text-brand-navy">Veridian Payables</p>
        <nav aria-label="Application">
          <ul className="flex flex-col gap-1">
            {items.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium',
                      isActive ? 'bg-brand-navy text-white' : 'text-slate-600 hover:bg-slate-100',
                    )
                  }
                >
                  <item.icon className="size-4" aria-hidden="true" />
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
          <p className="text-sm text-slate-500">
            {user ? (
              <>
                Signed in as <strong className="text-slate-700">{user.full_name}</strong>
              </>
            ) : null}
          </p>
          <Button
            variant="ghost"
            size="sm"
            onClick={async () => {
              await logout.mutateAsync()
              window.location.assign('/')
            }}
          >
            <LogOut className="size-4" aria-hidden="true" />
            Log out
          </Button>
        </header>
        <main id="main-content" className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
