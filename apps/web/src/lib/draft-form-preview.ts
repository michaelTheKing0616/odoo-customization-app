/** Stage H helpers — OdooPreviewKit schema + generation engine IR accessors. */

export type PreviewField = {
  id: string;
  name: string;
  string: string;
  ttype?: string;
  widget?: string | null;
  required?: boolean;
  selection?: Array<{ value: string; label: string }> | null;
};

export type PreviewGroup = {
  id: string;
  string: string;
  columns: 1 | 2;
  fields: PreviewField[];
};

export type PreviewNotebookPage = {
  id: string;
  string: string;
  fields: PreviewField[];
};

export type PreviewNotebook = {
  id: string;
  pages: PreviewNotebookPage[];
};

export type PreviewHeaderButton = {
  id: string;
  string: string;
  variant: "primary" | "secondary";
};

export type PreviewFormAlert = {
  id: string;
  level: "info" | "warning" | "danger" | string;
  message: string;
  when?: string | null;
  kind?: "alert" | "ribbon" | string;
};

export type PreviewStatusBar = {
  field: string;
  stages: string[];
  activeStage?: string | null;
};

export type PreviewSmartButton = {
  id: string;
  string: string;
  count?: number | string | null;
};

export type PreviewFormView = {
  type: "form";
  model: string;
  title: string;
  /** Stock app tile label for breadcrumb (e.g. Contacts) — never technical model. */
  appLabel?: string | null;
  recordTitleField?: string | null;
  statusbar?: PreviewStatusBar | null;
  headerButtons?: PreviewHeaderButton[];
  smartButtons?: PreviewSmartButton[];
  groups: PreviewGroup[];
  notebooks?: PreviewNotebook[];
  chatter?: "stub" | "hidden";
  groupLayout?: "stack" | "two-column";
  alerts?: PreviewFormAlert[];
};

export type PreviewListColumn = {
  id: string;
  name: string;
  string: string;
};

export type PreviewListDecorations = {
  danger?: string | null;
  info?: string | null;
  muted?: string | null;
};

export type PreviewListView = {
  type: "list";
  model: string;
  title: string;
  columns: PreviewListColumn[];
  decorations?: PreviewListDecorations | null;
};

export type PreviewKanbanView = {
  type: "kanban";
  model: string;
  title: string;
  groupBy?: string | null;
  cardFields: PreviewField[];
};

export type PreviewViewSchema = PreviewFormView | PreviewListView | PreviewKanbanView;

/** @deprecated Use PreviewFormView — kept for legacy call sites. */
export type ResidualFormPreview = PreviewFormView;

export type OptionASettings = {
  model: string;
  fields: Array<{ name: string; string: string; help?: string }>;
};

export type GenerationEngineIr = {
  capability?: string;
  gold_artifact_id?: string | null;
  module_delivery?: boolean;
  honesty?: string;
  refuse_reason?: string;
  user_phase?: string;
  user_phase_label?: string;
  grain?: string;
  stock_apps?: Array<{ id?: string; label?: string }>;
  form_preview?: PreviewFormView;
  list_preview?: PreviewListView;
  kanban_preview?: PreviewKanbanView;
  option_a_settings?: OptionASettings;
  needs_clarification?: {
    question?: string;
    options?: Array<{ id: string; label: string }>;
    default_id?: string;
  };
};

export function generationEngineFromDraft(
  draft: Record<string, unknown> | null | undefined,
): GenerationEngineIr | null {
  const raw = draft?._generation_engine;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  return raw as GenerationEngineIr;
}

