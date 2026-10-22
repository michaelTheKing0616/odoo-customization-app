// UI-S-21 Wizard (Draft Studio route) vision capture against the REAL page
// /connections/<id>/wizard with mocked API routes (no live Odoo, no live LLM).
// Usage: NODE_PATH=apps/web/node_modules node docs/vision-verify/UI-S-21/capture.cjs \
//          http://127.0.0.1:3021 docs/vision-verify/UI-S-21 after [states...]
const { chromium } = require("@playwright/test");
const path = require("path");

const [, , base = "http://127.0.0.1:3021", outDir = ".", prefix = "after", ...rest] = process.argv;
const ALL = ["empty", "brief", "progress", "error", "review", "clarify", "online", "stock", "unprobed"];
const states = rest.length ? rest : ALL;
const viewports = [
  { name: "desktop", width: 1440, height: 900, isMobile: false },
  { name: "narrow", width: 390, height: 844, isMobile: true },
];
const CONN = "vision-conn";
const PROMPT = "Track equipment inspections on project tasks, with a due date and a pass or fail result.";

const CAPS = {
  major: 19,
  edition: "community",
  server_version: "19.0",
  supported: [
    "object_create_crud_model",
    "object_write_update_path",
    "related_write_dotted_path",
    "view_inject_inherit",
    "view_inject_mutate",
    "base_automation_safe_triggers",
  ],
  unsupported: [],
  ga: true,
  message: "ok",
};

const FORM_PREVIEW = {
  type: "form",
  model: "x_inspection",
  title: "Equipment inspections",
  statusbar: { field: "x_state", stages: ["planned", "done"], activeStage: "planned" },
  headerButtons: [{ id: "mark_done", string: "Mark done", variant: "primary" }],
  groups: [
    {
      id: "main",
      string: "Inspection",
      columns: 2,
      fields: [
        { id: "x_name", name: "x_name", string: "Reference", ttype: "char", required: true },
        { id: "x_task_id", name: "x_task_id", string: "Task", ttype: "many2one" },
        { id: "x_due_date", name: "x_due_date", string: "Due date", ttype: "date" },
        { id: "x_result", name: "x_result", string: "Result", ttype: "selection" },
      ],
    },
  ],
  chatter: "stub",
};

const TEMPLATES = [
  { id: "library", name: "Library", description: "Books, categories, and loans with member tracking." },
  { id: "crm_lite", name: "CRM Lite", description: "Lightweight leads with partner and stage." },
  { id: "helpdesk_lite", name: "Helpdesk Lite", description: "Tickets with priority, owner, and SLA date." },
  { id: "assets", name: "Asset register", description: "Equipment, owners, and maintenance dates." },
];

const BASE_DRAFT = {
  technical_name: "x_inspection",
  display_name: "Equipment inspections",
  models: [
    {
      model: "x_inspection",
      description: "Inspection",
      fields: [
        { name: "x_name", ttype: "char", string: "Reference" },
        { name: "x_due_date", ttype: "date", string: "Due date" },
        { name: "x_result", ttype: "selection", string: "Result" },
        { name: "x_task_id", ttype: "many2one", string: "Task", relation: "project.task" },
      ],
    },
  ],
  _llm_status: { mode: "llm_full" },
  _enrichment_clean: true,
  _scorecard: {
    score_0_10: 7.2,
    dimensions: { domain_fit: 8, structure: 7, semantics: 7.5, ux: 6.5, hygiene: 7 },
    validators: { all_green: false },
    findings: [
      { dimension: "structure", element: "x_inspection", detail: "no search view yet" },
      { dimension: "ux", element: "x_result", detail: "selection has no default" },
    ],
  },
  _certification: { tier: "ReviewRequired", quality: 7, evidence: 4, risk: 3, option_a_pending: false },
  _generation_engine: { capability: "fields", form_preview: FORM_PREVIEW },
};

