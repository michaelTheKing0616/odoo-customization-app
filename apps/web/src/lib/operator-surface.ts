/** Read `_operator_surface` from a ModuleSpec draft for Wizard discoverability. */

export type OperatorSurfaceHostButton = {
  host_model: string;
  host_label: string;
  button_label: string;
  residual_model: string;
};

export type OperatorSurfaceResidualButton = {
  on_model: string;
  related_model: string;
  button_label: string;
};

export type OperatorSurfaceStockLink = {
  field: string;
  field_label: string;
  stock_model: string;
  stock_label: string;
  on_model: string;
};

export type OperatorSurface = {
  app_menu?: { label?: string; technical_name?: string } | null;
  host_buttons: OperatorSurfaceHostButton[];
  residual_buttons: OperatorSurfaceResidualButton[];
  stock_links: OperatorSurfaceStockLink[];
  summary: string;
  display_name?: string;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export function operatorSurfaceFromDraft(draft: unknown): OperatorSurface | null {
  const rec = asRecord(draft);
  if (!rec) return null;
  const raw = asRecord(rec._operator_surface);
  if (!raw) return null;

  const host_buttons: OperatorSurfaceHostButton[] = [];
  for (const row of Array.isArray(raw.host_buttons) ? raw.host_buttons : []) {
    const b = asRecord(row);
    if (!b) continue;
    const host_model = asString(b.host_model);
    const host_label = asString(b.host_label) || host_model;
    const button_label = asString(b.button_label) || "Open";
    const residual_model = asString(b.residual_model);
    if (!host_model || !residual_model) continue;
    host_buttons.push({ host_model, host_label, button_label, residual_model });
  }

  const residual_buttons: OperatorSurfaceResidualButton[] = [];
  for (const row of Array.isArray(raw.residual_buttons) ? raw.residual_buttons : []) {
    const b = asRecord(row);
    if (!b) continue;
    const on_model = asString(b.on_model);
    const related_model = asString(b.related_model);
    const button_label = asString(b.button_label) || "Open";
    if (!on_model || !related_model) continue;
    residual_buttons.push({ on_model, related_model, button_label });
  }

  const stock_links: OperatorSurfaceStockLink[] = [];
  for (const row of Array.isArray(raw.stock_links) ? raw.stock_links : []) {
    const b = asRecord(row);
    if (!b) continue;
    const field = asString(b.field);
    const stock_model = asString(b.stock_model);
    if (!field || !stock_model) continue;
    stock_links.push({
      field,
      field_label: asString(b.field_label) || field,
      stock_model,
      stock_label: asString(b.stock_label) || stock_model,
      on_model: asString(b.on_model),
    });
  }

  const menuRaw = asRecord(raw.app_menu);
  const app_menu = menuRaw
    ? {
        label: asString(menuRaw.label) || undefined,
        technical_name: asString(menuRaw.technical_name) || undefined,
      }
    : null;

  const summary = asString(raw.summary);
  const hasContent =
    Boolean(app_menu?.label) ||
    host_buttons.length > 0 ||
    residual_buttons.length > 0 ||
    stock_links.length > 0 ||
    Boolean(summary);
  if (!hasContent) return null;

  return {
    app_menu,
    host_buttons,
    residual_buttons,
    stock_links,
    summary,
    display_name: asString(raw.display_name) || undefined,
  };
}

export function operatorSurfaceHasPlacement(surface: OperatorSurface | null): boolean {
  if (!surface) return false;
  return (
    Boolean(surface.app_menu?.label) ||
    surface.host_buttons.length > 0 ||
    surface.residual_buttons.length > 0 ||
    surface.stock_links.length > 0
  );
}