function normalizeGroup(raw: unknown, index: number): PreviewGroup | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const g = raw as Record<string, unknown>;
  if (!Array.isArray(g.fields)) return null;
  const fields: PreviewField[] = [];
  g.fields.forEach((f, i) => {
    if (!f || typeof f !== "object") return;
    const fr = f as Record<string, unknown>;
    const name = String(fr.name || fr.id || `field_${i}`);
    const tech = name.replace(/^x_studio_/i, "x_");
    let ttype = fr.ttype ? String(fr.ttype).toLowerCase() : "char";
    const widgetRaw = fr.widget != null ? String(fr.widget) : null;
    const labelRaw = String(fr.string || "").trim();
    const label =
      labelRaw && !/^x_studio_/i.test(labelRaw)
        ? labelRaw
        : tech.replace(/^x_/, "").replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
    if (
      ttype === "boolean" ||
      ttype === "bool" ||
      widgetRaw === "boolean" ||
      widgetRaw === "boolean_toggle" ||
      (/checkbox|preferred for delivery/i.test(`${label} ${tech}`) && ttype === "char")
    ) {
      ttype = "boolean";
    }
    fields.push({
      id: String(fr.id || tech),
      name: tech,
      string: label,
      ttype,
      widget: widgetRaw,
      required: Boolean(fr.required),
      selection: Array.isArray(fr.selection)
        ? (fr.selection as Array<{ value: string; label: string }>)
        : null,
    });
  });
  return {
    id: String(g.id || `group_${index}`),
    string: String(g.string || "Group"),
    columns: g.columns === 2 ? 2 : 1,
    fields,
  };
}

function normalizeStatusbar(raw: unknown): PreviewStatusBar | null {
  if (!raw) return null;
  if (typeof raw === "string") {
    const field = raw.trim();
    if (!field) return null;
    return { field, stages: [field], activeStage: field };
  }
  if (typeof raw !== "object" || Array.isArray(raw)) return null;
  const s = raw as Record<string, unknown>;
  const field = String(s.field || "").trim();
  const stages = Array.isArray(s.stages)
    ? s.stages.map((x) => String(x)).filter(Boolean)
    : [];
  if (!field || stages.length === 0) return null;
  return {
    field,
    stages,
    activeStage: s.activeStage != null ? String(s.activeStage) : stages[0],
  };
}

/** Accepts new PreviewFormView and legacy Stage-H payloads (no `type`, string statusbar). */
export function normalizeFormPreview(raw: unknown): PreviewFormView | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const rec = raw as Record<string, unknown>;
  const model = String(rec.model || "").trim();
  if (!model || !Array.isArray(rec.groups)) return null;
  if (rec.type != null && rec.type !== "form") return null;

  const groups: PreviewGroup[] = [];
  rec.groups.forEach((g, i) => {
    const ng = normalizeGroup(g, i);
    if (ng) groups.push(ng);
  });

  const headerButtons: PreviewHeaderButton[] = [];
  if (Array.isArray(rec.headerButtons)) {
    rec.headerButtons.forEach((b, i) => {
      if (!b || typeof b !== "object") return;
      const br = b as Record<string, unknown>;
      headerButtons.push({
        id: String(br.id || `hdr-${i}`),
        string: String(br.string || "Button"),
        variant: br.variant === "primary" ? "primary" : "secondary",
      });
    });
  }

  const smartButtons: PreviewSmartButton[] = [];
  if (Array.isArray(rec.smartButtons)) {
    rec.smartButtons.forEach((b, i) => {
      if (!b || typeof b !== "object") return;
      const br = b as Record<string, unknown>;
      smartButtons.push({
        id: String(br.id || `stat-${i}`),
        string: String(br.string || "Open"),
        count: (br.count as number | string | null | undefined) ?? null,
      });
    });
  }

  const notebooks: PreviewNotebook[] = [];
  if (Array.isArray(rec.notebooks)) {
    rec.notebooks.forEach((nb, i) => {
      if (!nb || typeof nb !== "object") return;
      const n = nb as Record<string, unknown>;
      if (!Array.isArray(n.pages)) return;
      const pages: PreviewNotebook["pages"] = [];
      n.pages.forEach((p, pi) => {
        const page = (p && typeof p === "object" ? p : {}) as Record<string, unknown>;
        const fields: PreviewField[] = [];
        if (Array.isArray(page.fields)) {
          page.fields.forEach((f, fi) => {
            if (!f || typeof f !== "object") return;
            const fr = f as Record<string, unknown>;
            const name = String(fr.name || `f${fi}`);
            fields.push({
              id: String(fr.id || name),
              name,
              string: String(fr.string || name),
              ttype: fr.ttype ? String(fr.ttype) : "char",
            });
          });
        }
        pages.push({
          id: String(page.id || `page-${pi}`),
          string: String(page.string || `Page ${pi + 1}`),
          fields,
        });
      });
      notebooks.push({ id: String(n.id || `nb-${i}`), pages });
    });
  }

  const rawTitle = String(rec.title || "").trim();
  const humanTitle =
    rawTitle && rawTitle !== model && !/^res\./i.test(rawTitle) && rawTitle.toLowerCase() !== "res"
      ? rawTitle
      : model === "res.partner"
        ? "Contact"
        : rawTitle || model;

  return {
    type: "form",
    model,
    title: humanTitle,
    appLabel: rec.appLabel != null ? String(rec.appLabel) : model === "res.partner" ? "Contacts" : null,
    recordTitleField: rec.recordTitleField != null ? String(rec.recordTitleField) : "x_name",
    statusbar: normalizeStatusbar(rec.statusbar),
    headerButtons,
    smartButtons,
    groups,
    notebooks,
    chatter: rec.chatter === "stub" ? "stub" : "hidden",
    alerts: Array.isArray((raw as any).alerts) ? ((raw as any).alerts as PreviewFormAlert[]) : [],
    groupLayout: rec.groupLayout === "two-column" ? "two-column" : "stack",
  };
}

