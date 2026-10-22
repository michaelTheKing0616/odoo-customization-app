const { chromium } = require("@playwright/test");
(async () => {
  const b = await chromium.launch();
  for (const [name, w, h] of [["desktop", 1440, 900], ["mobile", 390, 844]]) {
    const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 2 });
    const errs = [];
    p.on("pageerror", (e) => errs.push(e.message));
    await p.goto("http://127.0.0.1:3002/e2e/draft-studio", { waitUntil: "networkidle" });
    await p.waitForTimeout(800);
    const ox = await p.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    await p.screenshot({ path: `docs/vision-verify/UI-S-20/regress-draft-studio-${name}.png`, fullPage: true });
    console.log(name, "overflowX=" + ox, "errors=" + errs.length);
  }
  await b.close();
})();
