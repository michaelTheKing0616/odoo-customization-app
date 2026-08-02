import { defineConfig, devices } from "@playwright/test";

const isCI = !!process.env.CI;

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 2 : 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    // Prefer production server for e2e — avoids Next file-watcher EMFILE issues.
    command: "pnpm exec next build && pnpm exec next start -H 127.0.0.1 -p 3000",
    cwd: ".",
    url: "http://127.0.0.1:3000/e2e/confirm",
    reuseExistingServer: !isCI,
    timeout: 180_000,
    env: {
      ...process.env,
      NEXT_PUBLIC_E2E: "1",
    },
  },
});
