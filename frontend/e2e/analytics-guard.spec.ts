import { expect, test } from '@playwright/test'

test('analytics page redirects unauthenticated visitors to login', async ({ page }) => {
  await page.goto('/analytics')
  await expect(page).toHaveURL(/\/login/)
})