function draftFor(state) {
  if (state === "clarify") {
    return {
      ...BASE_DRAFT,
      _generation_engine: {
        capability: "fields",
        form_preview: FORM_PREVIEW,
        needs_clarification: {
          question: "Should inspections live on project tasks, or as their own app with a menu?",
          options: [
            { id: "task", label: "On project tasks (adds a tab to the task form)" },
            { id: "app", label: "Own app with an Inspections menu" },
          ],
          default_id: "task",
        },
      },
    };
  }
  if (state === "online") {
    return {
      ...BASE_DRAFT,
      display_name: "Invoice pay link",
      _capability_primary_option_a: true,
      _live_apply: { option_a: ["QWeb PDF with a Pay now QR code", "Python compute for the pay link"] },
      _certification: { tier: "Reject", quality: 6, evidence: 2, risk: 5, option_a_pending: true },
    };
  }
  if (state === "stock") {
    return {
      technical_name: "stock_pos",
      display_name: "Point of Sale coverage",
      models: [],
      _scorecard: { score_0_10: 10, dimensions: {}, validators: { all_green: true }, findings: [] },
      _generation_engine: { capability: "stock_reuse", stock_apps: ["point_of_sale", "account"] },
      _certification: { tier: "ReviewRequired" },
    };
  }
  return BASE_DRAFT;
}

async function mock(page, state) {
  const online = state === "online";
  await page.route("**/api/**", async (route) => {
    const req = route.request();
    const url = req.url();
    const json = (body, status = 200) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (/\/api\/connections\/[^/?]+(\?.*)?$/.test(url) && req.method() === "GET") {
      return json({
        id: CONN,
        name: online ? "Acme on Odoo Online" : "Lab 19 sandbox",
        url: online ? "https://acme.odoo.com" : "http://127.0.0.1:8069",
        db_name: "odoo",
        username: "admin",
        server_version: "19.0",
        hosting: online ? "online" : "self_hosted",
        ...(state === "unprobed" ? {} : { capabilities: CAPS }),
        created_at: null,
        updated_at: null,
      });
    }
    if (url.includes("/api/ai/status")) return json({ enabled: true, ollama_reachable: true });
    if (url.includes("/api/ai/draft-module")) {
      if (state === "progress") {
        await new Promise((r) => setTimeout(r, 60_000));
        return json({ ok: true, draft: BASE_DRAFT, warnings: [] });
      }
      if (state === "error") {
        return json({ detail: "The model provider did not answer within 120 seconds." }, 503);
      }
      return json({ ok: true, draft: draftFor(state), warnings: [], note: "Draft only. Nothing applied." });
    }
    if (url.includes("/reuse-catalog")) return json([]);
    if (url.includes("/api/apps/templates")) return json(TEMPLATES);
    if (url.includes("/component-gallery")) return json([]);
    if (url.includes("/draft-cache")) return json([]);
    return route.continue();
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
    for (const state of states) {
      const page = await ctx.newPage();
      await mock(page, state);
      await page.goto(`${base}/connections/${CONN}/wizard`, { waitUntil: "domcontentloaded", timeout: 180000 });
      await page.getByTestId("draft-studio").waitFor({ timeout: 120000 });
      await page.waitForTimeout(800);
      if (vp.isMobile) {
        // AppShell keeps the sidebar open at 390px (global shell gap); collapse it so the
        // capture shows the Wizard itself.
        const collapse = page.getByRole("button", { name: "Collapse sidebar" });
        if (await collapse.count()) await collapse.first().click();
        await page.waitForTimeout(300);
      }
      if (!["empty", "unprobed"].includes(state)) {
        await page.getByTestId("draft-nl-prompt").fill(PROMPT);
      }
      if (!["empty", "brief", "unprobed"].includes(state)) {
        await page.getByTestId("create-draft").click();
        if (state === "progress") {
          await page.getByTestId("draft-studio-progress").waitFor({ timeout: 20000 });
        } else if (state === "error") {
          await page.waitForTimeout(1500);
        } else {
          await page.getByTestId("draft-studio-review-layout").waitFor({ timeout: 20000 });
        }
      }
      await page.waitForTimeout(700);
      const file = path.join(outDir, `${prefix}-${state}-${vp.name}.png`);
      await page.screenshot({ path: file, fullPage: true, animations: "disabled" });
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      console.log(`${file} overflowX=${overflow}`);
      if (vp.isMobile && state === "review") {
        // Phone review: the scorecard sits behind the Preview / Scorecard switch.
        const tab = page.getByTestId("draft-studio-mobile-tab-scorecard");
        if (await tab.count()) {
          await tab.click();
          await page.waitForTimeout(400);
          const scoreFile = path.join(outDir, `${prefix}-review-scorecard-${vp.name}.png`);
          await page.screenshot({ path: scoreFile, fullPage: true, animations: "disabled" });
          console.log(scoreFile);
        }
      }
      await page.close();
    }
    await ctx.close();
  }
  await browser.close();
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
