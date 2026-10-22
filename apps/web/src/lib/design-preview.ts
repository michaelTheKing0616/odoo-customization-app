import type { PreviewField, PreviewFormView } from "@/lib/draft-form-preview";
import type { StudioAppDesign, StudioDesignField } from "@/lib/studio-session";

/** App Studio design (agent or pipeline) -> Odoo-like form previews, one per new model or extended stock form. */
const TAB_TYPES = new Set(["one2many", "many2many", "html"]);
const STOCK_TITLE: Record<string, string> = {
  "res.partner": "Contact", "sale.order": "Quotation", "crm.lead": "Lead", "account.move": "Invoice",
  "project.task": "Task", "project.project": "Project", "hr.employee": "Employee", "product.template": "Product",
  "product.product": "Product", "res.users": "User", "helpdesk.ticket": "Ticket",
};

function toField(model: string, f: StudioDesignField): PreviewField {
  return {
    id: `${model}.${f.name}`, name: f.name, string: f.string || f.name.replace(/^x_/, "").replace(/_/g, " "),
    ttype: f.ttype, required: Boolean(f.required), relation: f.relation ?? null,
    selection: f.selection?.length ? f.selection.map(([value, label]) => ({ value, label: label ?? value })) : null,
  };
}

function formFor(model: string, title: string, fields: StudioDesignField[], appLabel: string | null): PreviewFormView {
  const all = fields.map((f) => toField(model, f));
  const main = all.filter((f) => !TAB_TYPES.has(f.ttype ?? ""));
  const tabs = all.filter((f) => TAB_TYPES.has(f.ttype ?? ""));
  const half = Math.ceil(main.length / 2);
  return {
    type: "form", model, title, appLabel,
    recordTitleField: main.find((f) => f.name === "x_name")?.name ?? null,
    groups: main.length > 3
      ? [{ id: `${model}:g1`, string: "", columns: 1, fields: main.slice(0, half) },
         { id: `${model}:g2`, string: "", columns: 1, fields: main.slice(half) }]
      : [{ id: `${model}:g1`, string: "", columns: 2, fields: main }],
    notebooks: tabs.length ? [{ id: `${model}:nb`, pages: tabs.map((f) => ({ id: `${model}:p:${f.name}`, string: f.string, fields: [f] })) }] : [],
    chatter: "stub",
  };
}

export function designPreviews(design: StudioAppDesign | null | undefined): PreviewFormView[] {
  if (!design) return [];
  const app = design.app_name || null;
  const out = (design.new_models || []).filter((m) => m.fields?.length).map((m) => formFor(m.name, m.label || m.name, m.fields, app));
  for (const e of design.stock_extensions || []) {
    if (e.fields?.length) out.push(formFor(e.model, STOCK_TITLE[e.model] ?? e.model, e.fields, null));
  }
  return out;
}

/** Stock Odoo apps the design builds on that this database doesn't have yet (and the owner didn't switch off). */
export function designAppsToInstall(design: StudioAppDesign | null | undefined): { module: string; app: string }[] {
  if (!design) return [];
  const off = new Set((design as { integrations_off?: string[] }).integrations_off || []);
  const seen = new Set<string>();
  return (design.integrations || [])
    .filter((i) => i.module && i.installed === false && i.status !== "deferred" && !off.has(i.module) && !off.has(i.app))
    .filter((i) => (seen.has(i.module) ? false : (seen.add(i.module), true)))
    .map((i) => ({ module: i.module, app: i.app || i.module }));
}
