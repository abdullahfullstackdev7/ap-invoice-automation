import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

/** Plan.md section 10 acceptance: "axe shows no serious violations" on
 * every public route. Lighthouse's >= 90 targets are not checked here;
 * this sandbox has no way to run a real Lighthouse pass against a
 * production build (see docs/analytics.md-style caveats elsewhere in
 * this repo for the same honesty pattern). */
const PUBLIC_ROUTES = [
  '/',
  '/platform',
  '/solutions',
  '/security',
  '/resources',
  '/resources/what-is-3-way-match',
  '/about',
  '/contact',
  '/privacy',
  '/terms',
  '/cookies',
  '/login',
]

for (const route of PUBLIC_ROUTES) {
  test(`${route} has no serious or critical axe violations`, async ({ page }) => {
    await page.goto(route)
    const results = await new AxeBuilder({ page }).analyze()
    const seriousOrWorse = results.violations.filter((v) =>
      ['serious', 'critical'].includes(v.impact ?? ''),
    )
    expect(seriousOrWorse, JSON.stringify(seriousOrWorse, null, 2)).toEqual([])
  })
}

test('404 page has no serious or critical axe violations', async ({ page }) => {
  await page.goto('/this-route-does-not-exist')
  const results = await new AxeBuilder({ page }).analyze()
  const seriousOrWorse = results.violations.filter((v) =>
    ['serious', 'critical'].includes(v.impact ?? ''),
  )
  expect(seriousOrWorse, JSON.stringify(seriousOrWorse, null, 2)).toEqual([])
})
