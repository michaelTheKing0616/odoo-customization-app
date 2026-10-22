import { expect, test, type Page } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

const OUT_DIR = path.resolve(__dirname, "../../../docs/vision-verify/PDF-01");
const PHASE = process.env.PDF01_PHASE === "after" ? "after" : "before";

async function applyTheme(page: Page, theme: "light" | "dark") {
  await page.addInitScript((t) => {
    localStorage.setItem("odoo-custom-theme", t);
    document.documentElement.classList.toggle("dark", t === "dark");
  }, theme);
}

test.describe(`PDF-01 vision ${PHASE}`, () => {
  test.describe.configure({ timeout: 90_000 });

  for (const theme of ["light", "dark"] as const) {
    test(`capture canvas ${PHASE} ${theme}`, async ({ page }) => {
      fs.mkdirSync(OUT_DIR, { recursive: true });
      await applyTheme(page, theme);
      await page.setViewportSize({ width: 1440, height: 1100 });
      await page.goto("/e2e/report-canvas");
      await expect(page.getByTestId("report-canvas-harness")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("report-canvas-stage")).toBeVisible();
      // Prefer paper node when present; fall back to stage for before shots.
      const paper = page.locator("[data-testid='report-paper']");
      const target = (await paper.count()) > 0 ? paper : page.getByTestId("report-canvas-stage");
      await target.screenshot({
        path: path.join(OUT_DIR, `${PHASE}-${theme}.png`),
      });
      // Full desktop frame for the card folder as well.
      await page.screenshot({
        path: path.join(OUT_DIR, `${PHASE}-desktop-${theme}.png`),
        fullPage: true,
      });
    });
  }

  test(`capture empty ${PHASE} light`, async ({ page }) => {
    fs.mkdirSync(OUT_DIR, { recursive: true });
    await applyTheme(page, "light");
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/e2e/report-canvas");
    await expect(page.getByTestId("report-canvas-harness")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("harness-toggle-empty").click();
    await page.screenshot({
      path: path.join(OUT_DIR, `${PHASE}-empty-light.png`),
      fullPage: true,
    });
  });
});
