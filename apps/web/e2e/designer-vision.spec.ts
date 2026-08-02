import { expect, test } from "@playwright/test";
import path from "node:path";

const OUT_DIR = path.resolve(__dirname, "../../../docs/vision-verify");

const MODES = [
  { mode: "form", file: "designer-form.png", testId: "designer-form-layout" },
  { mode: "list", file: "designer-list.png", testId: "designer-list-layout" },
  { mode: "kanban", file: "designer-kanban.png", testId: "designer-kanban-layout" },
] as const;

test.describe("Designer vision-verify screenshots", () => {
  for (const { mode, file, testId } of MODES) {
    test(`capture ${mode}`, async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 1100 });
      await page.goto(`/e2e/designer?mode=${mode}`);
      await expect(page.getByTestId("designer-harness")).toHaveAttribute(
        "data-mode",
        mode,
      );
      await expect(page.getByTestId(testId)).toBeVisible();

      if (mode === "kanban") {
        await expect(page.getByTestId("kanban-card-preview")).toBeVisible();
        await expect(page.getByTestId("kanban-groupby-chip")).toContainText(
          "x_stage",
        );
      }
      if (mode === "list") {
        await expect(page.getByTestId("list-preview-table")).toBeVisible();
      }

      const outPath = path.join(OUT_DIR, file);
      await page.screenshot({
        path: outPath,
        fullPage: true,
      });
    });
  }
});
