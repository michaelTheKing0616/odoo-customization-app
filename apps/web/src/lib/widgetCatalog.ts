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

export const WIDGET_OPTION_PRESETS: Record<string, { label: string; options: string }[]> = {
  image: IMAGE_SIZE_PRESETS,
  many2many_tags: [
    { label: "No create", options: '{"no_create": true}' },
    { label: "Color from color field", options: '{"color_field": "color"}' },
  ],
  radio: [{ label: "Horizontal", options: '{"horizontal": true}' }],
  phone: [{ label: "Enable SMS", options: '{"enable_sms": true}' }],
  progressbar: [{ label: "Current / max", options: '{"max_value": "x_max"}' }],
};

export const CSS_CLASS_PRESETS: { value: string; label: string }[] = [
  { value: "oe_inline", label: "Inline" },
  { value: "oe_avatar", label: "Avatar" },
  { value: "oe_highlight", label: "Highlight" },
  { value: "o_address_type", label: "Address type" },
];

export const GROUP_XML_PRESETS: { xmlId: string; label: string }[] = [
  { xmlId: "base.group_user", label: "Internal user" },
  { xmlId: "base.group_system", label: "Settings" },
  { xmlId: "base.group_erp_manager", label: "Access rights" },
  { xmlId: "base.group_portal", label: "Portal" },
];

export const PLACEHOLDER_TTYPES = new Set([
  "char",
  "text",
  "html",
  "many2one",
  "integer",
  "float",
  "monetary",
  "date",
  "datetime",
]);

export type GroupVisibilityToken = { xmlId: string; forbid: boolean };

export function parseGroupsAttr(raw: string | undefined): GroupVisibilityToken[] {
  if (!raw?.trim()) return [];
  return raw
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean)
    .map((tok) => {
      const forbid = tok.startsWith("!");
      return { xmlId: forbid ? tok.slice(1).trim() : tok, forbid };
    })
    .filter((t) => t.xmlId);
}

export function serializeGroupsAttr(tokens: GroupVisibilityToken[]): string | undefined {
  const cleaned = tokens
    .map((t) => ({ xmlId: t.xmlId.trim(), forbid: t.forbid }))
    .filter((t) => t.xmlId);
  if (!cleaned.length) return undefined;
  return cleaned.map((t) => (t.forbid ? `!${t.xmlId}` : t.xmlId)).join(",");
}

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
