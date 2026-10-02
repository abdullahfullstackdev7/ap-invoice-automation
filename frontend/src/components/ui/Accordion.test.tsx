import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { Accordion } from '@/components/ui/Accordion'

const items = [
  { question: 'First question', answer: 'First answer' },
  { question: 'Second question', answer: 'Second answer' },
]

describe('Accordion', () => {
  it('opens the first item by default and collapses it on click', async () => {
    const user = userEvent.setup()
    render(<Accordion items={items} />)

    const firstButton = screen.getByRole('button', { name: 'First question' })
    expect(firstButton).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('First answer')).toBeVisible()

    await user.click(firstButton)
    expect(firstButton).toHaveAttribute('aria-expanded', 'false')
  })

  it('opens a different item and closes the previous one', async () => {
    const user = userEvent.setup()
    render(<Accordion items={items} />)

    const secondButton = screen.getByRole('button', { name: 'Second question' })
    await user.click(secondButton)

    expect(secondButton).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('button', { name: 'First question' })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
  })
})
