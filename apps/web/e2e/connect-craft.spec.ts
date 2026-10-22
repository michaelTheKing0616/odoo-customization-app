import { test, expect } from "@playwright/test";

const base = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3080";

test.describe("UI-CONNECT connect craft (paper)", () => {
  test("empty: paper + one Observer chip + teal Add connection (no twin banners)", async ({
    page,
  }) => {
    await page.goto(`${base}/e2e/connect?state=empty`);
    await expect(page.getByTestId("connect-page")).toBeVisible();
    await expect(page.locator(".cn-paper")).toBeVisible();
    await expect(page.locator(".cn-hero h1")).toHaveText(/Connect your Odoo/);
    // One Observer chip (real risk), not stacked what/why/next banners
    await expect(page.getByTestId("connect-honesty")).toBeVisible();
    await expect(page.getByTestId("connect-honesty-title")).toContainText(/Observer/i);
    await expect(page.getByTestId("connect-honesty")).not.toContainText(/^Why$/);
    // No twin API-key banner on empty/self-host default
    await expect(page.getByTestId("connect-api-key-honesty")).toHaveCount(0);
    await expect(page.getByTestId("connect-empty-guide")).toBeVisible();
    await expect(page.getByTestId("connect-add-btn")).toHaveText("Add connection");
    await expect(page.getByTestId("connect-step-credentials")).toHaveAttribute(
      "data-state",
      "current",
    );
  });

  test("credentials Online: secret tip inline, not a second honesty banner", async ({ page }) => {
    await page.goto(`${base}/e2e/connect?state=credentials`);
    await expect(page.getByTestId("connect-api-key-honesty")).toBeVisible();
    await expect(page.getByTestId("connect-api-key-honesty")).toContainText(/API key/i);
    // Still only one Observer chip
    await expect(page.getByTestId("connect-honesty")).toHaveCount(1);
  });

  test("probing: progress inside paper", async ({ page }) => {
    await page.goto(`${base}/e2e/connect?state=probing`);
    await expect(page.getByTestId("connect-step-probe")).toHaveAttribute("data-state", "current");
    await expect(page.getByTestId("connect-probe-progress")).toBeVisible();
    await expect(page.getByTestId("connect-add-btn")).toBeDisabled();
  });

  test("error-auth: danger panel only when failed", async ({ page }) => {
    await page.goto(`${base}/e2e/connect?state=error-auth`);
    await expect(page.getByTestId("connect-error-guide")).toBeVisible();
    await expect(page.getByTestId("connect-error-guide-next")).toContainText(/API key/i);
  });

  test("success: connected paper + App Studio primary", async ({ page }) => {
    await page.goto(`${base}/e2e/connect?state=success`);
    await expect(page.getByTestId("connect-step-summary")).toHaveAttribute(
      "data-state",
      "current",
    );
    await expect(page.getByTestId("connect-connected-guide")).toBeVisible();
    await expect(page.getByTestId("connect-first-win-app-studio")).toBeVisible();
    // Observer chip gone on success
    await expect(page.getByTestId("connect-honesty")).toHaveCount(0);
  });

  test("no em dashes in visible connect copy", async ({ page }) => {
    await page.goto(`${base}/e2e/connect?state=credentials`);
    const text = await page.getByTestId("connect-page").innerText();
    expect(text).not.toMatch(/[\u2014\u2013]/);
  });
});
