import { expect, test } from "@playwright/test";

test.describe("ID Generator review UI", () => {
  test("empty shows what/why/next and honesty", async ({ page }) => {
    await page.goto("/e2e/id-generator?state=empty");
    await expect(page.getByTestId("id-generator-page")).toBeVisible();
await expect(page.getByTestId("id-generator-studio-chrome")).toBeVisible();
    await expect(page.getByTestId("id-generator-studio-bar")).toBeVisible();
        await expect(page.getByTestId("id-generator-honesty")).toBeVisible();
    await expect(page.getByTestId("id-generator-honesty")).toContainText("never write");
    await expect(page.getByTestId("id-generator-empty-guide")).toBeVisible();
    await expect(page.getByTestId("id-generator-empty-guide-why")).toBeVisible();
    await expect(page.getByTestId("id-generator-empty-guide-next")).toBeVisible();
    await expect(page.getByTestId("id-generator-step-source")).toHaveAttribute("data-state", "current");
    await expect(page.getByTestId("id-generator-download")).toBeDisabled();
  });

  test("csv preview enables teal Download primary", async ({ page }) => {
    await page.goto("/e2e/id-generator?state=csv-preview");
    await expect(page.getByTestId("id-generator-download")).toBeEnabled();
    await expect(page.getByTestId("id-generator-download")).toHaveClass(/bg-accent/);
    await expect(page.getByTestId("id-generator-counts")).toBeVisible();
    await expect(page.getByTestId("id-generator-step-preview")).toHaveAttribute("data-state", "current");
    await expect(page.getByTestId("id-generator-counts-guide")).toContainText("Nothing was written");
  });

  test("live dry-run labels no writes and gates Apply honesty", async ({ page }) => {
    await page.goto("/e2e/id-generator?state=live-dry-run");
    await expect(page.getByTestId("id-generator-dry-run")).toBeVisible();
    await expect(page.getByTestId("id-generator-counts-guide")).toContainText("Nothing was written");
    await expect(page.getByTestId("id-generator-preview-panel")).toContainText("no writes");
  });

  test("sequence state explains bridge is after Apply", async ({ page }) => {
    await page.goto("/e2e/id-generator?state=sequence");
    await expect(page.getByTestId("id-generator-sequence-guide")).toContainText("after Apply");
    await expect(page.getByTestId("id-generator-step-deliver")).toHaveAttribute("data-state", "current");
  });

  test("error uses what/why/next", async ({ page }) => {
    await page.goto("/e2e/id-generator?state=error");
    await expect(page.getByTestId("id-generator-error")).toBeVisible();
    await expect(page.getByTestId("id-generator-error-why")).toBeVisible();
    await expect(page.getByTestId("id-generator-error-next")).toBeVisible();
  });
});
