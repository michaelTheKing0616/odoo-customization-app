// UI-S-52 Bots / Bridge pass (Contract Studio) vision capture.
// Usage: NODE_PATH=apps/web/node_modules node docs/vision-verify/UI-S-52/capture.cjs <baseUrl> <outDir> <prefix> [states...]
// Uses the /e2e/bridge-contract?state=... harness (same component as /bridge/contracts/new).
const { chromium } = require("@playwright/test");
const path = require("path");

const [, , base = "http://127.0.0.1:3052", outDir = ".", prefix = "after", ...rest] = process.argv;
const ALL = ["empty", "two-way", "invalid", "validating", "passed", "refused", "error", "risk", "request"];
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
        reducedMotion: "reduce",
        colorScheme: "light",
      });
      const page = await ctx.newPage();
      await page.goto(`${base}/e2e/bridge-contract?state=${encodeURIComponent(state)}`, {
        waitUntil: "networkidle",
        timeout: 120000,
      });
      await page.getByTestId("bridge-contract-page").waitFor({ timeout: 60000 });
      await page.waitForTimeout(300);
      const file = path.join(outDir, `${prefix}-${state}-${vp.name}.png`);
      await page.screenshot({ path: file, fullPage: true, animations: "disabled" });
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      console.log(`${file} overflowX=${overflow}`);
      await ctx.close();
    }
  }
  // Dark mode spot check.
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, colorScheme: "dark", reducedMotion: "reduce" });
  const page = await ctx.newPage();
  await page.goto(`${base}/e2e/bridge-contract?state=refused`, { waitUntil: "networkidle", timeout: 120000 });
  await page.getByTestId("bridge-contract-page").waitFor();
  await page.waitForTimeout(300);
  const dark = path.join(outDir, `${prefix}-refused-dark.png`);
  await page.screenshot({ path: dark, fullPage: true, animations: "disabled" });
  console.log(`${dark} dark=${await page.evaluate(() => document.documentElement.classList.contains("dark"))}`);
  await ctx.close();
  await browser.close();
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