export function formPreviewFromDraft(
  draft: Record<string, unknown> | null | undefined,
): PreviewFormView | null {
  return normalizeFormPreview(generationEngineFromDraft(draft)?.form_preview);
}

export function listPreviewFromDraft(
  draft: Record<string, unknown> | null | undefined,
): PreviewListView | null {
  const preview = generationEngineFromDraft(draft)?.list_preview;
  if (!preview || typeof preview !== "object") return null;
  if (preview.type !== "list" || !Array.isArray(preview.columns)) return null;
  return preview;
}

export function kanbanPreviewFromDraft(
  draft: Record<string, unknown> | null | undefined,
): PreviewKanbanView | null {
  const preview = generationEngineFromDraft(draft)?.kanban_preview;
  if (!preview || typeof preview !== "object") return null;
  if (preview.type !== "kanban" || !Array.isArray(preview.cardFields)) return null;
  return preview;
}

export function previewViewsFromDraft(draft: Record<string, unknown> | null | undefined): {
  form: PreviewFormView | null;
  list: PreviewListView | null;
  kanban: PreviewKanbanView | null;
} {
  return {
    form: formPreviewFromDraft(draft),
    list: listPreviewFromDraft(draft),
    kanban: kanbanPreviewFromDraft(draft),
  };
}

/** Backward-compatible alias. */
export function residualFormPreviewFromDraft(
  draft: Record<string, unknown> | null | undefined,
): PreviewFormView | null {
  return formPreviewFromDraft(draft);
}

export function optionASettingsFromDraft(
  draft: Record<string, unknown> | null | undefined,
): OptionASettings | null {
  const engine = generationEngineFromDraft(draft);
  const settings = engine?.option_a_settings;
  if (settings?.model && Array.isArray(settings.fields) && settings.fields.length > 0) {
    return settings;
  }
  return null;
}

export function isRefuseCloneDraft(draft: Record<string, unknown> | null | undefined): boolean {
  return generationEngineFromDraft(draft)?.capability === "refuse_clone";
}

export function isGoldOptionADraft(draft: Record<string, unknown> | null | undefined): boolean {
  const engine = generationEngineFromDraft(draft);
  return engine?.capability === "option_a_standalone" && Boolean(engine.gold_artifact_id);
}

export function isOptionAAuthoredDraft(
  draft: Record<string, unknown> | null | undefined,
): boolean {
  return generationEngineFromDraft(draft)?.capability === "option_a_authored";
}

