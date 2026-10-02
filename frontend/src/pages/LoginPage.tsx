import { zodResolver } from '@hookform/resolvers/zod'
import { AlertCircle, ChevronDown, Eye, EyeOff, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { Button } from '@/components/ui/Button'
import { ApiError } from '@/lib/api-client'
import { useLogin, useVerifyMfa } from '@/lib/hooks/use-auth'

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE !== 'false'

const DEMO_ACCOUNTS = [
  { email: 'admin@veridianpayables.demo', role: 'Admin' },
  { email: 'clerk@veridianpayables.demo', role: 'AP Clerk' },
  { email: 'approver@veridianpayables.demo', role: 'Approver' },
  { email: 'manager@veridianpayables.demo', role: 'Finance Manager' },
  { email: 'auditor@veridianpayables.demo', role: 'Auditor' },
]
const DEMO_PASSWORD = 'ChangeMe123Demo!'

const loginSchema = z.object({
  email: z.string().min(1, 'Email is required').email('Enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
})

type LoginFormValues = z.infer<typeof loginSchema>

export function LoginPage() {
  const navigate = useNavigate()
  const login = useLogin()
  const verifyMfa = useVerifyMfa()

  const [showPassword, setShowPassword] = useState(false)
  const [demoOpen, setDemoOpen] = useState(false)
  const [mfaToken, setMfaToken] = useState<string | null>(null)
  const [mfaCode, setMfaCode] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema) })

  async function onSubmit(values: LoginFormValues) {
    setFormError(null)
    try {
      const result = await login.mutateAsync(values)
      if (result.status === 'mfa_required' && result.mfa_token) {
        setMfaToken(result.mfa_token)
        return
      }
      navigate('/app')
    } catch (error) {
      setFormError(
        error instanceof ApiError ? (error.detail ?? error.title) : 'Something went wrong',
      )
    }
  }

  async function onVerifyMfa(event: React.FormEvent) {
    event.preventDefault()
    if (!mfaToken) return
    setFormError(null)
    try {
      await verifyMfa.mutateAsync({ mfa_token: mfaToken, code: mfaCode })
      navigate('/app')
    } catch (error) {
      setFormError(error instanceof ApiError ? (error.detail ?? error.title) : 'Invalid code')
    }
  }

  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between bg-gradient-to-br from-brand-navy to-brand-navy-light p-12 text-white lg:flex">
        <Link to="/" className="flex items-center gap-2 text-lg font-semibold">
          <span
            aria-hidden="true"
            className="flex size-8 items-center justify-center rounded-lg bg-brand-blue text-sm font-bold"
          >
            V
          </span>
          Veridian Payables
        </Link>
        <div>
          <p className="font-serif text-3xl font-semibold">
            Every invoice matched, verified and paid with confidence.
          </p>
          <p className="mt-4 max-w-sm text-sm text-slate-300">
            Sign in to review exceptions, approve invoices and keep payments on schedule.
          </p>
        </div>
        <p className="text-xs text-slate-400">Sample product for demonstration.</p>
      </div>

      <div className="flex flex-col justify-center px-6 py-16 sm:px-12 lg:px-16">
        <div className="mx-auto w-full max-w-sm">
          <Link
            to="/"
            className="mb-8 inline-flex items-center gap-2 text-sm text-slate-500 hover:text-brand-navy lg:hidden"
          >
            &larr; Back to home
          </Link>

          {mfaToken ? (
            <>
              <h1 className="text-2xl font-semibold text-brand-navy">Enter your code</h1>
              <p className="mt-2 text-sm text-slate-500">
                Enter the 6-digit code from your authenticator app.
              </p>
              <form onSubmit={onVerifyMfa} className="mt-8 flex flex-col gap-5" noValidate>
                <div>
                  <label
                    htmlFor="mfa-code"
                    className="mb-1.5 block text-sm font-medium text-slate-700"
                  >
                    Verification code
                  </label>
                  <input
                    id="mfa-code"
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    required
                    value={mfaCode}
                    onChange={(event) => setMfaCode(event.target.value)}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm tracking-widest focus-visible:border-brand-blue"
                  />
                </div>
                {formError ? <FormAlert message={formError} /> : null}
                <Button type="submit" disabled={verifyMfa.isPending} className="w-full">
                  {verifyMfa.isPending ? (
                    <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  ) : null}
                  Verify
                </Button>
              </form>
            </>
          ) : (
            <>
              <h1 className="text-2xl font-semibold text-brand-navy">Log in</h1>
              <p className="mt-2 text-sm text-slate-500">
                Welcome back. Enter your details to continue.
              </p>

              <form
                onSubmit={handleSubmit(onSubmit)}
                className="mt-8 flex flex-col gap-5"
                noValidate
              >
                <div>
                  <label
                    htmlFor="email"
                    className="mb-1.5 block text-sm font-medium text-slate-700"
                  >
                    Email
                  </label>
                  <input
                    id="email"
                    type="email"
                    autoComplete="email"
                    aria-invalid={Boolean(errors.email)}
                    aria-describedby={errors.email ? 'email-error' : undefined}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus-visible:border-brand-blue"
                    {...register('email')}
                  />
                  {errors.email ? (
                    <p id="email-error" className="mt-1.5 text-sm text-(--color-danger)">
                      {errors.email.message}
                    </p>
                  ) : null}
                </div>

                <div>
                  <div className="mb-1.5 flex items-center justify-between">
                    <label htmlFor="password" className="text-sm font-medium text-slate-700">
                      Password
                    </label>
                    <Link to="/contact" className="text-xs text-brand-blue hover:underline">
                      Forgot password?
                    </Link>
                  </div>
                  <div className="relative">
                    <input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="current-password"
                      aria-invalid={Boolean(errors.password)}
                      aria-describedby={errors.password ? 'password-error' : undefined}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2.5 pr-10 text-sm focus-visible:border-brand-blue"
                      {...register('password')}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((show) => !show)}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      className="absolute top-1/2 right-3 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                    >
                      {showPassword ? (
                        <EyeOff className="size-4" aria-hidden="true" />
                      ) : (
                        <Eye className="size-4" aria-hidden="true" />
                      )}
                    </button>
                  </div>
                  {errors.password ? (
                    <p id="password-error" className="mt-1.5 text-sm text-(--color-danger)">
                      {errors.password.message}
                    </p>
                  ) : null}
                </div>

                <label className="flex items-center gap-2 text-sm text-slate-600">
                  <input type="checkbox" className="size-4 rounded border-slate-300" />
                  Keep me signed in on this device
                </label>

                {formError ? <FormAlert message={formError} /> : null}

                <Button type="submit" disabled={login.isPending} className="w-full">
                  {login.isPending ? (
                    <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  ) : null}
                  Log in
                </Button>
              </form>

              {DEMO_MODE ? (
                <div className="mt-8 rounded-xl border border-slate-200">
                  <button
                    type="button"
                    aria-expanded={demoOpen}
                    aria-controls="demo-access-panel"
                    onClick={() => setDemoOpen((open) => !open)}
                    className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-brand-navy"
                  >
                    Demo access
                    <ChevronDown
                      className={`size-4 transition-transform ${demoOpen ? 'rotate-180' : ''}`}
                      aria-hidden="true"
                    />
                  </button>
                  {demoOpen ? (
                    <div
                      id="demo-access-panel"
                      className="border-t border-slate-200 px-4 py-3 text-xs text-slate-600"
                    >
                      <p className="mb-2">
                        Password for every account:{' '}
                        <code className="rounded bg-slate-100 px-1 py-0.5">{DEMO_PASSWORD}</code>
                      </p>
                      <ul className="space-y-1">
                        {DEMO_ACCOUNTS.map((account) => (
                          <li key={account.email} className="flex justify-between gap-4">
                            <code className="text-slate-700">{account.email}</code>
                            <span className="text-slate-500">{account.role}</span>
                          </li>
                        ))}
                      </ul>
                      <p className="mt-2 text-slate-500">
                        Sample deployment only. Change these before exposing it outside a local
                        sandbox.
                      </p>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function FormAlert({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-lg bg-(--color-danger-bg) px-3 py-2.5 text-sm text-(--color-danger)"
    >
      <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      {message}
    </div>
  )
}
