// UI-S-19 Access vision capture.
// node capture.cjs <baseUrl> <outDir> <prefix> [targets...]
// Targets: harness:<state>[:dark] (e.g. harness:legacy) or real:<variant> (real:19, real:20, real:production, real:error).
// Run with NODE_PATH=apps/web/node_modules so @playwright/test resolves.
const { chromium } = require("@playwright/test");
const path = require("path");

const [, , base = "http://127.0.0.1:3002", outDir = ".", prefix = "after", ...rest] = process.argv;
const targets = rest.length
  ? rest
  : [
      "harness:legacy",
      "harness:staged",
      "harness:odoo20",
      "harness:plan",
      "harness:empty",
      "harness:error",
      "harness:lines",
      "harness:unknown",
      "harness:staged:dark",
      "harness:plan:dark",
      "real:19",
      "real:20",
      "real:production",
    ];
const viewports = [
  { name: "desktop", width: 1440, height: 900, isMobile: false },
  { name: "mobile", width: 390, height: 844, isMobile: true },
];

const GROUPS = [
  { id: 1, name: "Internal User", full_name: "User types / Internal User", share: false },
  { id: 2, name: "User", full_name: "Sales / User: Own Documents Only", share: false },
  { id: 3, name: "Administrator", full_name: "Sales / Administrator", share: false },
  { id: 4, name: "Portal", full_name: "User types / Portal", share: true },
];
const RIGHTS = [
  { id: 7, name: "res.partner internal", model: "res.partner", model_id: 11, group_id: 1, group_name: "Internal User", perm_read: true, perm_write: true, perm_create: true, perm_unlink: false, active: true },
  { id: 8, name: "res.partner sales admin", model: "res.partner", model_id: 11, group_id: 3, group_name: "Sales / Administrator", perm_read: true, perm_write: true, perm_create: true, perm_unlink: true, active: true },
  { id: 9, name: "res.partner portal", model: "res.partner", model_id: 11, group_id: 4, group_name: "Portal", perm_read: true, perm_write: false, perm_create: false, perm_unlink: false, active: true },
];
const RULES = [
  { id: 3, name: "Own partners", model: "res.partner", model_id: 11, domain_force: "[('user_id', '=', user.id)]", group_ids: [2], perm_read: true, perm_write: true, perm_create: true, perm_unlink: true, active: true, global: false },
];
const MATRIX = {
  models: ["res.partner", "sale.order"],
  groups: GROUPS,
  cells: [
    { model: "res.partner", group_id: 1, access_id: 7, name: "res.partner internal", perm_read: true, perm_write: true, perm_create: true, perm_unlink: false, active: true },
    { model: "res.partner", group_id: 3, access_id: 8, name: "res.partner sales admin", perm_read: true, perm_write: true, perm_create: true, perm_unlink: true, active: true },
    { model: "res.partner", group_id: 4, access_id: 9, name: "res.partner portal", perm_read: true, perm_write: false, perm_create: false, perm_unlink: false, active: true },
    { model: "sale.order", group_id: 2, access_id: 21, name: "sale.order user", perm_read: true, perm_write: true, perm_create: true, perm_unlink: false, active: true },
    { model: "sale.order", group_id: 3, access_id: 22, name: "sale.order admin", perm_read: true, perm_write: true, perm_create: true, perm_unlink: true, active: true },
  ],
};

function conn(variant) {
  const major = variant === "20" ? 20 : 19;
  return {
    id: "demo-conn",
    name: "Lagos Sessions",
    url: "http://127.0.0.1:8069",
    db_name: "odoo",
    username: "admin",
    server_version: `${major}.0`,
    write_mode: variant === "production" ? "production" : "standard",
    created_at: null,
    updated_at: null,
    capabilities: {
      major,
      edition: "community",
      server_version: `${major}.0`,
      supported: ["view_inject_inherit"],
      unsupported: [],
      ga: true,
      message: "ok",
      hosting_hint: "self_hosted",
      installed_modules_sample: ["base", "web", "sale"],
    },
  };
}

async function mockApi(page, variant) {
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    const json = (body, status = 200) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (url.includes("/api/auth/status")) {
      return json({ auth_mode: "off", auth_enabled: false, active_keys: 0, env_key_configured: false, bootstrap_available: false });
    }
    if (/\/api\/connections\/demo-conn(\?|$)/.test(url)) return json(conn(variant));
    if (/\/api\/connections(\?|$)/.test(url)) return json([conn(variant)]);
    if (variant === "error" && /\/access\/(rights|groups)/.test(url)) {
      return json({ detail: "Odoo RPC error: Access Denied for ir.model.access read" }, 502);
    }
    if (/\/access\/groups/.test(url)) return json(GROUPS);
    if (/\/access\/rights/.test(url)) return json(RIGHTS);
    if (/\/access\/rules/.test(url)) return json(variant === "20" ? [] : RULES);
    if (/\/access\/matrix/.test(url)) return json(MATRIX);
    if (/\/multi-company\/guidance/.test(url)) return json({ title: "Multi-company", body: "Add x_company_id and a global rule." });
    if (/\/documents\/gate/.test(url)) return json({ available: false, message: "Documents is not installed." });
    if (/\/documents\/folder-map/.test(url)) return json({ mapping: {} });
    if (/\/client-access|\/team-grants|\/grants/.test(url)) return json([]);
    return json([]);
  });
}

(async () => {
  const browser = await chromium.launch();
  for (const vp of viewports) {
    const ctx = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: 2,
      isMobile: vp.isMobile,
      hasTouch: vp.isMobile,
    });
    for (const target of targets) {
      const page = await ctx.newPage();
      const [kind, state, theme] = target.split(":");
      let url;
      let testId;
      if (kind === "real") {
        await mockApi(page, state);
        url = `${base}/connections/demo-conn/access`;
        testId = "access-page";
      } else {
        url = `${base}/e2e/access?state=${encodeURIComponent(state)}`;
        testId = "access-harness";
      }
      await page.goto(url, { waitUntil: "networkidle", timeout: 120000 });
      await page.getByTestId(testId).waitFor({ timeout: 60000 });
      if (theme === "dark") {
        await page.evaluate(() => document.documentElement.classList.add("dark"));
      }
      // Hide the Next dev indicator so it does not cover the matrix.
      await page.addStyleTag({ content: "nextjs-portal{display:none!important}" });
      await page.waitForTimeout(900);
      const suffix = theme ? `-${theme}` : "";
      const file = path.join(outDir, `${prefix}-${kind}-${state}${suffix}-${vp.name}.png`);
      await page.screenshot({ path: file, fullPage: true, animations: "disabled" });
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      console.log(`${file} overflowX=${overflow}`);
      await page.close();
    }
    await ctx.close();
  }
  await browser.close();
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
