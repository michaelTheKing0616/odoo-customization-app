// UI-S-26 Bulk data import vision capture.
// Usage: NODE_PATH=apps/web/node_modules node docs/vision-verify/UI-S-26/capture.cjs <baseUrl> <outDir> <prefix> [states...]
// Prefers /e2e/import?state=… harness (NEXT_PUBLIC_E2E=1). Falls back note if harness disabled.
const { chromium } = require("@playwright/test");
const path = require("path");

const [, , base = "http://127.0.0.1:3010", outDir = ".", prefix = "after", ...rest] = process.argv;
const ALL = ["empty", "map", "dry-run", "partial", "progress", "error"];
const states = rest.length ? rest : ALL;
const viewports = [
  { name: "desktop", width: 1440, height: 900, isMobile: false },
  { name: "narrow", width: 390, height: 844, isMobile: true },
];

(async () => {
  const browser = await chromium.launch();
  for (const vp of viewports) {
    for (const state of states) {
      const ctx = await browser.newContext({
        viewport: { width: vp.width, height: vp.height },
        deviceScaleFactor: 2,
        isMobile: vp.isMobile,
        hasTouch: vp.isMobile,
      });
      const page = await ctx.newPage();
      const url = `${base}/e2e/import?state=${encodeURIComponent(state)}`;
      await page.goto(url, { waitUntil: "networkidle", timeout: 120000 });
      await page.getByTestId("import-page").waitFor({ timeout: 60000 });
      if (vp.isMobile) {
        const toggle = page.getByRole("button", { name: /collapse sidebar/i });
        if (await toggle.count()) await toggle.first().click().catch(() => {});
      }
      await page.waitForTimeout(400);
      const file = path.join(outDir, `${prefix}-${state}-${vp.name}.png`);
      await page.screenshot({ path: file, fullPage: true, animations: "disabled" });
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      console.log(`${file} overflowX=${overflow}`);
      await ctx.close();
    }
  }
  await browser.close();
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
