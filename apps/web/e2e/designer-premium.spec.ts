import { expect, test } from "@playwright/test";
import path from "node:path";

const OUT_DIR = path.resolve(__dirname, "../../../docs/vision-verify");

test.describe("Studio-like View Designer shell", () => {
  test("form harness: live/layout canvas + tools rail + Odoo widgets + palette drop", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 1100 });
    await page.goto("/e2e/designer?mode=form");
    await expect(page.getByTestId("designer-harness")).toHaveAttribute("data-mode", "form");
    await expect(page.getByTestId("designer-studio-canvas")).toBeVisible();
    await expect(page.getByTestId("designer-tools-rail")).toBeVisible();
    await expect(page.getByTestId("form-canvas")).toBeVisible();
    await expect(page.getByTestId("odoo-form-sheet")).toBeVisible();
    await expect(page.getByTestId("odoo-widget-char-x_name")).toBeVisible();
    await expect(page.getByTestId("designer-field-palette")).toBeVisible();
    await expect(page.getByTestId("designer-canvas-mode-structure")).toBeVisible();

    const palette = page.getByTestId("palette-field-x_stage");
    const drop = page.getByTestId("canvas-drop-list").first();
    await palette.dragTo(drop);
    await expect(page.getByTestId("canvas-field-x_stage")).toBeVisible();

    await page.getByRole("button", { name: /Name.*x_name/i }).click();
    await page.getByRole("tab", { name: "Properties" }).click();
    await expect(page.getByText("x_name").first()).toBeVisible();

    await page.screenshot({
      path: path.join(OUT_DIR, "designer-studio-shell.png"),
      fullPage: true,
    });
  });

  test("list harness uses Odoo list preview, not wireframe boxes", async ({ page }) => {
    await page.goto("/e2e/designer?mode=list");
    await expect(page.getByTestId("designer-list-layout")).toBeVisible();
    await expect(page.getByTestId("odoo-list-view")).toBeVisible();
    await expect(page.getByTestId("designer-tools-rail")).toBeVisible();
  });

  test("tracks A–D chrome: session bar, properties, xpath behind Advanced", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1100 });
    await page.goto("/e2e/designer-premium");
    await expect(page.getByTestId("designer-premium-harness")).toBeVisible();
    await expect(page.getByTestId("designer-session-bar")).toBeVisible();
    await expect(page.getByTestId("designer-publish-state")).toContainText("Unpublished");
    await expect(page.getByTestId("designer-studio-canvas")).toBeVisible();
    await expect(page.getByTestId("odoo-form-sheet")).toBeVisible();
    await expect(page.getByTestId("overlay-hud")).toBeVisible();
    await page.getByRole("tab", { name: "Advanced" }).click();
    await expect(page.getByTestId("designer-xpath-panel")).toBeVisible();
    await page.screenshot({
      path: path.join(OUT_DIR, "designer-premium-studio.png"),
      fullPage: true,
    });
  });
});
