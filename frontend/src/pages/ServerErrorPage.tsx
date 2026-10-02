import { Link } from 'react-router-dom'

export function ServerErrorPage() {
  return (
    <main className="mx-auto flex min-h-svh max-w-md flex-col items-center justify-center gap-4 px-4 text-center">
      <p className="text-sm font-semibold text-brand-blue">500</p>
      <h1 className="text-2xl font-semibold text-brand-navy">Something went wrong</h1>
      <p className="text-sm text-slate-500">
        An unexpected error occurred. Try reloading the page, or head back home.
      </p>
      <Link to="/" className="text-sm text-brand-blue hover:underline">
        Back to home
      </Link>
    </main>
  )
}
