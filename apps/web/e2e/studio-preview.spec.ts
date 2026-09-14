import { test, expect } from "@playwright/test";

/**
 * Structural Odoo preview gates — harness uses production FormCanvas / OdooListView.
 * Mode is selected via `?mode=` (select is intentionally disabled in the harness).
 */
test.describe("Odoo preview surfaces (phases 1–6)", () => {
  test("form harness: sheet, statusbar stages, smart buttons, notebook tabs, banner", async ({
    page,
  }) => {
    await page.goto("/e2e/designer?mode=form");
    await expect(page.getByTestId("designer-harness")).toBeVisible({ timeout: 15000 });

    await expect(page.getByTestId("odoo-preview-banner")).toBeVisible();
    await expect(page.getByTestId("form-canvas")).toBeVisible();
    await expect(page.getByTestId("odoo-form-sheet")).toBeVisible();
    await expect(page.getByTestId("odoo-statusbar")).toBeVisible();
    await expect(page.getByTestId("odoo-statusbar")).toContainText("new");
    await expect(page.getByTestId("odoo-statusbar")).toContainText("done");
    await expect(page.getByTestId("odoo-button-box")).toBeVisible();
    await expect(page.getByTestId("odoo-button-box")).toContainText("Orders");
    await expect(page.getByTestId("odoo-chatter-stub")).toBeVisible();
    await expect(page.getByRole("button", { name: "Lines", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Notes", exact: true })).toBeVisible();
  });

  test("list harness: OdooListView table with decorations", async ({ page }) => {
    await page.goto("/e2e/designer?mode=list");
    await expect(page.getByTestId("designer-harness")).toBeVisible({ timeout: 15000 });

    await expect(page.getByTestId("designer-list-layout")).toBeVisible();
    await expect(page.getByTestId("odoo-list-view")).toBeVisible();
    await expect(page.getByTestId("list-preview-table")).toBeVisible();
    await expect(page.getByTestId("list-preview-table")).toContainText("Name");
  });

  test("kanban harness still mounts", async ({ page }) => {
    await page.goto("/e2e/designer?mode=kanban");
    await expect(page.getByTestId("designer-harness")).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId("designer-kanban-layout")).toBeVisible();
    await expect(page.getByTestId("kanban-card-preview")).toBeVisible();
  });
});
