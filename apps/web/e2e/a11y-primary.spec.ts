import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mockConnectionApi } from "./helpers/mockConnectionApi";

async function expectNoSeriousAxeViolations(page: Page, label: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .exclude('[data-testid="app-topbar"]')
    .disableRules(["document-title", "html-has-lang", "label"])
    .analyze();
  const serious = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  expect(serious, `${label} axe violations: ${JSON.stringify(serious, null, 2)}`).toEqual([]);
}

/** Eight UIX-4c kit-migrated operate/govern pages (mocked API). */
const PRIMARY_PAGES = [
  { path: "/connections/demo-conn/journal", testId: "journal-page", label: "Journal" },
  { path: "/connections/demo-conn/bulk-suite", testId: "bulk-suite-page", label: "Bulk Suite" },
  { path: "/connections/demo-conn/reminders", testId: "reminders-page", label: "Reminders" },
  { path: "/connections/demo-conn/id-generator", testId: "id-generator-page", label: "ID Generator" },
  { path: "/connections/demo-conn/reports", testId: "reports-page", label: "Reports" },
  { path: "/connections/demo-conn/housekeeping", testId: "housekeeping-page", label: "Housekeeping" },
  { path: "/connections/demo-conn/approvals", testId: "approvals-page", label: "Approvals" },
  { path: "/connections/demo-conn/import", testId: "import-page", label: "Import" },
] as const;

test.describe("UIX-5 a11y — primary pages (mocked API)", () => {
  test.describe.configure({ timeout: 90_000 });

  test.beforeEach(async ({ page }) => {
    await mockConnectionApi(page);
  });

  for (const { path, testId, label } of PRIMARY_PAGES) {
    test(`${label} renders and passes axe`, async ({ page }) => {
      await page.goto(path);
      await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 45_000 });
      await expect(page.getByTestId(testId)).toBeVisible({ timeout: 30_000 });
      await expectNoSeriousAxeViolations(page, label);
    });
  }
});
