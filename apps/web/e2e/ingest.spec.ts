import { expect, test } from "@playwright/test";

test.describe("Universal ingest review UI", () => {
  test("commit order visible and gaps block commit", async ({ page }) => {
    await page.goto("/e2e/ingest");
    await expect(page.getByTestId("ingest-page")).toBeVisible();
    await expect(page.getByTestId("ingest-commit-order")).toContainText("res.partner");
    await expect(page.getByTestId("ingest-step-0")).toBeVisible();
    await expect(page.getByTestId("ingest-gaps")).toBeVisible();
    await expect(page.getByTestId("ingest-commit-btn")).toBeDisabled();
    await expect(page.getByTestId("ingest-gap-block")).toBeVisible();
  });
});
