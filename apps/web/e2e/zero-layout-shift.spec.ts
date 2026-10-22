import { test, expect } from "@playwright/test";

/** Q2 touch 144: every loading area reserves its size. Fails if layout shift (CLS) passes 0.05. */
const base = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3010";
const PAGES = ["/e2e/connect?state=empty", "/e2e/menus", "/settings", "/approvals"];

for (const path of PAGES) {
  test(`no layout shift on ${path}`, async ({ page }) => {
    await page.addInitScript(() => {
      (window as unknown as { __cls: number }).__cls = 0;
      new PerformanceObserver((list) => {
        for (const e of list.getEntries() as Array<PerformanceEntry & { value: number; hadRecentInput: boolean }>) {
          if (!e.hadRecentInput) (window as unknown as { __cls: number }).__cls += e.value;
        }
      }).observe({ type: "layout-shift", buffered: true });
    });
    await page.goto(`${base}${path}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500); // past the keystone loader's 1 s delay
    const cls = await page.evaluate(() => (window as unknown as { __cls: number }).__cls);
    expect(cls).toBeLessThan(0.05);
  });
}
