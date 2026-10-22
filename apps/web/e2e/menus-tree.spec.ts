import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/** UI-S-13 Menus: APG tree keyboard model, drag refusal with a reason, staged move then Save the menu. */
test.describe("UI-S-13 menus tree (harness)", () => {
  test.describe.configure({ timeout: 90_000 });

  test("keyboard walks the tree with aria-expanded", async ({ page }) => {
    await page.goto("/e2e/menus");
    const tree = page.getByRole("tree", { name: /Menu tree/ });
    await expect(tree).toBeVisible({ timeout: 45_000 });
    const visitors = page.getByRole("treeitem", { name: "Visitors" });
    await expect(visitors).toHaveAttribute("tabindex", "0");
    await visitors.focus();
    await page.keyboard.press("ArrowLeft");
    await expect(visitors).toHaveAttribute("aria-expanded", "false");
    await page.keyboard.press("ArrowRight");
    await expect(visitors).toHaveAttribute("aria-expanded", "true");
    await page.keyboard.press("ArrowLeft");
    await page.keyboard.press("ArrowLeft");
    await expect(page.getByRole("treeitem", { name: "Front desk" })).toBeFocused();
    await page.keyboard.press("End");
    const fleet = page.getByRole("treeitem", { name: "Fleet" });
    await expect(fleet).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(fleet).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("heading", { level: 2, name: "Fleet" })).toBeVisible();
  });

  test("dragging a menu into its own branch is refused with a reason", async ({ page }) => {
    await page.goto("/e2e/menus");
    await expect(page.getByTestId("menu-row-1")).toBeVisible({ timeout: 45_000 });
    await page.getByTestId("menu-row-1").dragTo(page.getByTestId("menu-row-6"));
    await expect(page.getByTestId("menus-drop-refusal-title")).toHaveText(
      "Can't move “Front desk” under “Badge types”",
    );
    await expect(page.getByTestId("menus-drop-refusal-why")).toContainText("Odoo refuses recursive menus");
    await expect(page.getByTestId("menus-row-staged")).toHaveCount(0);
  });

  test("a valid drag stages the move and Save the menu writes it", async ({ page }) => {
    await page.goto("/e2e/menus");
    await expect(page.getByTestId("menu-row-6")).toBeVisible({ timeout: 45_000 });
    await page.getByTestId("menu-row-6").dragTo(page.getByTestId("menu-row-2"));
    await expect(page.getByTestId("menus-row-staged")).toHaveText("Unsaved move");
    await expect(page.getByTestId("menus-detail-changes")).toHaveText("1 change: parent");
    await expect(page.getByTestId("menus-detail-moved")).toContainText("Moving from Configuration to Visitors");
    await page.getByTestId("menus-detail-save").click();
    await expect(page.getByTestId("menus-notice")).toHaveText("Saved “Badge types” to Odoo.");
    await expect(page.getByTestId("menus-row-staged")).toHaveCount(0);
    await expect(page.getByTestId("menu-row-6")).toHaveAttribute("aria-level", "3");
  });

  for (const state of ["default", "new", "staged", "refused", "empty", "loading", "error", "blocked"]) {
    test(`axe has no serious issues: ${state}`, async ({ page }) => {
      await page.goto(`/e2e/menus?state=${state}`);
      await expect(page.getByTestId("menus-harness")).toBeVisible({ timeout: 45_000 });
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .include('[data-testid="menus-harness"]')
        .analyze();
      const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
      expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
    });
  }
});
