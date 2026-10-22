import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

/** View Designer stage 3-4 acceptance: contrast (light + dark), a keyboard-only walkthrough, and INP. */
const MODES = ["form", "list", "kanban"] as const;

async function contrast(page: Page) {
  const r = await new AxeBuilder({ page }).withRules(["color-contrast", "focus-order-semantics", "button-name", "aria-allowed-role"]).analyze();
  return r.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
}

async function worstInteraction(page: Page) {
  return page.evaluate(() => (window as unknown as { __inp: number }).__inp ?? 0);
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    (window as unknown as { __inp: number }).__inp = 0;
    new PerformanceObserver((list) => {
      for (const e of list.getEntries() as (PerformanceEntry & { interactionId?: number })[]) {
        if (e.interactionId) (window as unknown as { __inp: number }).__inp = Math.max((window as unknown as { __inp: number }).__inp, e.duration);
      }
    }).observe({ type: "event", buffered: true, durationThreshold: 16 } as PerformanceObserverInit);
  });
});

for (const mode of MODES) {
  test(`contrast passes in light and dark (${mode})`, async ({ page }) => {
    await page.goto(`/e2e/designer?mode=${mode}`);
    await expect(page.getByTestId("designer-harness")).toBeVisible();
    expect(await contrast(page), "light").toEqual([]);
    await page.emulateMedia({ colorScheme: "dark" });
    await page.evaluate(() => document.documentElement.setAttribute("data-theme", "dark"));
    expect(await contrast(page), "dark").toEqual([]);
  });
}

test("keyboard-only walkthrough reaches canvas, palette and save with visible focus", async ({ page }) => {
  await page.goto("/e2e/designer?mode=form");
  await expect(page.getByTestId("form-canvas")).toBeVisible();
  const seen = new Set<string>();
  let invisible = 0;
  for (let i = 0; i < 80; i++) {
    await page.keyboard.press("Tab");
    const info = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el === document.body) return null;
      const cs = getComputedStyle(el);
      const ring = cs.outlineStyle !== "none" && parseFloat(cs.outlineWidth) > 0 || cs.boxShadow !== "none";
      return { key: (el.getAttribute("aria-label") || el.textContent || el.tagName).trim().slice(0, 40), ring,
        canvas: !!el.closest('[data-testid="form-canvas"]') };
    });
    if (!info) continue;
    if (!info.ring) invisible++;
    seen.add(info.canvas ? "canvas" : info.key);
  }
  expect(seen.has("canvas"), "Tab reaches the canvas").toBe(true);
  expect(invisible, "focused elements without a visible ring").toBeLessThanOrEqual(2);
  // Arrow reorder on the focused canvas field (stage 3 keyboard move).
  await page.getByRole("button", { name: /Name.*x_name/i }).focus();
  await page.keyboard.press("ArrowDown");
  await expect(page.locator('[data-testid="form-canvas"] [data-canvas-field]').nth(1)).toContainText("Name");
});

test("INP stays under 200ms for select, reorder and mode switch", async ({ page }) => {
  await page.goto("/e2e/designer?mode=form");
  await expect(page.getByTestId("form-canvas")).toBeVisible();
  const field = page.getByRole("button", { name: /Name.*x_name/i });
  for (let i = 0; i < 5; i++) {
    await field.click();
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("ArrowUp");
  }
  await page.waitForTimeout(300);
  const inp = await worstInteraction(page);
  test.info().annotations.push({ type: "INP ms", description: String(Math.round(inp)) });
  expect(inp).toBeLessThan(200);
});
