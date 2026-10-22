import { expect, test, type Page } from "@playwright/test";
import path from "node:path";
import { mockConnectionApi } from "./helpers/mockConnectionApi";

/** One-off review capture for Overview stage 2 (not a regression gate). */
const OUT_DIR = path.resolve(__dirname, "../../../docs/vision-verify/OVERVIEW-STAGE2");

const SNAP = {
  ok: true, major: 18, series: "18.0", server_version: "18.0+e", edition: "enterprise", hosting: "onprem",
  support: "supported",
  apps: ["Sales", "CRM", "Inventory", "Invoicing", "Discuss", "Employees"].map((l) => ({ name: l.toLowerCase(), label: l })),
  modules: [],
  counts: { modules: 64, modules_hidden: 12, apps: 6, models: 412, custom_models: 3, automations: 4, scheduled_actions: 17, groups: 38 },
  custom_models: [
    { model: "x_renewal", label: "Renewal" }, { model: "x_site_visit", label: "Site visit" }, { model: "x_warranty", label: "Warranty claim" },
  ],
  models: [
    { model: "x_renewal", label: "Renewal" }, { model: "x_site_visit", label: "Site visit" }, { model: "x_warranty", label: "Warranty claim" },
    { model: "account.move", label: "Journal Entry" }, { model: "crm.lead", label: "Lead/Opportunity" },
    { model: "product.template", label: "Product" }, { model: "res.partner", label: "Contact" },
    { model: "sale.order", label: "Sales Order" }, { model: "stock.picking", label: "Transfer" },
  ],
  automations: [
    { name: "Renewal reminder", model_id: "Renewal", trigger: "on_time" },
    { name: "Assign new leads", model_id: "Lead/Opportunity", trigger: "on_create" },
  ],
  scheduled_actions: [
    { cron_name: "Mail: Email Queue Manager", interval_number: "1", interval_type: "hours" },
    { cron_name: "Nightly stock sync", interval_number: "1", interval_type: "days" },
  ],
  groups: [],
  can_change: [
    { key: "custom_fields", available: "yes", reason: "" }, { key: "custom_models", available: "yes", reason: "" },
    { key: "automations", available: "yes", reason: "" }, { key: "python_module_install", available: "no", reason: "Plan" },
  ],
  problems: [],
  attention: [
    { key: "failing_crons", severity: "critical", rank: 1, title: "Scheduled actions are failing",
      detail: "1 scheduled action(s) failed on their last runs. Odoo turns them off after repeated failures.",
      count: 1, drill: { section: "automations" }, names: ["Nightly stock sync"] },
    { key: "custom_no_access", severity: "warning", rank: 2, title: "Custom models nobody can open",
      detail: "These custom models have no access rules, so only the administrator can see them.",
      count: 1, drill: { section: "explorer", model: "x_site_visit", tab: "rules" }, names: ["x_site_visit"] },
    { key: "plan_limits", severity: "limit", rank: 3, title: "You may be near your plan's limits",
      detail: "This is an estimate from your plan and hosting. Some changes may need a different setup: custom code modules.",
      count: 1, drill: { section: "capabilities" }, names: ["custom code modules"] },
  ],
};

const DETAIL = {
  model: "x_renewal", label: "Renewal", custom: true,
  fields: [
    { name: "x_name", type: "char", string: "Name", required: true, relation: "", selection: [] },
    { name: "x_partner_id", type: "many2one", string: "Customer", required: true, relation: "res.partner", selection: [] },
    { name: "x_owner_id", type: "many2one", string: "Owner", required: false, relation: "res.users", selection: [] },
    { name: "x_due_date", type: "date", string: "Due date", required: false, relation: "", selection: [] },
    { name: "x_stage", type: "selection", string: "Stage", required: false, relation: "", selection: ["New", "Contacted", "Renewed", "Lost"] },
    { name: "x_amount", type: "monetary", string: "Amount", required: false, relation: "", selection: [] },
  ],
  views: { types: ["form", "list", "kanban"], form_field_count: 6, form_fields: [] },
  server_actions: [], menus: ["Renewals / All renewals"],
  record_rules: { source: "ir.model.access", rows: [] },
  problems: [],
};

async function routes(page: Page) {
  await mockConnectionApi(page);
  await page.route("**/api/connections/*/snapshot", (r) => r.fulfill({ json: SNAP }));
  await page.route("**/api/connections/*/snapshot/models/**", (r) => r.fulfill({ json: DETAIL }));
}

for (const theme of ["light", "dark"] as const) {
  test(`overview stage 2 ${theme}`, async ({ page }) => {
    test.setTimeout(120_000);
    await page.addInitScript((t) => {
      localStorage.setItem("odoo-custom-theme", t);
      document.documentElement.classList.toggle("dark", t === "dark");
    }, theme);
    await routes(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/connections/demo-conn");
    await expect(page.getByTestId("live-snapshot")).toBeVisible({ timeout: 90_000 });
    for (let i = 0; i < 3 && (await page.getByRole("dialog").count()) > 0; i++) {
      await page.keyboard.press("Escape");
      await page.waitForTimeout(300);
    }
    await page.getByRole("option", { name: /Renewal/ }).evaluate((el) => (el as HTMLElement).click());
    await expect(page.getByTestId("tab-fields")).toBeVisible();
    await page.screenshot({ path: path.join(OUT_DIR, `overview-${theme}.png`), fullPage: true });
  });
}
