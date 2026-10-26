import { defineConfig, devices } from "@playwright/test";

const baseURL = "http://127.0.0.1:3100";

export default defineConfig({
  testDir: "e2e",
  testMatch: /ui_f08\.spec\.ts$/,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 10_000 },
  reporter: "list",
  outputDir: "test-results/ui-f08",
  use: {
    baseURL,
    trace: "off",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "INGENIUM_DIST_DIR=.next-ui-f08 pnpm exec next dev --turbopack -H 127.0.0.1 -p 3100",
    cwd: ".",
    url: baseURL,
    reuseExistingServer: false,
    timeout: 180_000,
    env: {
      ...process.env,
      INGENIUM_DIST_DIR: ".next-ui-f08",
      PORT: "3100",
    },
  },
});
