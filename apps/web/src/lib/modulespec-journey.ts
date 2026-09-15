/** ModuleSpec journey — chrome only, not the apply/export engines. */

import type { ValidateLiveItem, ValidateLiveResult } from "@/lib/api";
import { actionErrorTitle } from "@/lib/action-error-title";
import { SCORE_BARS } from "@/lib/copy-guide";
import { isStockReuseDraft } from "@/lib/draft-form-preview";
import {
  certificationFromDraft,
  scorecardFromDraft,
  type DraftCertification,
  type DraftScorecard,
} from "@/lib/draft-studio-journey";
import {
  customCodeBlocks,
  emptyModuleSpec,
  ensureAccessRules,
  ensureMenus,
  ensureModels,
  ensureViews,
  type ModuleSpecDoc,
  type ModuleSpecField,
  type ModuleSpecModel,
} from "@/lib/modulespec-types";

export const MODULESPEC_STAGES = [
  { id: "load", label: "Load" },
  { id: "edit", label: "Edit" },
  { id: "validate", label: "Validate" },
  { id: "apply", label: "Apply" },
] as const;

export type ModuleSpecJourneyId = (typeof MODULESPEC_STAGES)[number]["id"];

export type ModuleSpecJourneyState = {
  id: ModuleSpecJourneyId;
  failed?: boolean;
  applied?: boolean;
};

export type ModuleSpecSessionState = "draft" | "unsaved" | "saved";

export type ModuleSpecBusy =
  | "load"
  | "save"
  | "import"
  | "validate"
  | "apply"
  | "zip"
  | "sandbox"
  | "lint"
  | "walkthrough"
  | null;

export type ModuleSpecSummary = {
  models: number;
  fields: number;
  views: number;
  menus: number;
  access: number;
  smart: number;
  autos: number;
  customCode: number;
};

export type LocalReadinessStatus = "pass" | "warn" | "fail" | "skip";

export type LocalReadinessItem = {
  id: string;
  label: string;
  status: LocalReadinessStatus;
  message: string;
};

export type LocalReadinessReport = {
  items: LocalReadinessItem[];
  failCount: number;
  warnCount: number;
  passCount: number;
  applyBlocked: boolean;
  headline: string;
  body: string;
};

const RELATIONAL_TYPES = new Set(["many2one", "one2many", "many2many"]);

export function moduleSpecSummary(spec: ModuleSpecDoc): ModuleSpecSummary {
  const models = ensureModels(spec);
  return {
    models: models.length,
    fields: models.reduce((n, model) => n + (model.fields?.length ?? 0), 0),
    views: ensureViews(spec).length,
    menus: ensureMenus(spec).length,
    access: ensureAccessRules(spec).length,
    smart: Array.isArray(spec.smart_buttons) ? spec.smart_buttons.length : 0,
    autos: Array.isArray(spec.automations) ? spec.automations.length : 0,
    customCode: customCodeBlocks(spec).length,
  };
}

export function hasModuleSpecContent(spec: ModuleSpecDoc | null | undefined): boolean {
  if (!spec) return false;
  if (isStockReuseDraft(spec as Record<string, unknown>)) return true;
  const summary = moduleSpecSummary(spec);
  return (
    summary.models > 0 ||
    summary.views > 0 ||
    summary.menus > 0 ||
    summary.customCode > 0 ||
    summary.access > 0
  );
}

export function isSpecDirty(spec: ModuleSpecDoc, baseline: ModuleSpecDoc): boolean {
  return JSON.stringify(spec) !== JSON.stringify(baseline);
}

export function moduleSpecSessionState(opts: {
  dirty: boolean;
  savedOnce: boolean;
  applied?: boolean;
}): ModuleSpecSessionState {
  if (opts.dirty) return "unsaved";
  if (opts.savedOnce || opts.applied) return "saved";
  return "draft";
}

export function moduleSpecJourneyFromState(opts: {
  hydrated?: boolean;
  hasContent?: boolean;
  busy?: ModuleSpecBusy;
  hasLiveValidation?: boolean;
  applied?: boolean;
  failed?: boolean;
}): ModuleSpecJourneyState {
  const failed = Boolean(opts.failed);
  if (opts.busy === "validate") return { id: "validate", failed };
  if (opts.busy === "apply" || opts.busy === "zip" || opts.busy === "sandbox") {
    return { id: "apply", failed, applied: Boolean(opts.applied) };
  }
  if (opts.applied) return { id: "apply", applied: true, failed };
  if (opts.hasLiveValidation || failed) return { id: "validate", failed };
  if (opts.hasContent) return { id: "edit", failed };
  void opts.hydrated;
  return { id: "load", failed };
}