export function optionAAuthoringPassed(
  draft: Record<string, unknown> | null | undefined,
): boolean {
  if (!isOptionAAuthoredDraft(draft)) return true;
  const rec = draft?._option_a_authoring;
  if (!rec || typeof rec !== "object" || Array.isArray(rec)) return false;
  return (rec as { status?: string }).status === "pass";
}

export type AuthoringFinding = {
  code?: string;
  message?: string;
  file?: string;
  model?: string;
  install_module?: string;
  install_label?: string;
};

export type HostInstallOffer = {
  module: string;
  label: string;
  models: string[];
  message?: string;
};

const HOST_APP_BY_MODEL: Record<string, { module: string; label: string }> = {
  "sale.order": { module: "sale", label: "Sales" },
  "sale.order.line": { module: "sale", label: "Sales" },
  "account.move": { module: "account", label: "Invoicing" },
  "account.move.line": { module: "account", label: "Invoicing" },
  "account.payment": { module: "account", label: "Invoicing" },
  "purchase.order": { module: "purchase", label: "Purchase" },
  "purchase.order.line": { module: "purchase", label: "Purchase" },
  "stock.picking": { module: "stock", label: "Inventory" },
  "stock.move": { module: "stock", label: "Inventory" },
  "stock.quant": { module: "stock", label: "Inventory" },
  "stock.warehouse": { module: "stock", label: "Inventory" },
  "product.product": { module: "product", label: "Products" },
  "product.template": { module: "product", label: "Products" },
  "crm.lead": { module: "crm", label: "CRM" },
  "project.project": { module: "project", label: "Project" },
  "project.task": { module: "project", label: "Project" },
  "hr.employee": { module: "hr", label: "Employees" },
  "hr.expense": { module: "hr_expense", label: "Expenses" },
  "hr.leave": { module: "hr_holidays", label: "Time Off" },
  "calendar.event": { module: "calendar", label: "Calendar" },
  "mrp.production": { module: "mrp", label: "Manufacturing" },
  "mrp.bom": { module: "mrp", label: "Manufacturing" },
  "pos.config": { module: "point_of_sale", label: "Point of Sale" },
  "pos.order": { module: "point_of_sale", label: "Point of Sale" },
  "pos.session": { module: "point_of_sale", label: "Point of Sale" },
  "fleet.vehicle": { module: "fleet", label: "Fleet" },
  "maintenance.request": { module: "maintenance", label: "Maintenance" },
  "repair.order": { module: "repair", label: "Repairs" },
  "website.page": { module: "website", label: "Website" },
  "event.event": { module: "event", label: "Events" },
  "survey.survey": { module: "survey", label: "Surveys" },
  "uom.uom": { module: "uom", label: "Units of Measure" },
};

const INHERIT_MODEL_MSG = /Inherit model\s+(\S+)\s+is not/i;

export function inheritModelFromFinding(row: AuthoringFinding): string {
  const direct = String(row.model || "").trim();
  if (direct) return direct;
  const match = String(row.message || "").match(INHERIT_MODEL_MSG);
  return match?.[1]?.replace(/\.$/, "") || "";
}

function offerFromUnknown(row: Record<string, unknown>): HostInstallOffer | null {
  const moduleName = String(row.module || "").trim();
  const label = String(row.label || "").trim();
  const models = Array.isArray(row.models)
    ? row.models.map((m) => String(m).trim()).filter(Boolean)
    : [];
  if (!moduleName || !label || !models.length) return null;
  return {
    module: moduleName,
    label,
    models,
    message: typeof row.message === "string" ? row.message : undefined,
  };
}

