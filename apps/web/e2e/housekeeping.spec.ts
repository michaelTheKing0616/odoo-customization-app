import { expect, test } from "@playwright/test";

test.describe("Attachment housekeeping review UI", () => {
  test("honesty and empty what/why/next", async ({ page }) => {
    await page.goto("/e2e/housekeeping?state=empty");
    await expect(page.getByTestId("housekeeping-page")).toBeVisible();
    await expect(page.getByTestId("housekeeping-honesty")).toBeVisible();
    await expect(page.getByTestId("housekeeping-step-rail")).toBeVisible();
    await expect(page.getByTestId("housekeeping-step-rail-scan")).toHaveAttribute(
      "data-active",
      "true",
    );
    await expect(page.getByText("No scan yet")).toBeVisible();
    await expect(page.getByTestId("housekeeping-clean-btn")).toBeDisabled();
    await expect(page.getByTestId("housekeeping-clean-btn")).toHaveClass(/bg-accent/);
  });

  test("scanned state enables clean primary", async ({ page }) => {
    await page.goto("/e2e/housekeeping?state=scanned");
    await expect(page.getByTestId("housekeeping-step-rail-review")).toHaveAttribute(
      "data-active",
      "true",
    );
    await expect(page.getByTestId("housekeeping-selected-count")).toContainText("2");
    await expect(page.getByTestId("housekeeping-clean-btn")).toBeEnabled();
    await expect(page.getByTestId("housekeeping-dry-run-btn")).toBeEnabled();
    await expect(page.getByTestId("housekeeping-orphan-table")).toBeVisible();
  });

  test("dry-run result labels no writes", async ({ page }) => {
    await page.goto("/e2e/housekeeping?state=dry-run");
    await expect(page.getByTestId("housekeeping-step-rail-dry-run")).toHaveAttribute(
      "data-active",
      "true",
    );
    await expect(page.getByTestId("housekeeping-clean-result")).toContainText(
      "Test run result (no writes)",
    );
    await expect(page.getByTestId("housekeeping-clean-result")).toHaveAttribute(
      "data-dry-run",
      "true",
    );
  });

  test("cleaned shows snapshot id", async ({ page }) => {
    await page.goto("/e2e/housekeeping?state=cleaned");
    await expect(page.getByTestId("housekeeping-step-rail-clean")).toHaveAttribute(
      "data-active",
      "true",
    );
    await expect(page.getByTestId("housekeeping-clean-result")).toContainText(
      "Clean result (files deleted)",
    );
    await expect(page.getByTestId("housekeeping-snapshot-id")).toContainText(
      "snap_hk_7f3a",
    );
  });
});
