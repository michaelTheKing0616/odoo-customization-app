import { defineConfig, devices } from "@playwright/test";

const baseURL = "http://127.0.0.1:3114";

export default defineConfig({
  testDir: "e2e",
  testMatch: /shell_drawer\.spec\.ts$/,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 10_000 },
  reporter: "list",
  outputDir: "test-results/shell-drawer",
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
    command:
      "INGENIUM_DIST_DIR=.next-shell-drawer pnpm exec next dev --turbopack -H 127.0.0.1 -p 3114",
    cwd: ".",
    url: baseURL,
    reuseExistingServer: false,
    timeout: 180_000,
    env: {
      ...process.env,
      INGENIUM_DIST_DIR: ".next-shell-drawer",
      PORT: "3114",
    },
  },
});
