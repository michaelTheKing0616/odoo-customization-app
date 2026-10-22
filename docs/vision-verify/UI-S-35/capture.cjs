// UI-S-35 Script Runner vision capture.
// Usage: NODE_PATH=apps/web/node_modules node docs/vision-verify/UI-S-35/capture.cjs <baseUrl> <outDir> <prefix> [states...]
// Prefers /e2e/script-runner?state=… harness (NEXT_PUBLIC_E2E=1). Stop YOUR mirror after capture.
const { chromium } = require("@playwright/test");
const path = require("path");

const [, , base = "http://127.0.0.1:3065", outDir = ".", prefix = "after", ...rest] = process.argv;
const ALL = ["empty", "idle", "confirm", "running", "succeeded", "failed", "observer", "error"];
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
      });
      const page = await ctx.newPage();
      const url = `${base}/e2e/script-runner?state=${encodeURIComponent(state)}`;
      await page.goto(url, { waitUntil: "networkidle", timeout: 120000 });
      await page.getByTestId("script-runner-page").waitFor({ timeout: 60000 });
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
  // Canonical aliases
  const fs = require("fs");
  const desk = path.join(outDir, `${prefix}-empty-desktop.png`);
  const narr = path.join(outDir, `${prefix}-confirm-narrow.png`);
  if (fs.existsSync(desk)) fs.copyFileSync(desk, path.join(outDir, "desktop.png"));
  if (fs.existsSync(narr)) fs.copyFileSync(narr, path.join(outDir, "narrow.png"));
  await browser.close();
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