export function moduleSpecJourneyHint(state: ModuleSpecJourneyState): string {
  if (state.failed && state.id === "validate") {
    return "Validation found issues. Fix the spec, then validate again. Completeness is not go-live. Promote stays human.";
  }
  if (state.failed && state.id === "apply") {
    return "Apply did not finish. Prefer sandbox first. Completeness ≠ Cert ≠ Autopilot. Promote stays human.";
  }
  switch (state.id) {
    case "load":
      return "Open a Draft Studio handoff, import a zip, or start a blank spec. Completeness is hygiene, not Certification.";
    case "edit":
      return "Edit models, fields, views, menus, and access as a workbench. JSON is an escape hatch. Completeness ≠ Cert ≠ Autopilot.";
    case "validate":
      return "Validate against this Odoo before Generate UI. Completeness is not Certification. Promote stays human.";
    case "apply":
      return "Generate UI writes live metadata. Zip and sandbox before promote. Completeness ≠ Cert ≠ Autopilot. Promote stays human.";
  }
}

export function moduleSpecHeaderDescription(
  connectionName?: string | null,
  projectName?: string | null,
): string {
  if (connectionName && projectName) {
    return `${connectionName} · ${projectName} — structured IR, then validate, then apply`;
  }
  if (connectionName) {
    return `${connectionName} · load, edit, validate, then apply. Completeness is not go-live`;
  }
  return "Structured IR for models, views, menus, and access. Validate, then apply. Promote stays human.";
}

export const MODULESPEC_ERROR_STEPS = {
  validate: "Validation failed",
  import: "Import failed",
  lint: "Lint found issues",
  zip: "Zip export failed",
  sandbox: "Sandbox failed",
  apply: "Generate UI failed",
  walkthrough: "Walkthrough seed failed",
  save: "Save failed",
  repair: "AI repair did not apply",
  load: "Could not load ModuleSpec",
} as const;

export type ModuleSpecErrorStep = keyof typeof MODULESPEC_ERROR_STEPS;

export function moduleSpecErrorTitle(
  stepOrMessage?: string | null,
  message?: string | null,
): string {
  return actionErrorTitle(
    stepOrMessage,
    MODULESPEC_ERROR_STEPS,
    "ModuleSpec request failed",
    message,
  );
}

export function primaryDesignerModel(spec: ModuleSpecDoc): string | null {
  const models = ensureModels(spec);
  const custom = models.find((row) => String(row.model || "").startsWith("x_"));
  const first = custom ?? models[0];
  const name = String(first?.model || "").trim();
  return name || null;
}

export function relationalFields(
  spec: ModuleSpecDoc,
): Array<{ model: string; field: ModuleSpecField }> {
  return ensureModels(spec).flatMap((model) =>
    (model.fields || [])
      .filter((field) => RELATIONAL_TYPES.has(String(field.ttype || "")))
      .map((field) => ({ model: model.model, field })),
  );
}

function scorecardFromSpec(spec: ModuleSpecDoc): DraftScorecard | undefined {
  return scorecardFromDraft(spec as Record<string, unknown>);
}

function certificationFromSpec(spec: ModuleSpecDoc): DraftCertification | undefined {
  return certificationFromDraft(spec as Record<string, unknown>);
}

export function completenessNote(spec: ModuleSpecDoc): string | null {
  const card = scorecardFromSpec(spec);
  if (typeof card?.score_0_10 !== "number") return null;
  const cert = certificationFromSpec(spec)?.tier;
  const certBit = cert ? ` Cert on this draft is ${cert} — not this bar.` : "";
  return `Completeness ${card.score_0_10.toFixed(1)}/10 is ModuleSpec hygiene, not go-live.${certBit}`;
}

function modelHasNamedFields(model: ModuleSpecModel): boolean {
  const fields = model.fields || [];
  return fields.some((field) => String(field.name || "").trim().length > 0);
}

function missingRelations(spec: ModuleSpecDoc): Array<{ model: string; field: string }> {
  return relationalFields(spec)
    .filter((row) => !String(row.field.relation || "").trim())
    .map((row) => ({ model: row.model, field: row.field.name }));
}

