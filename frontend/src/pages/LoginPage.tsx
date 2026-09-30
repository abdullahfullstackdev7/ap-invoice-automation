import { Link } from 'react-router-dom'

export function LoginPage() {
  return (
    <main className="mx-auto flex min-h-svh max-w-md flex-col justify-center gap-4 px-4">
      <h1 className="text-2xl font-semibold text-brand-navy">Log in</h1>
      <p className="text-sm text-slate-500">
        Authentication is implemented in Phase 3. This is a placeholder shell.
      </p>
      <Link to="/" className="text-sm text-brand-blue hover:underline">
        Back to home
      </Link>
    </main>
  )
}
