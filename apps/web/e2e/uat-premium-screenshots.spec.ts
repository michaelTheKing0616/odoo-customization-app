import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

const OUT_DIR = path.resolve(__dirname, "../../../docs/uat-premium/screenshots");

async function applyTheme(page: Page, theme: "light" | "dark") {
  await page.addInitScript((t) => {
    localStorage.setItem("odoo-custom-theme", t);
    document.documentElement.classList.toggle("dark", t === "dark");
  }, theme);
}

const TARGETS = [
  { path: "/e2e/designer-premium", testId: "designer-premium-harness", name: "01-designer-premium" },
  { path: "/e2e/designer?mode=form", testId: "designer-harness", name: "01b-designer-legacy-harness" },
  { path: "/e2e/overlay", testId: "overlay-harness", name: "01c-designer-overlay" },
  { path: "/e2e/automations", testId: "automations-harness", name: "02-automations" },
  { path: "/e2e/builder", testId: "builder-harness", name: "03-builder" },
  { path: "/e2e/menus", testId: "menus-harness", name: "04-menus" },
  { path: "/e2e/access", testId: "access-harness", name: "05-access" },
  { path: "/e2e/studio", testId: "studio-page", name: "06-app-studio" },
  { path: "/e2e/draft-studio", testId: "draft-studio", name: "07-draft-studio" },
  { path: "/e2e/job", testId: "job-autopilot", name: "08-job-autopilot-sandbox" },
  { path: "/e2e/job?mode=production", testId: "job-autopilot", name: "08b-job-autopilot-production-refuse" },
  { path: "/e2e/modulespec", testId: "modulespec-page", name: "09-modulespec" },
  { path: "/e2e/projects", testId: "projects-page", name: "10-projects" },
  { path: "/e2e/expert", testId: "expert-harness", name: "11-expert" },
] as const;

test.describe("Premium UX world-class UAT screenshots", () => {
  test.describe.configure({ timeout: 90_000 });

  for (const theme of ["light", "dark"] as const) {
    for (const target of TARGETS) {
      test(`capture ${target.name} ${theme}`, async ({ page }) => {
        await applyTheme(page, theme);
        await page.setViewportSize({ width: 1440, height: 1100 });
        await page.goto(target.path);
        await expect(page.getByTestId(target.testId)).toBeVisible({ timeout: 30_000 });
        await page.screenshot({
          path: path.join(OUT_DIR, `${target.name}-${theme}.png`),
          fullPage: true,
        });
      });
    }
  }
});
