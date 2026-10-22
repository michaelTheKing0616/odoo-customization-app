import { expect, test, type Locator, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
import path from "node:path";

/** UI-F11 evidence: virtualized DataTable / BulkResultTable on the data-table harness, keyboard, axe, desktop and 390 shots. */
const OUT_DIR = path.resolve(__dirname, "../../../docs/vision-verify/UI-F11");
const VIEWPORTS = [
  { suffix: "desktop", width: 1440, height: 900 },
  { suffix: "390", width: 390, height: 844 },
] as const;
const TABLE_SCOPES = ["data-table-large", "data-table-bulk", "data-table-small"] as const;
const MAX_TABS = 40;
const ROWS_DOWN = 40;

/** Runs axe on the whole harness page (recorded only) and on the three table cards (returned for the gate). */
async function seriousAxeViolations(page: Page, label: string) {
  const record = async (scope: "page" | "tables") => {
    let builder = new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .exclude('[data-testid="app-topbar"]')
      .disableRules(["document-title", "html-has-lang", "label"]);
    if (scope === "tables") {
      for (const id of TABLE_SCOPES) builder = builder.include(`[data-testid="${id}"]`);
    }
    const results = await builder.analyze();
    fs.appendFileSync(
      path.join(OUT_DIR, "axe-results.jsonl"),
      `${JSON.stringify({
        label,
        scope,
        violations: results.violations.map((v) => ({
          id: v.id,
          impact: v.impact,
          nodes: v.nodes.length,
          targets: v.nodes.map((node) => node.target.join(" ")),
        })),
      })}\n`,
    );
    return results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  };
  await record("page");
  return record("tables");
}

async function openHarness(page: Page, width: number, height: number) {
  await page.setViewportSize({ width, height });
  await page.goto("/e2e/data-table");
  await expect(page.getByTestId("data-table-page")).toBeVisible({ timeout: 45_000 });
}

async function tabToGrid(page: Page, scope: string) {
  for (let i = 0; i < MAX_TABS; i += 1) {
    await page.keyboard.press("Tab");
    const inScope = await page.evaluate(
      (id) =>
        document.activeElement?.getAttribute("role") === "grid" &&
        !!document.activeElement.closest(`[data-testid="${id}"]`),
      scope,
    );
    if (inScope) return;
  }
  throw new Error(`Tab never reached the grid in ${scope}`);
}

function renderedRows(card: Locator) {
  return card.locator("tbody tr:not([aria-hidden])");
}

test.describe("UI-F11 virtualized tables — keyboard, axe and vision evidence", () => {
  test.describe.configure({ timeout: 120_000 });

  test.beforeAll(() => {
    fs.mkdirSync(OUT_DIR, { recursive: true });
  });

  for (const vp of VIEWPORTS) {
    test(`5,000 rows virtualize; arrows reach rows past the viewport; header stays pinned @${vp.suffix}`, async ({ page }) => {
      await openHarness(page, vp.width, vp.height);
      const card = page.getByTestId("data-table-large");
      const grid = card.getByRole("grid");
      const scroller = card.getByTestId("data-table-scroll");

      await expect(scroller).toBeVisible();
      await expect(grid).toHaveAttribute("aria-rowcount", "5001");
      await expect(grid.locator("thead tr")).toHaveAttribute("aria-rowindex", "1");
      expect(await renderedRows(card).count()).toBeLessThan(100);

      await card.scrollIntoViewIfNeeded();
      await tabToGrid(page, "data-table-large");
      await expect(grid).toBeFocused();
      await expect(scroller).not.toHaveCSS("box-shadow", "none");

      for (let i = 0; i < ROWS_DOWN; i += 1) await page.keyboard.press("ArrowDown");
      await expect(grid).toHaveAttribute("aria-activedescendant", `data-table-row-f-${ROWS_DOWN}`);
      const active = card.locator(`#data-table-row-f-${ROWS_DOWN}`);
      await expect(active).toHaveAttribute("data-active", "true");
      await expect(active).toHaveAttribute("aria-rowindex", String(ROWS_DOWN + 2));
      await expect(active).not.toHaveCSS("background-color", "rgba(0, 0, 0, 0)");

      const scrollBox = (await scroller.boundingBox())!;
      const headBox = (await grid.locator("thead").boundingBox())!;
      const rowBox = (await active.boundingBox())!;
      expect(await scroller.evaluate((el) => el.scrollTop)).toBeGreaterThan(0);
      expect(Math.abs(headBox.y - scrollBox.y)).toBeLessThanOrEqual(2);
      expect(rowBox.y).toBeGreaterThanOrEqual(headBox.y + headBox.height - 1);
      expect(rowBox.y + rowBox.height).toBeLessThanOrEqual(scrollBox.y + scrollBox.height + 1);
      expect(await card.locator("tr").evaluateAll((rows) => rows.filter((r) => r.getAnimations().length > 0).length)).toBe(0);

      await page.screenshot({ path: path.join(OUT_DIR, `data-table-keyboard-${vp.suffix}.png`) });
      const serious = await seriousAxeViolations(page, `/e2e/data-table (row ${ROWS_DOWN} active by keyboard) @${vp.suffix}`);
      expect(serious, `axe violations: ${JSON.stringify(serious, null, 2)}`).toEqual([]);

      const sizeHeader = grid.getByRole("columnheader", { name: /Size/ });
      await expect(sizeHeader).toHaveAttribute("aria-sort", "none");
      await sizeHeader.getByRole("button").click();
      await expect(sizeHeader).toHaveAttribute("aria-sort", "ascending");
      await expect(grid).toHaveAttribute("aria-rowcount", "5001");
    });

    test(`bulk result virtualizes at 120 records and drops to a plain table when filtered @${vp.suffix}`, async ({ page }) => {
      await page.emulateMedia({ reducedMotion: "reduce" });
      await openHarness(page, vp.width, vp.height);
      const bulk = page.getByTestId("data-table-bulk");
      await expect(bulk.getByTestId("data-table-scroll")).toBeVisible();
      await expect(bulk.getByRole("grid")).toHaveAttribute("aria-rowcount", "121");
      const bulkScroller = bulk.getByTestId("data-table-scroll");
      await bulkScroller.evaluate((el) => el.scrollTo({ top: el.scrollHeight }));
      const lastRow = bulk.locator("tbody tr", { hasText: "Partner 120" });
      await expect(lastRow).toBeVisible();
      await expect(lastRow).toHaveAttribute("aria-rowindex", "121");

      await bulk.getByRole("button", { name: "Failed", exact: true }).click();
      await expect(bulk.getByTestId("data-table-scroll")).toHaveCount(0);
      await expect(renderedRows(bulk)).toHaveCount(12);
      await expect(bulk.getByRole("grid")).toHaveAttribute("aria-rowcount", "13");

      const small = page.getByTestId("data-table-small");
      await expect(small.getByTestId("data-table-scroll")).toHaveCount(0);
      await expect(renderedRows(small)).toHaveCount(12);
      await expect(small.getByRole("grid")).toHaveAttribute("aria-rowcount", "13");

      await bulk.scrollIntoViewIfNeeded();
      await page.screenshot({ path: path.join(OUT_DIR, `data-table-bulk-filtered-${vp.suffix}.png`) });
      const serious = await seriousAxeViolations(page, `/e2e/data-table (bulk filtered to Failed, reduced motion) @${vp.suffix}`);
      expect(serious, `axe violations: ${JSON.stringify(serious, null, 2)}`).toEqual([]);
    });
  }
});
