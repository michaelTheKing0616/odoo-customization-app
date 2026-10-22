// UI-S-20 vision capture: node capture.cjs <baseUrl> <outDir> <prefix> [states...]
// Run with NODE_PATH=apps/web/node_modules so @playwright/test resolves.
const { chromium } = require("@playwright/test");
const path = require("path");

const [, , base = "http://127.0.0.1:3002", outDir = ".", prefix = "after", ...rest] = process.argv;
const states = rest.length ? rest : ["brief"];
const viewports = [
  { name: "desktop", width: 1440, height: 900, isMobile: false },
  { name: "mobile", width: 390, height: 844, isMobile: true },
];

(async () => {
  const browser = await chromium.launch();
  for (const vp of viewports) {
    const ctx = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: 2,
      isMobile: vp.isMobile,
      hasTouch: vp.isMobile,
    });
    const page = await ctx.newPage();
    for (const state of states) {
      const url = `${base}/e2e/studio${state === "brief" ? "" : `?state=${state}`}`;
      await page.goto(url, { waitUntil: "networkidle", timeout: 120000 });
      await page.getByTestId("studio-page").waitFor({ timeout: 60000 });
      await page.waitForTimeout(600);
      const file = path.join(outDir, `${prefix}-${state}-${vp.name}.png`);
      await page.screenshot({ path: file, fullPage: true, animations: "disabled" });
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      console.log(`${file} overflowX=${overflow}`);
    }
    await ctx.close();
  }
  await browser.close();
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
