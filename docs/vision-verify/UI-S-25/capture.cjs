// UI-S-25 Expert vision capture.
// Usage: NODE_PATH=apps/web/node_modules node docs/vision-verify/UI-S-25/capture.cjs <baseUrl> <outDir> <prefix> [states...]
// Drives the real route /connections/demo-conn/expert and the /e2e/expert harness drawer with
// Playwright route mocks (no live Odoo, no live LLM).
const { chromium } = require("@playwright/test");
const path = require("path");

const [, , base = "http://127.0.0.1:3002", outDir = ".", prefix = "after", ...rest] = process.argv;
const ALL = ["empty", "answer", "loading", "error", "route", "unsupported", "drawer"];
const states = rest.length ? rest : ALL;
const viewports = [
  { name: "desktop", width: 1440, height: 900, isMobile: false },
  { name: "narrow", width: 390, height: 844, isMobile: true },
];

const CONN = {
  id: "demo-conn",
  name: "Lab 19 Community",
  url: "http://127.0.0.1:8069",
  db_name: "odoo",
  username: "admin",
  server_version: "19.0",
  created_at: null,
  updated_at: null,
  capabilities: {
    major: 19,
    edition: "community",
    server_version: "19.0",
    supported: ["view_inject_inherit"],
    unsupported: [],
    ga: true,
    message: "ok",
  },
};

const ANSWER = {
  answer_markdown:
    "Use an inherited view with `inherit_id` and an XPath `position` so your field lands inside the existing arch without replacing it [1].\n\n" +
    "1. Target a stable anchor, such as `//field[@name='partner_id']`.\n" +
    "2. Prefer `position=\"after\"` over `replace`; `replace` breaks other modules that inherit the same node [2].\n" +
    "3. Keep the inherit in its own record so it can be removed cleanly.",
  citations: [
    { source: "odoo_docs", version: "19.0", breadcrumb: "Views › Inheritance", chunk_id: "c1", source_index: 1 },
    { source: "odoo_docs", version: "19.0", breadcrumb: "Views › XPath positions", chunk_id: "c2", source_index: 2 },
  ],
  grounded: true,
  declined: false,
  uncited_warning: false,
  suggested_tools: [{ id: "designer", label: "Open View Designer", deep_link: "/connections/demo-conn/designer" }],
  caution_flags: ["replace_arch"],
};

const PROMPTS = [
  { id: "xpath", label: "XPath inherit", question: "How does xpath inherit extend a form without replacing the primary arch?" },
  { id: "acl", label: "AccessError on x_ model", question: "What usually causes an AccessError when writing a custom x_ model?" },
  { id: "stack", label: "Module stack", question: "Which Community modules do I need before customizing Sales and Contacts?" },
];

const ROUTE_OK = {
  prompt: "upload 200 journal entries",
  can_handle: "true",
  message: "Best fit: Journal batch import.",
  matches: [
    {
      feature_id: "journal.batch",
      title: "Journal batch",
      confidence: 0.9,
      why: "Matched journal entries and a bulk upload.",
      route: "journal?tab=batch",
      deep_link: "/connections/demo-conn/journal?tab=batch",
      can_handle: "true",
      recipe: "accounting.journal_batch",
    },
  ],
  alternatives: [
    {
      feature_id: "import.csv",
      title: "Import",
      confidence: 0.55,
      why: "Generic CSV import can also create account.move lines.",
      route: "import",
      deep_link: "/connections/demo-conn/import",
      can_handle: "partial",
    },
  ],
  ambiguous: false,
  honesty: "Preview is not posted. Nothing is written until you confirm in the feature.",
  source: "deterministic",
  llm_used: false,
};

const ROUTE_NO = {
  prompt: "send SMS blast",
  can_handle: "false",
  message: "ingenium does not send SMS or WhatsApp blasts.",
  matches: [],
  alternatives: [],
  ambiguous: false,
  honesty: "Use an Odoo SMS provider module for this.",
  source: "unsupported_catalog",
  llm_used: false,
};

