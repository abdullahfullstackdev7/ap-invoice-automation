import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiRequest } from '@/lib/api-client'
import { LoginPage } from '@/pages/LoginPage'

vi.mock('@/lib/api-client', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api-client')>('@/lib/api-client')
  return { ...actual, apiRequest: vi.fn() }
})

const mockedApiRequest = vi.mocked(apiRequest)

function renderLoginPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('LoginPage', () => {
  afterEach(() => {
    mockedApiRequest.mockReset()
  })

  it('shows validation errors for empty fields', async () => {
    const user = userEvent.setup()
    renderLoginPage()

    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByText('Email is required')).toBeInTheDocument()
    expect(screen.getByText('Password is required')).toBeInTheDocument()
    expect(mockedApiRequest).not.toHaveBeenCalled()
  })

  it('submits valid credentials and calls the login endpoint', async () => {
    mockedApiRequest.mockResolvedValueOnce({ status: 'ok' })
    const user = userEvent.setup()
    renderLoginPage()

    await user.type(screen.getByLabelText('Email'), 'clerk@example.com')
    await user.type(screen.getByLabelText('Password'), 'CorrectHorseBattery12')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    await waitFor(() =>
      expect(mockedApiRequest).toHaveBeenCalledWith('/auth/login', {
        method: 'POST',
        body: { email: 'clerk@example.com', password: 'CorrectHorseBattery12' },
      }),
    )
  })

  it('shows the MFA step when the backend requires it', async () => {
    mockedApiRequest.mockResolvedValueOnce({ status: 'mfa_required', mfa_token: 'challenge-token' })
    const user = userEvent.setup()
    renderLoginPage()

    await user.type(screen.getByLabelText('Email'), 'approver@example.com')
    await user.type(screen.getByLabelText('Password'), 'CorrectHorseBattery12')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByText('Enter your code')).toBeInTheDocument()
  })

  it('shows the demo access panel when demo mode is on', async () => {
    const user = userEvent.setup()
    renderLoginPage()

    await user.click(screen.getByRole('button', { name: /demo access/i }))
    expect(screen.getByText('admin@veridianpayables.demo')).toBeInTheDocument()
  })
})
