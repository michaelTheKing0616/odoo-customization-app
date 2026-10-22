// UI-S-13 Menus vision capture.
// node capture.cjs <baseUrl> <outDir> <prefix> [targets...]
// Targets: harness:<state>[:dark] or real:<variant>[:dark] or flow:<name>.
// Run from apps/web with NODE_PATH=$PWD/node_modules so @playwright/test resolves.
const { chromium } = require("@playwright/test");
const path = require("path");

const [, , base = "http://127.0.0.1:3002", outDir = ".", prefix = "after", ...rest] = process.argv;
const targets = rest.length
  ? rest
  : [
      "harness:default",
      "harness:new",
      "harness:staged",
      "harness:refused",
      "harness:empty",
      "harness:loading",
      "harness:error",
      "harness:blocked",
      "harness:default:dark",
      "harness:refused:dark",
      "real:19",
      "real:19:dark",
      "flow:drag-refused",
      "flow:drag-staged",
      "flow:keyboard",
    ];
const viewports = [
  { name: "desktop", width: 1440, height: 900, isMobile: false },
  { name: "mobile", width: 390, height: 844, isMobile: true },
];

const MENUS = [
  { id: 1, name: "Front desk", parent_id: null, action: null, action_id: null, sequence: 10, web_icon: "base,static/description/icon.png", child_count: 2, group_ids: [] },
  { id: 2, name: "Visitors", parent_id: 1, parent_name: "Front desk", action: "ir.actions.act_window,10", action_id: 10, sequence: 10, web_icon: null, child_count: 2, group_ids: [] },
  { id: 3, name: "Checked in", parent_id: 2, parent_name: "Visitors", action: "ir.actions.act_window,11", action_id: 11, sequence: 10, web_icon: null, child_count: 0, group_ids: [] },
  { id: 4, name: "Expected today", parent_id: 2, parent_name: "Visitors", action: "ir.actions.act_window,12", action_id: 12, sequence: 20, web_icon: null, child_count: 0, group_ids: [] },
  { id: 5, name: "Configuration", parent_id: 1, parent_name: "Front desk", action: null, action_id: null, sequence: 90, web_icon: null, child_count: 1, group_ids: [3] },
  { id: 6, name: "Badge types", parent_id: 5, parent_name: "Configuration", action: "ir.actions.act_window,13", action_id: 13, sequence: 10, web_icon: null, child_count: 0, group_ids: [3] },
  { id: 7, name: "Fleet", parent_id: null, action: "ir.actions.act_window,14", action_id: 14, sequence: 20, web_icon: "fleet,static/description/icon.png", child_count: 0, group_ids: [] },
];
const ACTIONS = [
  { id: 10, name: "Visitors", res_model: "x_visitor", view_mode: "list,form" },
  { id: 11, name: "Checked in", res_model: "x_visitor", view_mode: "list,form" },
  { id: 12, name: "Expected today", res_model: "x_visitor", view_mode: "list,form" },
  { id: 13, name: "Badge types", res_model: "x_badge_type", view_mode: "list,form" },
  { id: 14, name: "Vehicles", res_model: "fleet.vehicle", view_mode: "kanban,list,form" },
];
const GROUPS = [
  { id: 1, name: "Internal User", full_name: "User types / Internal User", share: false },
  { id: 3, name: "Administrator", full_name: "Front desk / Administrator", share: false },
];
const SNAPSHOTS = [
  { id: "a1b2c3d4e5f6", resource_type: "menu", resource_key: "5", label: "Menu Configuration before edit", reversible: "yes", created_at: "2026-10-05T17:40:00Z" },
  { id: "b2c3d4e5f6a1", resource_type: "action", resource_key: "13", label: "Action Badge types created", reversible: "partial", created_at: "2026-10-05T16:12:00Z" },
];

function conn() {
  return {
    id: "demo-conn", name: "Lagos Sessions", url: "http://127.0.0.1:8069", db_name: "odoo", username: "admin",
    server_version: "19.0", write_mode: "standard", created_at: null, updated_at: null,
    capabilities: { major: 19, edition: "community", server_version: "19.0", supported: ["view_inject_inherit", "list_as_list_type"], unsupported: [], ga: true, message: "ok", hosting_hint: "self_hosted", installed_modules_sample: ["base", "web"] },
  };
}

