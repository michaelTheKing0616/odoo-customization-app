import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
import path from "node:path";
import { mockConnectionApi } from "./helpers/mockConnectionApi";

/** UI-F06 evidence: Base UI tooltip open on the expert harness, axe in the open state, desktop and 390 shots. */
const OUT_DIR = path.resolve(__dirname, "../../../docs/vision-verify/UI-F06");
const VIEWPORTS = [
  { suffix: "desktop", width: 1440, height: 900 },
  { suffix: "390", width: 390, height: 844 },
] as const;
const MAX_TABS = 40;

async function seriousAxeViolations(page: Page, label: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .exclude('[data-testid="app-topbar"]')
    .disableRules(["document-title", "html-has-lang", "label"])
    .analyze();
  fs.appendFileSync(
    path.join(OUT_DIR, "axe-results.jsonl"),
    `${JSON.stringify({ label, violations: results.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length })) })}\n`,
  );
  return results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
}

async function openHarness(page: Page, width: number, height: number) {
  await page.setViewportSize({ width, height });
  await mockConnectionApi(page);
  await page.goto("/e2e/expert");
  await expect(page.getByTestId("expert-harness")).toBeVisible({ timeout: 45_000 });
  return page.getByTestId("explain-this");
}

async function tabTo(page: Page, testId: string) {
  for (let i = 0; i < MAX_TABS; i += 1) {
    await page.keyboard.press("Tab");
    const focused = await page.evaluate(() => document.activeElement?.getAttribute("data-testid"));
    if (focused === testId) return;
  }
  throw new Error(`Tab never reached [data-testid="${testId}"]`);
}

test.describe("UI-F06 tooltip — axe and vision evidence (expert harness)", () => {
  test.describe.configure({ timeout: 90_000 });

  test.beforeAll(() => {
    fs.mkdirSync(OUT_DIR, { recursive: true });
  });

  for (const vp of VIEWPORTS) {
    test(`keyboard focus opens, Escape closes, axe clean while open @${vp.suffix}`, async ({ page }) => {
      const trigger = await openHarness(page, vp.width, vp.height);
      await tabTo(page, "explain-this");

      const tooltip = page.getByRole("tooltip");
      await expect(tooltip).toBeVisible();
      await expect(tooltip).toHaveCSS("opacity", "1");
      const tooltipId = await tooltip.getAttribute("id");
      expect(tooltipId).toBeTruthy();
      await expect(trigger).toHaveAttribute("aria-describedby", tooltipId!);

      await page.screenshot({ path: path.join(OUT_DIR, `expert-tooltip-keyboard-${vp.suffix}.png`) });
      const serious = await seriousAxeViolations(page, `/e2e/expert (tooltip open, keyboard) @${vp.suffix}`);
      expect(serious, `axe violations: ${JSON.stringify(serious, null, 2)}`).toEqual([]);

      await page.keyboard.press("Escape");
      await expect(tooltip).toHaveCount(0);
      await expect(trigger).not.toHaveAttribute("aria-describedby", /.+/);
      await expect(trigger).toBeFocused();
    });

    test(`hover opens with reduced motion as opacity only @${vp.suffix}`, async ({ page }) => {
      await page.emulateMedia({ reducedMotion: "reduce" });
      const trigger = await openHarness(page, vp.width, vp.height);
      await trigger.hover();

      const tooltip = page.getByRole("tooltip");
      await expect(tooltip).toBeVisible();
      await expect(tooltip).toHaveCSS("opacity", "1");
      await expect(tooltip).toHaveCSS("transition-property", "opacity");
      await expect(tooltip).toHaveCSS("transform", "none");

      await page.screenshot({ path: path.join(OUT_DIR, `expert-tooltip-hover-reduced-${vp.suffix}.png`) });
      const serious = await seriousAxeViolations(page, `/e2e/expert (tooltip open, hover, reduced motion) @${vp.suffix}`);
      expect(serious, `axe violations: ${JSON.stringify(serious, null, 2)}`).toEqual([]);
    });
  }

  test("full motion animates transform and opacity only, under 300 ms", async ({ page }) => {
    const trigger = await openHarness(page, 1440, 900);
    await trigger.hover();
    const tooltip = page.getByRole("tooltip");
    await expect(tooltip).toBeVisible();
    await expect(tooltip).toHaveCSS("transition-property", "transform, opacity");
    const durations = (await tooltip.evaluate((el) => getComputedStyle(el).transitionDuration))
      .split(",")
      .map((value) => parseFloat(value) * 1000);
    for (const ms of durations) expect(ms).toBeLessThan(300);
  });
});
