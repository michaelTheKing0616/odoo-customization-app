import { expect, test, type Page } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

const OUT_DIR = path.resolve(__dirname, "../../../docs/vision-verify/PDF-06");

async function applyTheme(page: Page, theme: "light" | "dark") {
  await page.addInitScript((t) => {
    localStorage.setItem("odoo-custom-theme", t);
    document.documentElement.classList.toggle("dark", t === "dark");
  }, theme);
}

async function gotoHarness(page: Page) {
  await page.goto("/e2e/reports-studio");
  await expect(page.getByTestId("reports-studio-harness")).toBeVisible({
    timeout: 30_000,
  });
}

test.describe("PDF-06 vision UI-S-17", () => {
  test.describe.configure({ timeout: 90_000 });

  test("capture desktop", async ({ page }) => {
    fs.mkdirSync(OUT_DIR, { recursive: true });
    await applyTheme(page, "light");
    await page.setViewportSize({ width: 1440, height: 1100 });
    await gotoHarness(page);
    await page.getByTestId("harness-shot-desktop").click();
    await expect(page.getByTestId("reports-save-arch")).toHaveText("Save the printout");
    await page.screenshot({
      path: path.join(OUT_DIR, "desktop.png"),
      fullPage: true,
    });
  });

  test("capture narrow ~390", async ({ page }) => {
    fs.mkdirSync(OUT_DIR, { recursive: true });
    await applyTheme(page, "light");
    await page.setViewportSize({ width: 390, height: 844 });
    await gotoHarness(page);
    await page.getByTestId("harness-shot-desktop").click();
    await page.screenshot({
      path: path.join(OUT_DIR, "narrow.png"),
      fullPage: true,
    });
  });

  test("capture inherit mode", async ({ page }) => {
    fs.mkdirSync(OUT_DIR, { recursive: true });
    await applyTheme(page, "light");
    await page.setViewportSize({ width: 1440, height: 1100 });
    await gotoHarness(page);
    await page.getByTestId("harness-shot-inherit").click();
    await expect(page.getByTestId("report-inherit-chrome")).toBeVisible();
    await page.screenshot({
      path: path.join(OUT_DIR, "inherit-mode.png"),
      fullPage: true,
    });
  });

  test("capture render error", async ({ page }) => {
    fs.mkdirSync(OUT_DIR, { recursive: true });
    await applyTheme(page, "light");
    await page.setViewportSize({ width: 1440, height: 1100 });
    await gotoHarness(page);
    await page.getByTestId("harness-shot-render-error").click();
    await expect(page.getByTestId("report-render-error")).toBeVisible();
    await expect(page.getByTestId("report-render-error-line")).toContainText(
      "Template line 28",
    );
    await page.screenshot({
      path: path.join(OUT_DIR, "render-error.png"),
      fullPage: true,
    });
  });
});
