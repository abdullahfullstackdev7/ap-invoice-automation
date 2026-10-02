import { defineConfig, devices } from '@playwright/test'

// Configurable so this project's e2e suite doesn't collide with another
// project's dev server already holding the default port in a shared
// environment (set PLAYWRIGHT_PORT to use something else).
const port = process.env.PLAYWRIGHT_PORT ?? '5173'
const baseURL = `http://localhost:${port}`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  reporter: 'html',
  use: {
    baseURL,
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npm run dev -- --port ${port} --strictPort`,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
  },
})
