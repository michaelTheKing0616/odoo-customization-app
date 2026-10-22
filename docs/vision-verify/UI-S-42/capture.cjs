// UI-S-42 Billing vision capture.
// Usage: NODE_PATH=apps/web/node_modules node docs/vision-verify/UI-S-42/capture.cjs <baseUrl> <outDir> <prefix> [states...]
// Uses the /e2e/billing?state=... harness (NEXT_PUBLIC_E2E=1). Prefix "before" shoots the legacy page.
// Stop YOUR mirror after capture.
const { chromium } = require("@playwright/test");
const path = require("path");
const fs = require("fs");

const [, , base = "http://127.0.0.1:3142", outDir = ".", prefix = "after", ...rest] = process.argv;
const ALL = [
  "trial",
  "active",
  "free",
  "choose",
  "past-due",
  "internal",
  "upgraded",
  "portal-error",
  "at-limit",
  "loading",
  "empty",
  "error",
];
const states = rest.length ? rest : ALL;
const viewports = [
  { name: "desktop", width: 1440, height: 900, isMobile: false },
  { name: "narrow", width: 390, height: 844, isMobile: true },
];

(async () => {
  const browser = await chromium.launch();
  const report = [];
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
      const url = `${base}/e2e/billing?state=${encodeURIComponent(state)}`;
      await page.goto(url, { waitUntil: "load", timeout: 240000 });
      if (prefix !== "before") await page.getByTestId("billing-page").waitFor({ timeout: 60000 });
      if (vp.isMobile) {
        const toggle = page.getByRole("button", { name: /collapse sidebar/i });
        if (await toggle.count()) await toggle.first().click().catch(() => {});
      }
      // Hide the Next dev indicator so it does not sit on the content.
      await page.addStyleTag({ content: "nextjs-portal{display:none!important}" }).catch(() => {});
      await page.waitForTimeout(500);
      const file = path.join(outDir, `${prefix}-${state}-${vp.name}.png`);
      await page.screenshot({ path: file, fullPage: true, animations: "disabled" });
      const m = await page.evaluate(() => {
        const root = document.querySelector('[data-testid="billing-page"]');
        const primaries = root ? root.querySelectorAll("button.bg-accent, a.bg-accent").length : 0;
        const text = root ? root.innerText : document.body.innerText;
        return {
          overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          primaries,
          emDash: /[\u2014\u2013]/.test(text),
        };
      });
      report.push({ file: path.basename(file), ...m });
      console.log(`${file} overflowX=${m.overflowX} tealPrimaries=${m.primaries} emDash=${m.emDash}`);
      await ctx.close();
    }
  }
  if (prefix !== "before" && states.includes("active")) {
    // Dark proof shot for the paid steady state.
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, reducedMotion: "reduce", colorScheme: "dark" });
    const page = await ctx.newPage();
    await page.addInitScript(() => {
      try { localStorage.setItem("theme", "dark"); } catch {}
    });
    await page.goto(`${base}/e2e/billing?state=active`, { waitUntil: "load", timeout: 240000 });
    await page.evaluate(() => document.documentElement.classList.add("dark"));
    await page.addStyleTag({ content: "nextjs-portal{display:none!important}" }).catch(() => {});
    await page.waitForTimeout(400);
    const file = path.join(outDir, `${prefix}-active-dark.png`);
    await page.screenshot({ path: file, fullPage: true, animations: "disabled" });
    console.log(file);
    await ctx.close();
  }
  const desk = path.join(outDir, `${prefix}-active-desktop.png`);
  const narr = path.join(outDir, `${prefix}-trial-narrow.png`);
  if (prefix === "after") {
    if (fs.existsSync(desk)) fs.copyFileSync(desk, path.join(outDir, "desktop.png"));
    if (fs.existsSync(narr)) fs.copyFileSync(narr, path.join(outDir, "narrow.png"));
  }
  fs.writeFileSync(path.join(outDir, `${prefix}-metrics.json`), JSON.stringify(report, null, 2));
  await browser.close();
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
