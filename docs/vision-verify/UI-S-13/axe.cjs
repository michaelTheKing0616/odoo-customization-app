// UI-S-13 axe sweep: node axe.cjs <baseUrl>. Run from apps/web with NODE_PATH=$PWD/node_modules.
const { chromium } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;
const base = process.argv[2] || "http://127.0.0.1:3002";
const states = ["default", "new", "staged", "refused", "empty", "loading", "error", "blocked"];
(async () => {
  const b = await chromium.launch();
  let bad = 0;
  for (const theme of ["light", "dark"]) {
    const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: theme });
    const p = await ctx.newPage();
    for (const s of states) {
      await p.goto(`${base}/e2e/menus?state=${s}`, { waitUntil: "networkidle" });
      await p.getByTestId("menus-harness").waitFor();
      if (theme === "dark") await p.evaluate(() => document.documentElement.classList.add("dark"));
      await p.waitForTimeout(300);
      const r = await new AxeBuilder({ page: p })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .include('[data-testid="menus-harness"]')
        .analyze();
      const serious = r.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
      const minor = r.violations.filter((v) => !(v.impact === "serious" || v.impact === "critical"));
      bad += serious.length;
      console.log(
        `${theme} ${s}: serious=${serious.length} other=${minor.length}` +
          (r.violations.length
            ? " " + JSON.stringify(r.violations.map((v) => ({ id: v.id, impact: v.impact, n: v.nodes.slice(0, 3).map((x) => x.target.join(" ")) })))
            : ""),
      );
    }
    await ctx.close();
  }
  await b.close();
  process.exit(bad ? 1 : 0);
})();
