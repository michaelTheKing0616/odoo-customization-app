// UI-S-50 Plan inbox vision capture.
// Usage: NODE_PATH=apps/web/node_modules node docs/vision-verify/UI-S-50/capture.cjs <baseUrl> <outDir> <prefix> [states...]
// Uses the /e2e/plan-inbox?state=… harness (NEXT_PUBLIC_E2E=1). Stop YOUR mirror after capture.
const { chromium } = require("@playwright/test");
const fs = require("fs");
const path = require("path");

const [, , base = "http://127.0.0.1:3070", outDir = ".", prefix = "after", ...rest] = process.argv;
const ALL = [
  "idle",
  "loading",
  "empty",
  "error",
  "r1",
  "r3",
  "r3-confirm",
  "r4",
  "r4-self",
  "stale",
  "expired",
  "approved",
  "not-found",
  "signed-out",
  "forbidden",
];
const states = rest.length ? rest : ALL;
const viewports = [
  { name: "desktop", width: 1440, height: 900, isMobile: false },
  { name: "narrow", width: 390, height: 844, isMobile: true },
];
const themes = (process.env.UIS50_THEMES || "light").split(",");

(async () => {
  const browser = await chromium.launch();
  const report = [];
  for (const theme of themes) {
    for (const vp of viewports) {
      for (const state of states) {
        const ctx = await browser.newContext({
          viewport: { width: vp.width, height: vp.height },
          deviceScaleFactor: 2,
          isMobile: vp.isMobile,
          hasTouch: vp.isMobile,
          reducedMotion: "reduce",
          colorScheme: theme === "dark" ? "dark" : "light",
        });
        const page = await ctx.newPage();
        if (theme === "dark") {
          await page.addInitScript(() => {
            try {
              localStorage.setItem("theme", "dark");
            } catch {}
            document.documentElement.classList.add("dark");
          });
        }
        await page.goto(`${base}/e2e/plan-inbox?state=${encodeURIComponent(state)}`, {
          waitUntil: "networkidle",
          timeout: 120000,
        });
        await page.getByTestId("approvals-inbox-page").waitFor({ timeout: 60000 });
        if (state === "r3" && vp.isMobile) {
          // Narrow R3: open the exact-ops disclosure so the full diff is in the shot.
          const ops = page.getByTestId("plan-card-ops");
          if (await ops.count()) await ops.locator("summary").click();
        }
        await page.waitForTimeout(300);
        const suffix = theme === "light" ? "" : `-${theme}`;
        const file = path.join(outDir, `${prefix}-${state}-${vp.name}${suffix}.png`);
        await page.screenshot({ path: file, fullPage: true, animations: "disabled" });
        const metrics = await page.evaluate(() => ({
          overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          primaries: document.querySelectorAll("button.bg-accent").length,
          sections: document.querySelectorAll('[data-testid="plan-card-section"]').length,
          slots: document.querySelectorAll('[data-testid="plan-card-slot"]').length,
          dashes: /[\u2014\u2013]/.test(document.body.innerText),
        }));
        report.push({ state, viewport: vp.name, theme, file: path.basename(file), ...metrics });
        console.log(`${path.basename(file)} ${JSON.stringify(metrics)}`);
        await ctx.close();
      }
    }
  }
  fs.writeFileSync(path.join(outDir, `${prefix}-metrics.json`), JSON.stringify(report, null, 2));
  const desk = path.join(outDir, `${prefix}-r3-desktop.png`);
  const narr = path.join(outDir, `${prefix}-r3-narrow.png`);
  if (fs.existsSync(desk)) fs.copyFileSync(desk, path.join(outDir, "desktop.png"));
  if (fs.existsSync(narr)) fs.copyFileSync(narr, path.join(outDir, "narrow.png"));
  await browser.close();
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
