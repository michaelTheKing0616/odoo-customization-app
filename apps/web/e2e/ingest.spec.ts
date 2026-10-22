import { expect, test } from "@playwright/test";

test.describe("Universal ingest review UI", () => {
  test("commit order visible and gaps block commit", async ({ page }) => {
    await page.goto("/e2e/ingest");
    await expect(page.getByTestId("ingest-page")).toBeVisible();
    await expect(page.getByTestId("ingest-honesty")).toBeVisible();
    await expect(page.getByTestId("ingest-step-rail")).toBeVisible();
    await expect(page.getByTestId("ingest-commit-order")).toContainText("res.partner");
    await expect(page.getByTestId("ingest-step-0")).toBeVisible();
    await expect(page.getByTestId("ingest-gaps")).toBeVisible();
    await expect(page.getByTestId("ingest-commit-btn")).toBeDisabled();
    await expect(page.getByTestId("ingest-gap-block")).toBeVisible();
    await expect(page.getByTestId("ingest-commit-btn")).toHaveClass(/bg-accent/);
  });

  test("override requires a reason before apply", async ({ page }) => {
    await page.goto("/e2e/ingest?state=override");
    await expect(page.getByTestId("ingest-needs-confirm")).toBeVisible();
    await expect(page.getByTestId("ingest-apply-overrides")).toBeDisabled();
    await page.getByTestId("ingest-override-reason").fill("Vendor list misclassified");
    await expect(page.getByTestId("ingest-apply-overrides")).toBeEnabled();
  });

  test("dry-run result labels no writes", async ({ page }) => {
    await page.goto("/e2e/ingest?state=dry-run");
    await expect(page.getByTestId("ingest-commit-btn")).toBeEnabled();
    await expect(page.getByTestId("ingest-commit-log")).toContainText(
      "Test run result (no writes)",
    );
    await expect(page.getByTestId("ingest-step-rail-dry-run")).toHaveAttribute(
      "data-active",
      "true",
    );
  });

  test("empty state shows what/why/next", async ({ page }) => {
    await page.goto("/e2e/ingest?state=empty");
    await expect(page.getByText("No ingest job yet")).toBeVisible();
    await expect(page.getByTestId("ingest-step-rail-upload")).toHaveAttribute(
      "data-active",
      "true",
    );
  });
});