function offersFromFindings(findings: AuthoringFinding[]): HostInstallOffer[] {
  const grouped = new Map<string, HostInstallOffer>();
  for (const row of findings) {
    if (row.code !== "model_missing") continue;
    const model = inheritModelFromFinding(row);
    const app =
      (row.install_module && row.install_label
        ? { module: row.install_module, label: row.install_label }
        : HOST_APP_BY_MODEL[model]) || null;
    if (!app || model.startsWith("x_")) continue;
    const existing = grouped.get(app.module);
    if (existing) {
      if (!existing.models.includes(model)) existing.models.push(model);
      continue;
    }
    grouped.set(app.module, {
      module: app.module,
      label: app.label,
      models: [model],
    });
  }
  return [...grouped.values()].map((offer) => ({
    ...offer,
    message:
      `This Option A module inherits ${offer.models.join(", ")}. Those models come from the stock ${offer.label} app (${offer.module}). ` +
      "Install it on this connection so the authoring gate can verify the inherit. That does not install this custom zip — Promote stays human.",
  }));
}

export function hostInstallOffersFromDraft(
  draft: Record<string, unknown> | null | undefined,
): HostInstallOffer[] {
  const rec = draft?._option_a_authoring;
  if (rec && typeof rec === "object" && !Array.isArray(rec)) {
    const stamped = (rec as { host_install?: unknown }).host_install;
    if (Array.isArray(stamped) && stamped.length) {
      const offers = stamped
        .filter((row) => row && typeof row === "object")
        .map((row) => offerFromUnknown(row as Record<string, unknown>))
        .filter((row): row is HostInstallOffer => Boolean(row));
      if (offers.length) return offers;
    }
  }
  return offersFromFindings(optionAAuthoringFindings(draft));
}

export function authoringFindingsWithoutHostInstall(
  draft: Record<string, unknown> | null | undefined,
): AuthoringFinding[] {
  const covered = new Set(hostInstallOffersFromDraft(draft).flatMap((o) => o.models));
  return optionAAuthoringFindings(draft).filter((row) => {
    if (row.code !== "model_missing") return true;
    const model = inheritModelFromFinding(row);
    return !model || !covered.has(model);
  });
}

export function optionAAuthoringFindings(
  draft: Record<string, unknown> | null | undefined,
): AuthoringFinding[] {
  const rec = draft?._option_a_authoring;
  if (!rec || typeof rec !== "object" || Array.isArray(rec)) return [];
  const rows = (rec as { findings?: unknown }).findings;
  if (!Array.isArray(rows)) return [];
  return rows.filter((row) => row && typeof row === "object") as AuthoringFinding[];
}

const TRANSIENT_AUTHOR_CODES = new Set(["author_failed", "empty_module", "llm_unavailable"]);

export function optionAAuthoringRetryable(
  draft: Record<string, unknown> | null | undefined,
): boolean {
  if (optionAAuthoringPassed(draft)) return false;
  const rec = draft?._option_a_authoring;
  if (rec && typeof rec === "object" && !Array.isArray(rec) && (rec as { retryable?: boolean }).retryable) {
    return true;
  }
  const findings = optionAAuthoringFindings(draft);
  if (!findings.length) return false;
  return findings.every((row) => TRANSIENT_AUTHOR_CODES.has(String(row.code || "")));
}

const JSON_REPAIR_RE =
  /unterminated|incomplete json|malformed json|jsondecodeerror|invalid control character|not an object|author_json/;

export function optionAAuthoringNeedsAutoRepair(
  draft: Record<string, unknown> | null | undefined,
): boolean {
  if (!optionAAuthoringRetryable(draft)) return false;
  const blob = optionAAuthoringFindings(draft)
    .map((row) => `${row.code || ""} ${row.message || ""}`)
    .join(" ")
    .toLowerCase();
  return JSON_REPAIR_RE.test(blob);
}

export function isStockReuseDraft(draft: Record<string, unknown> | null | undefined): boolean {
  return generationEngineFromDraft(draft)?.capability === "stock_reuse";
}

export type StockAppRow = { id: string; label: string };

const STOCK_APP_LABELS: Record<string, string> = {
  point_of_sale: "Point of Sale",
  sale: "Sales",
  account: "Invoicing",
  contacts: "Contacts",
  mail: "Discuss",
  hr: "Employees",
  stock: "Inventory",
  purchase: "Purchase",
  crm: "CRM",
  project: "Project",
  calendar: "Calendar",
  mrp: "Manufacturing",
  website: "Website",
  product: "Products",
};

