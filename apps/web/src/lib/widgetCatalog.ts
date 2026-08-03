/** Curated Odoo field widgets (mirrors packages/odoo-client widget_catalog.py). */

export type WidgetOption = {
  id: string;
  label: string;
  hint?: string;
};

export const IMAGE_SIZE_PRESETS: { label: string; options: string }[] = [
  { label: "90 × 90", options: '{"size": [90, 90]}' },
  { label: "128 × 128", options: '{"size": [128, 128]}' },
  { label: "256 × 256", options: '{"size": [256, 256]}' },
];

const FALLBACK: Record<string, WidgetOption[]> = {
  char: [
    { id: "email", label: "Email" },
    { id: "phone", label: "Phone" },
    { id: "url", label: "URL" },
    { id: "barcode", label: "Barcode" },
  ],
  integer: [{ id: "priority", label: "Priority" }],
  float: [
    { id: "float_time", label: "Float time" },
    { id: "progressbar", label: "Progress bar" },
    { id: "percentage", label: "Percentage" },
  ],
  selection: [
    { id: "radio", label: "Radio" },
    { id: "priority", label: "Priority" },
    { id: "selection_badge", label: "Badge" },
  ],
  many2many: [
    { id: "many2many_tags", label: "Tags" },
    { id: "many2many_checkboxes", label: "Checkboxes" },
  ],
  many2one: [
    { id: "many2one_avatar", label: "Avatar" },
    { id: "many2one_avatar_user", label: "User avatar" },
  ],
  binary: [
    { id: "image", label: "Image" },
    { id: "pdf_viewer", label: "PDF viewer" },
    { id: "signature", label: "Signature" },
  ],
  html: [{ id: "html", label: "HTML" }],
};

export function fallbackWidgetsForTtype(ttype: string): WidgetOption[] {
  return FALLBACK[ttype] ?? [];
}

export type FieldModifierMode = "off" | "always" | "domain";

export function modifierToMode(value: boolean | string | undefined): FieldModifierMode {
  if (value === true || value === "1") return "always";
  if (typeof value === "string" && value.trim() && value !== "0") return "domain";
  return "off";
}

export function modeToModifier(mode: FieldModifierMode, domain: string): boolean | string | undefined {
  if (mode === "always") return true;
  if (mode === "domain") {
    const d = domain.trim();
    return d && d !== "[]" ? d : undefined;
  }
  return undefined;
}
