// UI-S-19 axe sweep: node axe.cjs <baseUrl>. Run with NODE_PATH=apps/web/node_modules.
const { chromium } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;
const base = process.argv[2] || "http://127.0.0.1:3002";
const states = ["legacy", "staged", "odoo20", "plan", "empty", "error", "lines", "unknown"];
(async () => {
  const b = await chromium.launch();
  let bad = 0;
  for (const theme of ["light", "dark"]) {
    const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: theme });
    const p = await ctx.newPage();
    for (const s of states) {
      await p.goto(`${base}/e2e/access?state=${s}`, { waitUntil: "networkidle" });
      await p.getByTestId("access-harness").waitFor();
      if (theme === "dark") await p.evaluate(() => document.documentElement.classList.add("dark"));
      await p.waitForTimeout(300);
      const r = await new AxeBuilder({ page: p })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .include('[data-testid="access-harness"]')
        .analyze();
      const serious = r.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
      bad += serious.length;
      console.log(`${theme} ${s}: serious=${serious.length}` + (serious.length ? " " + JSON.stringify(serious.map((v) => ({ id: v.id, n: v.nodes.slice(0, 3).map((x) => x.target.join(" ")) }))) : ""));
    }
    await ctx.close();
  }
  await b.close();
  process.exit(bad ? 1 : 0);
})();
