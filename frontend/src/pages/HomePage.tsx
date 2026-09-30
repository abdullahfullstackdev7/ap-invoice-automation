import { Link } from 'react-router-dom'

import { useHealth } from '@/lib/hooks/use-health'

export function HomePage() {
  const { data, isLoading, isError } = useHealth()

  return (
    <main className="mx-auto flex min-h-svh max-w-[1240px] flex-col items-center justify-center gap-4 px-4 text-center">
      <h1 className="font-serif text-4xl font-semibold text-brand-navy md:text-5xl">
        Veridian Payables
      </h1>
      <p className="max-w-xl text-slate-600">
        Every invoice matched, verified and paid with confidence.
      </p>
      <p className="text-sm text-slate-500">
        API status:{' '}
        {isLoading ? 'checking...' : isError ? 'unreachable' : (data?.status ?? 'unknown')}
      </p>
      <Link
        to="/login"
        className="rounded-lg bg-brand-blue px-5 py-2.5 text-sm font-medium text-white hover:bg-brand-blue/90"
      >
        Log in to the platform
      </Link>
    </main>
  )
}