async function mockApi(page, state) {
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    const json = (body, status = 200) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (url.includes("/api/expert/suggested-prompts")) return json(PROMPTS);
    if (url.includes("/api/expert/ask")) {
      if (state === "loading") return; // never resolves: holds the progress state
      if (state === "error") return json({ detail: "Expert retrieval timed out after 60s" }, 504);
      return json(ANSWER);
    }
    if (url.includes("/expert/route") || url.includes("/batch-os/intent-route")) {
      return json(state === "unsupported" ? ROUTE_NO : ROUTE_OK);
    }
    if (/\/api\/connections\/?(\?|$)/.test(url)) return json([CONN]);
    if (/\/api\/connections\/demo-conn\/?(\?|$)/.test(url)) return json(CONN);
    if (/(migration-assist|deployment-panel)/.test(url)) return json(null);
    return json([]);
  });
}

async function seedThread(page) {
  await page.evaluate((answer) => {
    sessionStorage.setItem(
      "expert-thread-demo-conn",
      JSON.stringify([
        { role: "user", content: "How does xpath inherit extend a form without replacing the primary arch?" },
        { role: "assistant", content: answer.answer_markdown, response: answer },
      ]),
    );
  }, ANSWER);
}

(async () => {
  const browser = await chromium.launch();
  for (const vp of viewports) {
    for (const state of states) {
      const ctx = await browser.newContext({
        viewport: { width: vp.width, height: vp.height },
        deviceScaleFactor: 2,
        isMobile: vp.isMobile,
        hasTouch: vp.isMobile,
      });
      const page = await ctx.newPage();
      await mockApi(page, state);
      if (state === "drawer") {
        await page.goto(`${base}/e2e/expert`, { waitUntil: "networkidle", timeout: 120000 });
        await page.getByTestId("expert-harness").waitFor({ timeout: 60000 });
        await page.evaluate((answer) => {
          sessionStorage.setItem(
            "expert-thread-e2e-expert-conn",
            JSON.stringify([
              { role: "user", content: "How does xpath inherit extend a form without replacing the primary arch?" },
              { role: "assistant", content: answer.answer_markdown, response: answer },
            ]),
          );
        }, ANSWER);
        await page.reload({ waitUntil: "networkidle" });
        await page.getByTestId("explain-this").click();
        await page.getByTestId("expert-panel").waitFor({ timeout: 30000 });
      } else {
        await page.goto(`${base}/connections/demo-conn/expert`, { waitUntil: "networkidle", timeout: 120000 });
        await page.getByTestId("expert-destination").waitFor({ timeout: 90000 });
        if (vp.isMobile) {
          // Global shell keeps the sidebar open at 390px (known gap); collapse it for a fair capture.
          const toggle = page.getByRole("button", { name: /collapse sidebar/i });
          if (await toggle.count()) await toggle.first().click().catch(() => {});
        }
        if (state === "answer") {
          await seedThread(page);
          await page.reload({ waitUntil: "networkidle" });
          await page.getByTestId("expert-destination").waitFor({ timeout: 60000 });
        }
        const input = page.getByTestId("expert-input");
        const hasInline = (await input.count()) > 0 && (await page.getByTestId("expert-panel").count()) === 0;
        if ((state === "loading" || state === "error") && hasInline) {
          await input.first().fill("Why does my x_visitor form throw AccessError on save?");
          await page.getByRole("button", { name: "Ask Expert" }).first().click();
          if (state === "error") await page.getByTestId("expert-error").waitFor({ timeout: 30000 });
          else await page.waitForTimeout(800);
        }
        if (state === "route" || state === "unsupported") {
          const routeInput = page.getByTestId("intent-router-input");
          const disclosure = page.getByTestId("expert-router-disclosure");
          if (await disclosure.count()) {
            const open = await disclosure.evaluate((el) => el.hasAttribute("open"));
            if (!open) await disclosure.locator("summary").click();
          }
          await routeInput.fill(state === "route" ? "upload 200 journal entries" : "send SMS blast");
          await page.getByTestId("intent-router-submit").click();
          await page
            .getByTestId(state === "route" ? "intent-router-matches" : "intent-router-unsupported")
            .waitFor({ timeout: 30000 });
          await page.getByTestId("intent-router-panel").scrollIntoViewIfNeeded();
        }
      }
      await page.waitForTimeout(600);
      const file = path.join(outDir, `${prefix}-${state}-${vp.name}.png`);
      await page.screenshot({ path: file, fullPage: state !== "drawer", animations: "disabled" });
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
