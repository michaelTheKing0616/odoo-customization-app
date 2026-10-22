// UI-S-18 Code Studio vision capture (real route, API mocked in the browser).
// node capture.cjs <baseUrl> <outDir> <prefix> [targets...]
// Target: <state>[:dark]. States: ready, validated, blocked, syntax, stale, testfail,
// optiona, gate, error, loading.
// Desktop shots use the real route /connections/demo-conn/code-studio inside the app shell.
// Mobile shots use the shell-free harness /e2e/code-studio (same CodeStudioScreen), because
// the app shell itself does not collapse at 390 px (pre-existing, outside this card).
// Run from apps/web with NODE_PATH=$PWD/node_modules so @playwright/test resolves.
const { chromium } = require("@playwright/test");
const path = require("path");

const [, , base = "http://127.0.0.1:3118", outDir = ".", prefix = "after", ...rest] = process.argv;
const targets = rest.length
  ? rest
  : [
      "ready",
      "validated",
      "blocked",
      "syntax",
      "stale",
      "testfail",
      "optiona",
      "gate",
      "error",
      "loading",
      "validated:dark",
      "optiona:dark",
    ];
const viewports = [
  { name: "desktop", width: 1440, height: 900, isMobile: false },
  { name: "mobile", width: 390, height: 844, isMobile: true },
];

const CONN = {
  id: "demo-conn",
  name: "Lagos Sessions",
  url: "http://127.0.0.1:8069",
  db_name: "odoo",
  username: "admin",
  server_version: "19.0",
  write_mode: "standard",
  hosting: "self_hosted",
  created_at: null,
  updated_at: null,
  capabilities: {
    major: 19,
    edition: "community",
    server_version: "19.0",
    supported: ["code_server_actions"],
    unsupported: [],
    ga: true,
    message: "ok",
    hosting_hint: "self_hosted",
    installed_modules_sample: ["base", "web"],
  },
};

function gate(supported) {
  return {
    probe: { supported },
    gating: supported
      ? {
          feature: "code_studio",
          title: "Live code server actions",
          why: "This instance accepts state=code server actions over RPC.",
          options: [],
          available: true,
          capability_key: "code_server_actions",
          gating_choices: [],
        }
      : {
          feature: "code_studio",
          title: "Live code actions unavailable",
          why: "Live code actions are not available on this instance.",
          options: [
            "Export Python as an installable module (Option A)",
            "Sandbox-test the module, then promote explicitly",
            "Use Automations → Python module export for scheduled logic",
          ],
          available: false,
          capability_key: "code_server_actions",
          gating_choices: [],
        },
    developer_role_required: true,
    entitlement_key: "dev_tools",
  };
}

const MODELS = [
  { id: 1, model: "res.partner", name: "Contact", state: "base", transient: false },
  { id: 2, model: "sale.order", name: "Sales Order", state: "base", transient: false },
  { id: 3, model: "x_session_booking", name: "Session booking", state: "manual", transient: false },
];
const SYMBOLS = [
  { name: "env", description: "Odoo environment for the current user." },
  { name: "model", description: "Model of the record the action runs on." },
  { name: "record", description: "The record the action runs on, or None." },
  { name: "records", description: "Recordset the action runs on." },
  { name: "log", description: "log(message, level='info') writes to ir.logging." },
  { name: "UserError", description: "Raise to stop with a message for the user." },
  { name: "datetime", description: "Python datetime module (safe subset)." },
];
const SNIPPETS = [
  { id: "set_field", label: "Set a field on each record", code: "for rec in records:\n    rec.write({'x_flag': True})" },
  { id: "guard", label: "Stop with a message", code: "if not record.email:\n    raise UserError('Add an email first.')" },
];

const TRACEBACK = [
  "Authentication RPC failed",
  "Traceback (most recent call last):",
  '  File "/usr/lib/python3/dist-packages/odoo/service/db.py", line 1',
  'psycopg.OperationalError: database "granted" does not exist',
].join("\n");

