import { Loader2 } from 'lucide-react'
import { useEffect } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'

import { useCurrentUser } from '@/lib/hooks/use-auth'

export function RequireAuth() {
  const navigate = useNavigate()
  const { data: user, isLoading, isError } = useCurrentUser()

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
  return <Outlet />
}