async function mockApi(page, variant) {
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (body, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (url.includes("/api/auth/status")) return json({ auth_mode: "off", auth_enabled: false, active_keys: 0, env_key_configured: false, bootstrap_available: false });
    if (/\/api\/connections\/demo-conn(\?|$)/.test(url)) return json(conn());
    if (/\/api\/connections(\?|$)/.test(url)) return json([conn()]);
    if (/menus-builder\/tree/.test(url)) {
      if (variant === "error") return json({ detail: "Odoo RPC error: Access Denied for ir.ui.menu read" }, 502);
      return json(variant === "empty" ? [] : MENUS);
    }
    if (/menus-builder\/menus\/\d+/.test(url) && method === "PATCH") {
      const id = Number(url.match(/menus\/(\d+)/)[1]);
      return json(MENUS.find((m) => m.id === id));
    }
    if (/menus-builder\/actions/.test(url)) return json(ACTIONS);
    if (/\/access\/groups/.test(url)) return json(GROUPS);
    if (/\/snapshots(\?|$)/.test(url)) return json(SNAPSHOTS);
    return json([]);
  });
}

async function dragRow(page, fromId, toSel) {
  const src = page.getByTestId(`menu-row-${fromId}`);
  const dst = typeof toSel === "string" ? page.getByTestId(toSel) : page.getByTestId(`menu-row-${toSel}`);
  // HTML5 DnD: dispatch the event sequence with a shared DataTransfer.
  const dt = await page.evaluateHandle(() => new DataTransfer());
  await src.dispatchEvent("dragstart", { dataTransfer: dt });
  await dst.dispatchEvent("dragenter", { dataTransfer: dt });
  await dst.dispatchEvent("dragover", { dataTransfer: dt });
  return { src, dst, dt };
}

(async () => {
  const browser = await chromium.launch();
  for (const vp of viewports) {
    for (const target of targets) {
      const [kind, state, theme] = target.split(":");
      const ctx = await browser.newContext({
        viewport: { width: vp.width, height: vp.height },
        deviceScaleFactor: 2,
        isMobile: vp.isMobile,
        hasTouch: vp.isMobile,
        colorScheme: theme === "dark" ? "dark" : "light",
      });
      const page = await ctx.newPage();
      let url;
      let testId;
      if (kind === "real" || kind === "flow") {
        await mockApi(page, kind === "real" ? state : "19");
        url = `${base}/connections/demo-conn/menus`;
        testId = "menus-page";
      } else {
        url = `${base}/e2e/menus?state=${encodeURIComponent(state)}`;
        testId = "menus-harness";
      }
      await page.goto(url, { waitUntil: "networkidle", timeout: 120000 });
      await page.getByTestId(testId).waitFor({ timeout: 60000 });
      if (theme === "dark") await page.evaluate(() => document.documentElement.classList.add("dark"));
      await page.addStyleTag({ content: "nextjs-portal{display:none!important}" });
      await page.waitForTimeout(700);
      if (kind === "flow") {
        await page.getByTestId("menu-row-2").waitFor({ timeout: 30000 });
        if (state === "drag-refused") {
          const { dst, dt } = await dragRow(page, 2, 3);
          await dst.dispatchEvent("drop", { dataTransfer: dt });
          await page.getByTestId("menu-row-2").dispatchEvent("dragend", { dataTransfer: dt });
        } else if (state === "drag-staged") {
          const { dst, dt } = await dragRow(page, 6, 2);
          await dst.dispatchEvent("drop", { dataTransfer: dt });
          await page.getByTestId("menu-row-6").dispatchEvent("dragend", { dataTransfer: dt });
        } else if (state === "keyboard") {
          await page.getByTestId("menu-row-1").focus();
          await page.keyboard.press("ArrowDown");
          await page.keyboard.press("ArrowDown");
          await page.keyboard.press("ArrowLeft");
        }
        await page.waitForTimeout(500);
      }
      // Scroll to the end so sticky save bars rest in their natural place in a full-page shot.
      await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
      await page.waitForTimeout(150);
      const suffix = theme ? `-${theme}` : "";
      const file = path.join(outDir, `${prefix}-${kind}-${state}${suffix}-${vp.name}.png`);
      await page.screenshot({ path: file, fullPage: true, animations: "disabled" });
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      console.log(`${file} overflowX=${overflow}`);
      await ctx.close();
    }
  }
  await browser.close();
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