async function mockApi(page, state) {
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (body, status = 200) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    let payload = {};
    try {
      payload = JSON.parse(route.request().postData() || "{}");
    } catch {
      payload = {};
    }
    if (url.includes("/api/auth/status"))
      return json({ auth_mode: "off", auth_enabled: false, active_keys: 0, env_key_configured: false, bootstrap_available: false });
    if (/\/api\/connections\/demo-conn(\?|$)/.test(url)) return json(CONN);
    if (/\/api\/connections(\?|$)/.test(url)) return json([CONN]);
    if (/production-readiness/.test(url)) return json({ passed: true, items: [], first_write_acknowledged: true });
    if (/code-studio\/gate/.test(url)) {
      if (state === "loading") return; // never resolves: skeleton stays
      return json(gate(state !== "gate"));
    }
    if (/code-studio\/context/.test(url)) {
      if (state === "error") return json({ detail: TRACEBACK }, 502);
      return json({ major: 19, symbols: SYMBOLS });
    }
    if (/code-studio\/snippets/.test(url)) return json({ snippets: SNIPPETS });
    if (/code-studio\/probe/.test(url)) return json({ supported: state !== "gate" });
    if (/code-studio\/validate/.test(url)) {
      const code = String(payload.code || "");
      if (/^\s*(import|from)\s/m.test(code)) {
        const line = code.split("\n").findIndex((l) => /^\s*(import|from)\s/.test(l)) + 1;
        return json({ ok: true, syntax_ok: true, warnings: [{ code: "imports_forbidden", message: "Import statements are blocked in server-action safe_eval.", line: String(line) }], error: null, line: null });
      }
      if (/:\s*$/.test(code.split("\n")[0] || "") && code.split("\n").length === 1) {
        return json({ ok: false, syntax_ok: false, warnings: [], error: "Syntax error: expected an indented block (line 2)", line: 2 });
      }
      if ((code.match(/\(/g) || []).length !== (code.match(/\)/g) || []).length) {
        return json({ ok: false, syntax_ok: false, warnings: [], error: "Syntax error: '(' was never closed (line 2)", line: 2 });
      }
      return json({ ok: true, syntax_ok: true, warnings: [], error: null, line: null });
    }
    if (/code-studio\/test-run/.test(url)) {
      return json({
        ok: false,
        validation: { ok: true, syntax_ok: true, warnings: [], error: null, line: null },
        ran_for_real: true,
        record: { model: payload.model || "res.partner", id: 7 },
        exception: "ValueError: Invalid field 'x_flag' on model 'res.partner'",
        field_diff: [],
        snapshot_id: "snap-7f3a91",
      });
    }
    if (/\/models/.test(url)) return json(MODELS);
    return json([]);
  });
}

async function clickByName(page, names) {
  for (const name of names) {
    const btn = page.getByRole("button", { name, exact: true });
    if ((await btn.count()) > 0) {
      await btn.first().click();
      return true;
    }
  }
  return false;
}

async function setLine(page, n, value) {
  const input = page.getByLabel(`Line ${n}`, { exact: true });
  await input.fill(value);
}

const VALIDATE = ["Validate code", "Check syntax"];

(async () => {
  const browser = await chromium.launch();
  for (const vp of viewports) {
    for (const target of targets) {
      const [state, theme] = target.split(":");
      const ctx = await browser.newContext({
        viewport: { width: vp.width, height: vp.height },
        deviceScaleFactor: 2,
        isMobile: vp.isMobile,
        hasTouch: vp.isMobile,
        colorScheme: theme === "dark" ? "dark" : "light",
      });
      await ctx.addInitScript(() => {
        try {
          localStorage.setItem("first-write-ack:demo-conn", "1");
        } catch {}
      });
      const page = await ctx.newPage();
      await mockApi(page, state);
      const route = vp.isMobile && prefix !== "before" ? "/e2e/code-studio" : "/connections/demo-conn/code-studio";
      await page.goto(`${base}${route}`, { waitUntil: "domcontentloaded", timeout: 180000 });
      await page.getByTestId("code-studio-page").waitFor({ timeout: 120000 });
      if (theme === "dark") await page.evaluate(() => document.documentElement.classList.add("dark"));
      await page.addStyleTag({ content: "nextjs-portal{display:none!important}" });
      if (state === "loading") {
        await page.getByTestId("code-studio-loading").waitFor({ timeout: 30000 });
      } else if (state === "gate") {
        await page.getByTestId("gating-callout").first().waitFor({ timeout: 30000 });
      } else if (state === "error") {
        await page.getByTestId("error-notice").waitFor({ timeout: 30000 });
      } else {
        await page.getByTestId("code-studio-editor").waitFor({ timeout: 30000 });
      }
      await page.waitForTimeout(600);
      if (state === "validated" || state === "stale" || state === "testfail") {
        await clickByName(page, VALIDATE);
        await page.waitForTimeout(400);
      }
      if (state === "stale") {
        await setLine(page, 2, "    rec.write({'name': rec.name or 'Renamed'})");
      }
      if (state === "blocked") {
        await setLine(page, 1, "import os");
        await clickByName(page, VALIDATE);
      }
      if (state === "syntax") {
        await setLine(page, 2, "    rec.write({'name': rec.name or 'Updated'}");
        await clickByName(page, VALIDATE);
      }
      if (state === "testfail") {
        await clickByName(page, ["Test run on record"]);
      }
      if (state === "optiona") {
        await page.getByRole("radio", { name: /Custom-code module/ }).check();
        await clickByName(page, VALIDATE);
      }
      await page.waitForTimeout(700);
      await page.evaluate(() => window.scrollTo(0, 0));
      const suffix = theme ? `-${theme}` : "";
      const file = path.join(outDir, `${prefix}-${state}${suffix}-${vp.name}.png`);
      await page.screenshot({ path: file, fullPage: true, animations: "disabled" });
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      console.log(`${file} overflowX=${overflow}`);
      await ctx.close();
    }
  }
  await browser.close();
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
