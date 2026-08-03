import { expect, test, type Page } from "@playwright/test";
import path from "node:path";
import { mockConnectionApi } from "./helpers/mockConnectionApi";

const OUT_DIR = path.resolve(__dirname, "../../../docs/vision-verify");

async function applyTheme(page: Page, theme: "light" | "dark") {
  await page.addInitScript((t) => {
    localStorage.setItem("odoo-custom-theme", t);
    document.documentElement.classList.toggle("dark", t === "dark");
  }, theme);
}

const HARNESS_TARGETS = [
  { path: "/e2e/tokens", testId: "tokens-page", name: "tokens" },
  { path: "/e2e/kit", testId: "kit-page", name: "kit" },
] as const;

const SHELL_TARGET = {
  path: "/connections/demo-conn",
  testId: "connection-overview",
  shellTestId: "app-shell",
  name: "shell-overview",
} as const;

const PRIMARY_TARGETS = [
  { path: "/connections/demo-conn/journal", testId: "journal-page", name: "journal" },
  { path: "/connections/demo-conn/bulk-suite", testId: "bulk-suite-page", name: "bulk-suite" },
  { path: "/connections/demo-conn/reminders", testId: "reminders-page", name: "reminders" },
  { path: "/connections/demo-conn/id-generator", testId: "id-generator-page", name: "id-generator" },
  { path: "/connections/demo-conn/reports", testId: "reports-page", name: "reports" },
  { path: "/connections/demo-conn/housekeeping", testId: "housekeeping-page", name: "housekeeping" },
  { path: "/connections/demo-conn/approvals", testId: "approvals-page", name: "approvals" },
  { path: "/connections/demo-conn/import", testId: "import-page", name: "import" },
] as const;

test.describe("REM-12 vision-verify sweep", () => {
  test.describe.configure({ timeout: 90_000 });

  for (const theme of ["light", "dark"] as const) {
    for (const target of HARNESS_TARGETS) {
      test(`capture ${target.name} ${theme}`, async ({ page }) => {
        await applyTheme(page, theme);
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto(target.path);
        await expect(page.getByTestId(target.testId)).toBeVisible();
        await page.screenshot({
          path: path.join(OUT_DIR, `${target.name}-${theme}.png`),
          fullPage: true,
        });
      });
    }

    test(`capture shell overview ${theme}`, async ({ page }) => {
      await applyTheme(page, theme);
      await mockConnectionApi(page);
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(SHELL_TARGET.path);
      await expect(page.getByTestId(SHELL_TARGET.shellTestId)).toBeVisible({ timeout: 45_000 });
      await expect(page.getByTestId(SHELL_TARGET.testId)).toBeVisible({ timeout: 30_000 });
      await page.screenshot({
        path: path.join(OUT_DIR, `${SHELL_TARGET.name}-${theme}.png`),
        fullPage: true,
      });
    });

    for (const target of PRIMARY_TARGETS) {
      test(`capture ${target.name} ${theme}`, async ({ page }) => {
        await applyTheme(page, theme);
        await mockConnectionApi(page);
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto(target.path);
        await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 45_000 });
        await expect(page.getByTestId(target.testId)).toBeVisible({ timeout: 30_000 });
        await page.screenshot({
          path: path.join(OUT_DIR, `${target.name}-${theme}.png`),
          fullPage: true,
        });
      });
    }
  }
});
