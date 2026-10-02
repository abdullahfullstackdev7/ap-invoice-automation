import { Loader2 } from 'lucide-react'
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/Button'
import { useCurrentUser, useLogout } from '@/lib/hooks/use-auth'

/** Placeholder landing page after login. The real authenticated shell
 * (sidebar, invoices, exceptions, approvals, ...) ships in Phase 11; this
 * page exists so Phase 10's login flow has somewhere real to land and
 * proves cookie auth end to end via GET /auth/me. */
export function AppStubPage() {
  const navigate = useNavigate()
  const { data: user, isLoading, isError } = useCurrentUser()
  const logout = useLogout()

  useEffect(() => {
    if (isError) navigate('/login', { replace: true })
  }, [isError, navigate])

  if (isLoading) {
    return (
      <main className="flex min-h-svh items-center justify-center">
        <Loader2 className="size-6 animate-spin text-brand-blue" aria-label="Loading" />
      </main>
    )
  }

  if (!user) return null

  return (
    <main className="mx-auto flex min-h-svh max-w-lg flex-col items-center justify-center gap-4 px-4 text-center">
      <h1 className="text-2xl font-semibold text-brand-navy">You&apos;re signed in</h1>
      <p className="text-slate-600">
        Signed in as <strong>{user.full_name}</strong> ({user.role.replace('_', ' ')}).
      </p>
      <p className="max-w-sm text-sm text-slate-500">
        The authenticated application - invoices, exceptions, approvals, analytics - ships in Phase
        11. This page confirms the login flow works end to end with cookie auth.
      </p>
      <Button
        variant="outline"
        onClick={async () => {
          await logout.mutateAsync()
          navigate('/')
        }}
      >
        Log out
      </Button>
    </main>
  )
}
