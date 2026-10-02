import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { MainNav } from '@/components/layout/MainNav'

describe('MainNav', () => {
  it('opens and closes the mobile drawer', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <MainNav />
      </MemoryRouter>,
    )

    const toggle = screen.getByRole('button', { name: /open menu/i })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')

    await user.click(toggle)
    expect(screen.getByRole('button', { name: /close menu/i })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    expect(screen.getAllByRole('link', { name: 'Request a demo' }).length).toBeGreaterThan(0)
  })

  it('opens the Platform mega menu with its items', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <MainNav />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', { name: 'Platform' }))
    expect(screen.getByRole('link', { name: /3-way match/i })).toHaveAttribute(
      'href',
      '/platform#match',
    )
  })
})
