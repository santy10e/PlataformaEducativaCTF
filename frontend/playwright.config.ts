import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  retries: 0,
  reporter: 'list',
  // CYBERLAB_E2E_BASE_URL targets a running stack (for example http://localhost); otherwise a Vite dev server proxies to it.
  use: { baseURL: process.env.CYBERLAB_E2E_BASE_URL ?? 'http://127.0.0.1:5174', trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: process.env.CYBERLAB_E2E_BASE_URL ? undefined : {
    command: 'npm run dev -- --host 127.0.0.1 --port 5174',
    url: 'http://127.0.0.1:5174/login',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
})
