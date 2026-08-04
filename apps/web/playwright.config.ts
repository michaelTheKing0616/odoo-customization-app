import { defineConfig, devices } from "@playwright/test";

const isCI = !!process.env.CI;

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000";
const webPort = new URL(baseURL).port || "3000";

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 2 : 0,
  reporter: "list",
  use: {
    baseURL,
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
    command: `pnpm exec next build && pnpm exec next start -H 127.0.0.1 -p ${webPort}`,
    cwd: ".",
    url: `${baseURL}/e2e/overlay`,
    reuseExistingServer: !isCI,
    timeout: 180_000,
    env: {
      ...process.env,
      NEXT_PUBLIC_E2E: "1",
      NEXT_PUBLIC_API_URL:
        process.env.NEXT_PUBLIC_API_URL ??
        process.env.PLAYWRIGHT_API_BASE ??
        "http://127.0.0.1:8001",
    },
  },
});