function labelStockApp(id: string): string {
  return STOCK_APP_LABELS[id] || id.replaceAll("_", " ");
}

export function stockAppsFromDraft(
  draft: Record<string, unknown> | null | undefined,
): StockAppRow[] {
  const engine = generationEngineFromDraft(draft);
  const raw = engine?.stock_apps;
  if (Array.isArray(raw) && raw.length > 0) {
    return raw
      .map((row) => {
        if (!row || typeof row !== "object") return null;
        const rec = row as { id?: string; label?: string };
        const id = String(rec.id || "").trim();
        if (!id) return null;
        return { id, label: String(rec.label || labelStockApp(id)) };
      })
      .filter((row): row is StockAppRow => Boolean(row));
  }
  const depends = Array.isArray(draft?.depends) ? (draft?.depends as unknown[]) : [];
  return depends
    .map((id) => String(id || "").trim())
    .filter(Boolean)
    .map((id) => ({ id, label: labelStockApp(id) }));
}

export function wantsModuleDelivery(draft: Record<string, unknown> | null | undefined): boolean {
  const engine = generationEngineFromDraft(draft);
  if (engine?.module_delivery) return true;
  return draft?._delivery_preference === "module_zip";
}

export type DocumentGrammarCard = {
  shape: string;
  display_name: string;
  header_model: string;
  document_count: number;
  slots: string[];
  states: string[];
  extra_apps: number;
  summary: string;
};

export function documentGrammarFromDraft(
  draft: Record<string, unknown> | null | undefined,
): DocumentGrammarCard | null {
  const raw = draft?._document_grammar;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const rec = raw as Record<string, unknown>;
  const summary = String(rec.summary || "").trim();
  if (!summary) return null;
  return {
    shape: String(rec.shape || ""),
    display_name: String(rec.display_name || ""),
    header_model: String(rec.header_model || ""),
    document_count: Number(rec.document_count || 0),
    slots: Array.isArray(rec.slots) ? rec.slots.map((s) => String(s)) : [],
    states: Array.isArray(rec.states) ? rec.states.map((s) => String(s)) : [],
    extra_apps: Number(rec.extra_apps || 0),
    summary,
  };
}

export type SurfaceFinding = { dimension?: string; element?: string; detail?: string };

export function surfaceGateFindingsFromDraft(
  draft: Record<string, unknown> | null | undefined,
): SurfaceFinding[] {
  const live = draft?._live_apply;
  if (!live || typeof live !== "object" || Array.isArray(live)) return [];
  const rows = (live as { findings?: SurfaceFinding[] }).findings;
  if (!Array.isArray(rows)) return [];
  return rows.filter(
    (row) =>
      row &&
      (String(row.dimension || "") === "surface" ||
        String(row.detail || "").startsWith("surface:")),
  );
}

export function surfaceGateBlocksInstall(
  draft: Record<string, unknown> | null | undefined,
): boolean {
  return surfaceGateFindingsFromDraft(draft).length > 0;
}

/** Quality-score / closer finished — not “Apply to Odoo is allowed”. */
export function draftFinisherComplete(
  draft: Record<string, unknown> | null | undefined,
): boolean {
  if (!draft) return false;
  if (draft._generation_incomplete) return false;
  if (isStockReuseDraft(draft) || isRefuseCloneDraft(draft)) {
    return true;
  }
  if (draft._component && draft._senior_shape) return true;
  return Boolean(draft._scorecard) || Boolean(draft._odoo_app_bar);
}

export function busyLabelFromJobResult(result: Record<string, unknown> | null | undefined): string | null {
  const phase = result?.user_phase_label;
  if (typeof phase === "string" && phase.trim()) return phase;
  const step = result?.step_label;
  if (typeof step === "string" && step.trim()) return `${step}…`;
  return null;
}
