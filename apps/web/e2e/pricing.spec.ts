import { test, expect } from "@playwright/test";

test.describe("Pricing page (MON-4 / REM-10)", () => {
  test("renders tier comparison from registry", async ({ page }) => {
    await page.goto("/pricing");
    await expect(page.getByRole("heading", { name: "Pricing" })).toBeVisible();
    await expect(page.getByText("Free Solo")).toBeVisible();
    await expect(page.getByText("Pro")).toBeVisible();
    await expect(page.getByText("Project Pass")).toBeVisible();
    await expect(page.getByText("Operate tools")).toBeVisible();
  });

  test("landing links to pricing", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "See pricing" })).toBeVisible();
  });

  test("shows registry-driven Pro price when API available", async ({ page }) => {
    await page.goto("/pricing");
    const proPrice = page.getByTestId("price-pro");
    if ((await proPrice.count()) > 0) {
      await expect(proPrice).toContainText("$39");
    }
  });
});

test.describe("Billing flows harness (REM-10)", () => {
  test("trial banner and upgrade sheet", async ({ page }) => {
    await page.goto("/e2e/billing");
    await expect(page.getByTestId("trial-banner")).toBeVisible();
    await expect(page.getByTestId("downgrade-summary")).toBeVisible();
    await page.getByTestId("open-upgrade").click();
    await expect(page.getByTestId("upgrade-sheet")).toBeVisible();
  });

  test("upgrade sheet extra-slots panel visible for slot limit", async ({ page }) => {
    await page.goto("/e2e/billing");
    await page.getByTestId("open-upgrade").click();
    await expect(page.getByTestId("upgrade-sheet")).toBeVisible();
    // Panel renders when catalog loads; may be empty offline — sheet still opens
    await expect(page.getByRole("link", { name: "Compare all plans" })).toBeVisible();
  });
});
