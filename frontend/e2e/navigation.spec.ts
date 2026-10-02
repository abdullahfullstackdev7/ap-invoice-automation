import { expect, test } from '@playwright/test'

test('home page shows the hero and primary CTA', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toContainText(
    'Every invoice matched, verified and paid with confidence',
  )
  await expect(page.getByRole('link', { name: /log in to the platform/i })).toBeVisible()
})

test('nav mega menu opens and links to a platform section', async ({ page }) => {
  await page.goto('/')
  await page
    .getByRole('navigation', { name: 'Main' })
    .getByRole('button', { name: 'Platform' })
    .click()
  await page
    .getByRole('navigation', { name: 'Main' })
    .getByRole('link', { name: /3-way match/i })
    .click()
  await expect(page).toHaveURL(/\/platform#match/)
})

test('FAQ accordion expands an answer', async ({ page }) => {
  await page.goto('/')
  const question = page.getByRole('button', { name: /what file formats are supported/i })
  await question.click()
  await expect(question).toHaveAttribute('aria-expanded', 'true')
})

test('login page shows a validation error for an empty form', async ({ page }) => {
  await page.goto('/login')
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page.getByText('Email is required')).toBeVisible()
})

test('404 page links back home', async ({ page }) => {
  await page.goto('/this-route-does-not-exist')
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible()
  await page.getByRole('link', { name: /back to home/i }).click()
  await expect(page).toHaveURL('/')
})
