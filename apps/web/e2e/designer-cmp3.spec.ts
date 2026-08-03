import { expect, test } from "@playwright/test";

test.describe("Designer CMP-3 niche palette + preview theme", () => {
  test("form harness shows niche palette and themed preview scope", async ({ page }) => {
    await page.goto("/e2e/designer?mode=form");
    await expect(page.getByTestId("niche-widget-palette")).toBeVisible();
    await expect(page.getByTestId("niche-widget-palette")).toContainText("boolean_favorite");
    const scope = page.getByTestId("preview-theme-scope");
    await expect(scope).toBeVisible();
    await expect(scope).toHaveCSS("--odoo-primary", "#714B67");
  });

  test("kanban harness shows niche palette and themed preview scope", async ({ page }) => {
    await page.goto("/e2e/designer?mode=kanban");
    await expect(page.getByTestId("niche-widget-palette")).toBeVisible();
    await expect(page.getByTestId("kanban-card-preview")).toBeVisible();
    await expect(page.getByTestId("preview-theme-scope")).toHaveCSS(
      "--odoo-primary",
      "#714B67",
    );
  });
});
