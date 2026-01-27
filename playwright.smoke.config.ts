/**
 * Playwright configuration for smoke tests against the REAL production instance.
 *
 * Usage:
 *   npx playwright test tests/smoke.spec.ts --config=playwright.smoke.config.ts
 *
 * Prerequisites:
 *   - Production server must be running on port 31415
 *   - Start with: ./run start  (or use 'auto start dazflow')
 */
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  testMatch: 'smoke.spec.ts',
  outputDir: './output/testing/smoke-results',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [['html', { outputFolder: './output/smoke-report' }]],
  use: {
    baseURL: 'http://localhost:31415',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  // No webServer - expects production server to already be running
});
