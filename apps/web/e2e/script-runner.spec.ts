import { expect, test } from "@playwright/test";

test.describe("Script Runner page", () => {
  test("renders editor and console on a live connection when available", async ({ page }) => {
    await page.goto("/connect");
    const connectionLink = page.locator('a[href^="/connections/"]').first();
    if ((await connectionLink.count()) === 0) {
      test.skip();
    }
    const href = await connectionLink.getAttribute("href");
    if (!href) test.skip();
    await page.goto(`${href}/script-runner`);
    await expect(page.getByTestId("script-runner-page")).toBeVisible();
    await expect(page.getByTestId("script-runner-editor")).toBeVisible();
    await expect(page.getByTestId("script-runner-console")).toBeVisible();
  });

  test("harness: studio bar honesty, no dry-run stage, teal Run primary", async ({ page }) => {
    await page.goto("/e2e/script-runner?state=idle");
    await expect(page.getByTestId("script-runner-page")).toBeVisible();
    await expect(page.getByTestId("script-runner-studio-chrome")).toBeVisible();
    await expect(page.getByTestId("script-runner-studio-bar")).toBeVisible();
    await expect(page.getByTestId("script-runner-honesty")).toContainText(/no dry-run/i);
    await expect(page.locator(".op-studio .sr-guide")).toHaveCount(0);
    await expect(page.getByTestId("script-runner-step-compose")).toBeVisible();
    await expect(page.getByTestId("script-runner-step-confirm")).toBeVisible();
    await expect(page.getByTestId("script-runner-step-run")).toBeVisible();
    await expect(page.getByTestId("script-runner-step-dry-run")).toHaveCount(0);
    await expect(page.getByTestId("script-runner-run-btn")).toBeVisible();
    await expect(page.getByTestId("script-runner-idle-guide")).toBeVisible();
  });

  test("harness: confirm dialog states no dry-run", async ({ page }) => {
    await page.goto("/e2e/script-runner?state=confirm");
    await expect(page.getByTestId("confirm-dialog-v2")).toBeVisible();
    await expect(page.getByTestId("confirm-dialog-v2")).toContainText(/no dry-run/i);
    await expect(page.getByTestId("script-runner-step-confirm")).toHaveAttribute("data-state", "current");
  });

  test("harness: succeeded shows snapshot restore honesty", async ({ page }) => {
    await page.goto("/e2e/script-runner?state=succeeded");
    await expect(page.getByTestId("script-runner-success")).toContainText(/3 writes/i);
    await expect(page.getByTestId("script-runner-restore")).toContainText("snap_sr_9a2c");
    await expect(page.getByTestId("script-runner-restore")).toContainText(/partly recoverable|does not undo/i);
    await expect(page.getByTestId("script-runner-result-label")).toContainText(/writes applied/i);
  });

  test("harness: failed and observer what/why/next", async ({ page }) => {
    await page.goto("/e2e/script-runner?state=failed");
    await expect(page.getByTestId("script-runner-failure")).toContainText(/AccessError|failed/i);
    await page.goto("/e2e/script-runner?state=observer");
    await expect(page.getByTestId("script-runner-observer")).toContainText(/observer/i);
    await expect(page.getByTestId("script-runner-run-btn")).toBeDisabled();
  });

  test("harness: empty what/why/next", async ({ page }) => {
    await page.goto("/e2e/script-runner?state=empty");
    await expect(page.getByTestId("script-runner-empty-guide")).toBeVisible();
    await expect(page.getByTestId("script-runner-empty-guide-next")).toContainText(/Run script/i);
  });
});
