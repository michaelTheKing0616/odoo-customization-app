import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
import path from "node:path";

/** UI-F05 evidence: Base UI tabs on the kit harness, keyboard selection, axe, desktop and 390 shots. */
const OUT_DIR = path.resolve(__dirname, "../../../docs/vision-verify/UI-F05");
const VIEWPORTS = [
  { suffix: "desktop", width: 1440, height: 900 },
  { suffix: "390", width: 390, height: 844 },
] as const;
const MAX_TABS = 40;

/**
 * Runs axe on the whole kit page (recorded only) and on the tabs subtree (returned for the gate).
 * The kit page renders every kit family, so page-level hits outside the tabs belong to other cards.
 */
async function seriousAxeViolations(page: Page, label: string) {
  const record = async (scope: "page" | "tabs") => {
    let builder = new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .exclude('[data-testid="app-topbar"]')
      .disableRules(["document-title", "html-has-lang", "label"]);
    if (scope === "tabs") builder = builder.include('[data-testid="tabs"]');
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
  return record("tabs");
}

async function openKit(page: Page, width: number, height: number) {
  await page.setViewportSize({ width, height });
  await page.goto("/e2e/kit");
  await expect(page.getByTestId("kit-page")).toBeVisible({ timeout: 45_000 });
  const tabs = page.getByTestId("tabs");
  await tabs.scrollIntoViewIfNeeded();
  return tabs;
}

async function tabToTab(page: Page, name: string) {
  for (let i = 0; i < MAX_TABS; i += 1) {
    await page.keyboard.press("Tab");
    const focused = await page.evaluate(() => ({
      role: document.activeElement?.getAttribute("role"),
      text: document.activeElement?.textContent,
    }));
    if (focused.role === "tab" && focused.text === name) return;
  }
  throw new Error(`Tab never reached the "${name}" tab`);
}

test.describe("UI-F05 tabs — axe and vision evidence (kit harness)", () => {
  test.describe.configure({ timeout: 90_000 });

  test.beforeAll(() => {
    fs.mkdirSync(OUT_DIR, { recursive: true });
  });

  for (const vp of VIEWPORTS) {
    test(`arrow keys, Home and End select; focus ring shows; axe clean @${vp.suffix}`, async ({ page }) => {
      const tabs = await openKit(page, vp.width, vp.height);
      const tabA = tabs.getByRole("tab", { name: "Tab A" });
      const tabB = tabs.getByRole("tab", { name: "Tab B" });
      const indicator = tabs.getByTestId("tabs-indicator");

      await tabToTab(page, "Tab A");
      await expect(tabA).toHaveAttribute("aria-selected", "true");
      await expect(tabA).toHaveAttribute("tabindex", "0");
      await expect(tabB).toHaveAttribute("tabindex", "-1");
      await expect(tabA).toHaveAttribute("aria-controls", await tabs.getByRole("tabpanel").getAttribute("id") ?? "");
      await expect(indicator).toBeVisible();

      await page.keyboard.press("ArrowRight");
      await expect(tabB).toBeFocused();
      await expect(tabB).toHaveAttribute("aria-selected", "true");
      await expect(tabs.getByRole("tabpanel")).toHaveText("Tab B content");
      await expect(tabs.getByRole("tabpanel")).toHaveAttribute("aria-labelledby", (await tabB.getAttribute("id"))!);
      await expect(tabB).not.toHaveCSS("box-shadow", "none");

      const boxB = await tabB.boundingBox();
      await expect
        .poll(async () => (await indicator.boundingBox())?.x)
        .toBeCloseTo(boxB!.x, 0);

      await page.screenshot({ path: path.join(OUT_DIR, `kit-tabs-keyboard-${vp.suffix}.png`) });
      const serious = await seriousAxeViolations(page, `/e2e/kit (tabs, Tab B selected by keyboard) @${vp.suffix}`);
      expect(serious, `axe violations: ${JSON.stringify(serious, null, 2)}`).toEqual([]);

      await page.keyboard.press("Home");
      await expect(tabA).toBeFocused();
      await expect(tabA).toHaveAttribute("aria-selected", "true");
      await page.keyboard.press("End");
      await expect(tabB).toBeFocused();
      await expect(tabB).toHaveAttribute("aria-selected", "true");
    });

    test(`reduced motion keeps the indicator opacity only @${vp.suffix}`, async ({ page }) => {
      await page.emulateMedia({ reducedMotion: "reduce" });
      const tabs = await openKit(page, vp.width, vp.height);
      await tabs.getByRole("tab", { name: "Tab B" }).click();
      const indicator = tabs.getByTestId("tabs-indicator");
      await expect(indicator).toBeVisible();
      await expect(indicator).toHaveCSS("transition-property", "opacity");
      const ms = parseFloat(await indicator.evaluate((el) => getComputedStyle(el).transitionDuration)) * 1000;
      expect(ms).toBeLessThanOrEqual(200);

      await page.screenshot({ path: path.join(OUT_DIR, `kit-tabs-reduced-${vp.suffix}.png`) });
      const serious = await seriousAxeViolations(page, `/e2e/kit (tabs, reduced motion) @${vp.suffix}`);
      expect(serious, `axe violations: ${JSON.stringify(serious, null, 2)}`).toEqual([]);
    });
  }

  test("full motion moves the indicator on transform and opacity only, under 300 ms", async ({ page }) => {
    const tabs = await openKit(page, 1440, 900);
    const indicator = tabs.getByTestId("tabs-indicator");
    await expect(indicator).toBeVisible();
    await expect(indicator).toHaveCSS("transition-property", "transform, opacity");
    const durations = (await indicator.evaluate((el) => getComputedStyle(el).transitionDuration))
      .split(",")
      .map((value) => parseFloat(value) * 1000);
    for (const ms of durations) expect(ms).toBeLessThan(300);
    const widthBefore = await indicator.evaluate((el) => getComputedStyle(el).width);
    await tabs.getByRole("tab", { name: "Tab B" }).click();
    await expect(indicator).toHaveCSS("width", widthBefore);
  });
});
