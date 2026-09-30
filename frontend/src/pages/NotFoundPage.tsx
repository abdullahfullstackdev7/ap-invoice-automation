import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <main className="mx-auto flex min-h-svh max-w-md flex-col items-center justify-center gap-4 px-4 text-center">
      <h1 className="text-2xl font-semibold text-brand-navy">Page not found</h1>
      <Link to="/" className="text-sm text-brand-blue hover:underline">
        Back to home
      </Link>
    </main>
  )
}