export function localReadiness(spec: ModuleSpecDoc): LocalReadinessReport {
  const summary = moduleSpecSummary(spec);
  const stockReuse = isStockReuseDraft(spec as Record<string, unknown>);
  const models = ensureModels(spec);
  const missingRel = missingRelations(spec);
  const unnamedModels = models.filter((model) => !String(model.model || "").trim());
  const hollowModels = models.filter((model) => !modelHasNamedFields(model));
  const customModels = models.filter((model) => String(model.model || "").startsWith("x_"));
  const views = ensureViews(spec);
  const modelsMissingViews = customModels.filter(
    (model) => !views.some((view) => view.model === model.model),
  );
  const items: LocalReadinessItem[] = [];

  const display = String(spec.display_name || "").trim();
  const technical = String(spec.technical_name || "").trim();
  if (!display || !technical) {
    items.push({
      id: "identity",
      label: "Identity",
      status: "fail",
      message: "Display name and technical name are required before apply.",
    });
  } else {
    items.push({
      id: "identity",
      label: "Identity",
      status: "pass",
      message: `${display} (${technical})`,
    });
  }

  if (stockReuse && summary.models === 0) {
    items.push({
      id: "models",
      label: "Models",
      status: "skip",
      message: "Empty ModuleSpec is correct for stock reuse. Open Job Autopilot — do not Generate UI.",
    });
  } else if (summary.models === 0) {
    items.push({
      id: "models",
      label: "Models",
      status: "fail",
      message: "No models yet. Load a draft, import a zip, or add an x_ model.",
    });
  } else if (unnamedModels.length) {
    items.push({
      id: "models",
      label: "Models",
      status: "fail",
      message: `${unnamedModels.length} model(s) are missing a technical name.`,
    });
  } else {
    items.push({
      id: "models",
      label: "Models",
      status: "pass",
      message: `${summary.models} model(s), ${summary.fields} field(s).`,
    });
  }

  if (!stockReuse && hollowModels.length) {
    items.push({
      id: "fields",
      label: "Fields",
      status: "warn",
      message: `${hollowModels.length} model(s) have no named fields.`,
    });
  } else if (summary.fields > 0) {
    items.push({
      id: "fields",
      label: "Fields",
      status: "pass",
      message: `${summary.fields} field(s) across ${summary.models} model(s).`,
    });
  }

  if (missingRel.length) {
    items.push({
      id: "relations",
      label: "Relations",
      status: "fail",
      message: `${missingRel.length} relational field(s) need a target model.`,
    });
  } else if (relationalFields(spec).length) {
    items.push({
      id: "relations",
      label: "Relations",
      status: "pass",
      message: `${relationalFields(spec).length} relational field(s) have a target.`,
    });
  }

  if (!stockReuse && summary.models > 0 && summary.views === 0) {
    items.push({
      id: "views",
      label: "Views",
      status: "warn",
      message: "No views in the spec. Generate UI can still emit defaults, but review the workbench first.",
    });
  } else if (modelsMissingViews.length) {
    items.push({
      id: "views",
      label: "Views",
      status: "warn",
      message: `${modelsMissingViews.length} custom model(s) have no view yet.`,
    });
  } else if (summary.views > 0) {
    items.push({
      id: "views",
      label: "Views",
      status: "pass",
      message: `${summary.views} view(s).`,
    });
  }

  if (!stockReuse && summary.models > 0 && summary.menus === 0) {
    items.push({
      id: "menus",
      label: "Menus",
      status: "warn",
      message: "No menus yet. Generate UI can write a default tree; review it before apply.",
    });
  } else if (summary.menus > 0) {
    items.push({
      id: "menus",
      label: "Menus",
      status: "pass",
      message: `${summary.menus} menu item(s).`,
    });
  }

  if (!stockReuse && summary.models > 0 && summary.access === 0) {
    items.push({
      id: "security",
      label: "Security",
      status: "warn",
      message: "No access rules in the spec. Apply may add Internal User ACL, but review security first.",
    });
  } else if (summary.access > 0) {
    items.push({
      id: "security",
      label: "Security",
      status: "pass",
      message: `${summary.access} access rule(s).`,
    });
  }

  if (summary.customCode > 0) {
    items.push({
      id: "custom_code",
      label: "Custom code",
      status: "warn",
      message: `${summary.customCode} block(s) skip live Generate UI. Export zip, sandbox, then promote.`,
    });
  }

  const failCount = items.filter((item) => item.status === "fail").length;
  const warnCount = items.filter((item) => item.status === "warn").length;
  const passCount = items.filter((item) => item.status === "pass").length;
  const applyBlocked = stockReuse || failCount > 0;

  return {
    items,
    failCount,
    warnCount,
    passCount,
    applyBlocked,
    headline: readinessHeadline({ stockReuse, failCount, warnCount, summary }),
    body: readinessBody({ stockReuse, failCount, warnCount, customCode: summary.customCode }),
  };
}

