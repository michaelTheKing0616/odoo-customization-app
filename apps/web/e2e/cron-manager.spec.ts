import { expect, test } from "@playwright/test";

test.describe("Cron Manager UI-S-32", () => {
  test("honesty and empty what/why/next", async ({ page }) => {
    await page.goto("/e2e/cron-manager?state=empty");
    await expect(page.getByTestId("cron-manager-page")).toBeVisible();
    await expect(page.getByTestId("cron-honesty-guide")).toBeVisible();
    await expect(page.getByTestId("cron-honesty-guide-title")).toContainText(
      "Enable, disable, and trigger are live",
    );
    await expect(page.getByTestId("cron-stage-rail")).toBeVisible();
    await expect(page.getByTestId("cron-step-list")).toHaveAttribute("data-state", "current");
    await expect(page.getByTestId("cron-empty-guide")).toBeVisible();
    await expect(page.getByTestId("cron-empty-guide-why")).toBeVisible();
    await expect(page.getByTestId("cron-empty-guide-next")).toBeVisible();
    await expect(page.getByTestId("cron-save-btn")).toHaveClass(/bg-accent/);
    await expect(page.getByTestId("cron-run-now-btn")).toBeDisabled();
    await expect(page.getByTestId("cron-dry-run-btn")).toBeDisabled();
  });

  test("select enables dry-run and run now secondary", async ({ page }) => {
    await page.goto("/e2e/cron-manager?state=select");
    await expect(page.getByTestId("cron-step-select")).toHaveAttribute("data-state", "current");
    await expect(page.getByTestId("cron-selected-count")).toContainText("1 selected");
    await expect(page.getByTestId("cron-dry-run-btn")).toBeEnabled();
    await expect(page.getByTestId("cron-run-now-btn")).toBeEnabled();
    await expect(page.getByTestId("cron-jobs-list")).toBeVisible();
    await expect(page.getByTestId("cron-toggle-11")).toContainText("Disable");
    await expect(page.getByTestId("cron-toggle-12")).toContainText("Enable");
  });

  test("dry-run result labels no writes", async ({ page }) => {
    await page.goto("/e2e/cron-manager?state=dry-run");
    await expect(page.getByTestId("cron-step-trigger")).toHaveAttribute("data-state", "current");
    await expect(page.getByTestId("cron-last-run")).toContainText("Test run result (no writes)");
    await expect(page.getByTestId("cron-last-run")).toHaveAttribute("data-dry-run", "true");
  });

  test("compose shows next-run preview in connection timezone", async ({ page }) => {
    await page.goto("/e2e/cron-manager?state=compose");
    await expect(page.getByTestId("cron-step-save")).toHaveAttribute("data-state", "current");
    await expect(page.getByTestId("cron-next-run-preview")).toBeVisible();
    await expect(page.getByTestId("cron-next-run-preview-zone")).toContainText("Africa/Lagos");
    await expect(page.getByTestId("cron-save-btn")).toHaveClass(/bg-accent/);
  });

  test("error guide is what/why/next", async ({ page }) => {
    await page.goto("/e2e/cron-manager?state=error");
    await expect(page.getByTestId("cron-error-guide")).toBeVisible();
    await expect(page.getByTestId("cron-error-guide-title")).toContainText("Could not load");
    await expect(page.getByTestId("cron-error-guide-why")).toBeVisible();
    await expect(page.getByTestId("cron-error-guide-next")).toBeVisible();
  });
});