export function readinessHeadline(opts: {
  stockReuse?: boolean;
  failCount: number;
  warnCount: number;
  summary: ModuleSpecSummary;
}): string {
  if (opts.stockReuse) {
    return "Stock reuse — empty ModuleSpec is correct";
  }
  if (opts.failCount > 0) {
    return `${opts.failCount} blocking issue${opts.failCount === 1 ? "" : "s"} before apply`;
  }
  if (opts.warnCount > 0) {
    return `Ready to validate · ${opts.warnCount} review item${opts.warnCount === 1 ? "" : "s"}`;
  }
  if (opts.summary.models === 0) {
    return "Load a spec to begin";
  }
  return `Ready to validate · ${opts.summary.models} model(s), ${opts.summary.fields} field(s)`;
}

export function readinessBody(opts: {
  stockReuse?: boolean;
  failCount: number;
  warnCount: number;
  customCode: number;
}): string {
  if (opts.stockReuse) {
    return "Do not Generate UI. Job Autopilot is the done-bar for stock coverage. Completeness ≠ Cert ≠ Autopilot. Promote stays human.";
  }
  if (opts.failCount > 0) {
    return "Fix blocking issues, then validate on this Odoo. Completeness is ModuleSpec hygiene — not Certification or Autopilot.";
  }
  if (opts.customCode > 0) {
    return "Live Generate UI writes metadata only. Custom Python/XML needs zip → sandbox → promote. Completeness ≠ Cert ≠ Autopilot.";
  }
  if (opts.warnCount > 0) {
    return "Warnings do not block validate. Completeness is not go-live. Promote stays human.";
  }
  return "Validate against this connection, then Generate UI or export a zip. Completeness ≠ Cert ≠ Autopilot. Promote stays human.";
}

export function liveValidationHeadline(result: ValidateLiveResult | null): string | null {
  if (!result) return null;
  if (result.ok && result.fail_count === 0 && result.warn_count === 0) {
    return "Live validate passed";
  }
  if (result.ok && result.warn_count > 0) {
    return `Live validate passed with ${result.warn_count} warning${result.warn_count === 1 ? "" : "s"}`;
  }
  return `Live validate: ${result.fail_count} fail, ${result.warn_count} warn`;
}

export function liveItemTone(
  status: ValidateLiveItem["status"],
): LocalReadinessStatus {
  if (status === "pass") return "pass";
  if (status === "warn") return "warn";
  return "fail";
}

export function honestyLegend(): string[] {
  return [SCORE_BARS.completeness, SCORE_BARS.certification, SCORE_BARS.autopilot];
}

export function sessionSubmitHint(opts: {
  sessionState: ModuleSpecSessionState;
  projectId?: string | null;
  applied?: boolean;
}): string {
  if (opts.sessionState === "unsaved") {
    return opts.projectId ? "Save project to keep this IR" : "Save as project, or Generate UI when ready";
  }
  if (opts.applied) return "Last Generate UI wrote this connection. Review in Odoo or View Designer.";
  if (opts.sessionState === "saved") return "Last save is the baseline. Edit to mark unsaved.";
  return "Load a draft, then edit. Nothing writes to Odoo until Generate UI.";
}

export function downloadZipBase64(filename: string, zipBase64: string): void {
  const binary = atob(zipBase64);
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  const blob = new Blob([bytes], { type: "application/zip" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  const safe = filename.replace(/\.zip$/i, "") || "custom_module";
  anchor.href = url;
  anchor.download = `${safe}.zip`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function defaultModel(index: number): ModuleSpecModel {
  const n = index + 1;
  return {
    model: `x_new_model_${n}`,
    description: `New model ${n}`,
    mode: "new",
    fields: [{ name: "x_name", ttype: "char", string: "Name", required: true }],
  };
}

export { emptyModuleSpec };
