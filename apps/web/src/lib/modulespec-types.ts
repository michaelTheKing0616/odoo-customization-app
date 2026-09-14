/** ModuleSpec IR types — structured editor contract, not a live Odoo write. */

export type ModuleSpecField = {
  name: string;
  ttype?: string;
  string?: string;
  required?: boolean;
  readonly?: boolean;
  relation?: string | null;
  relation_field?: string | null;
  selection?: string | null;
  help?: string | null;
};

export type ModuleSpecModel = {
  model: string;
  description?: string;
  mode?: string;
  mixins?: string[];
  is_workflow?: boolean;
  fields?: ModuleSpecField[];
};

export type ModuleSpecView = {
  name?: string;
  model?: string;
  type?: string;
  arch?: string;
  mode?: string;
  inherit_id?: string | null;
};

export type ModuleSpecMenu = {
  name?: string;
  sequence?: number;
  technical_name?: string;
  xml_id?: string;
  parent_xml_id?: string;
  action_xml_id?: string;
};

export type ModuleSpecAccessRule = {
  id?: string;
  name?: string;
  model?: string;
  group?: string;
  perm_read?: number | boolean;
  perm_write?: number | boolean;
  perm_create?: number | boolean;
  perm_unlink?: number | boolean;
};

export type ModuleSpecDoc = {
  technical_name?: string;
  display_name?: string;
  depends?: string[];
  models?: ModuleSpecModel[];
  views?: ModuleSpecView[];
  menus?: ModuleSpecMenu[];
  actions?: unknown[];
  access_rules?: ModuleSpecAccessRule[];
  smart_buttons?: Array<Record<string, unknown>>;
  automations?: Array<Record<string, unknown>>;
  custom_code_blocks?: Array<Record<string, unknown>>;
  unmapped?: Array<Record<string, unknown>>;
  include_barcode_scan_widget?: boolean;
  [key: string]: unknown;
};

export type ModuleSpecSection =
  | "models"
  | "views"
  | "menus"
  | "security"
  | "relations"
  | "extras"
  | "custom_code";

export const MODULESPEC_SECTIONS: Array<{ id: ModuleSpecSection; label: string }> = [
  { id: "models", label: "Models" },
  { id: "views", label: "Views" },
  { id: "menus", label: "Menus" },
  { id: "security", label: "Security" },
  { id: "relations", label: "Relations" },
  { id: "extras", label: "Automations" },
  { id: "custom_code", label: "Custom code" },
];

export const MODULESPEC_TTYPES = [
  "char",
  "text",
  "integer",
  "float",
  "boolean",
  "date",
  "datetime",
  "selection",
  "many2one",
  "one2many",
  "many2many",
  "binary",
  "html",
  "monetary",
  "json",
] as const;

export function emptyModuleSpec(): ModuleSpecDoc {
  return {
    technical_name: "custom_app",
    display_name: "Custom App",
    depends: ["base"],
    models: [],
  };
}

export function cloneModuleSpec(spec: ModuleSpecDoc): ModuleSpecDoc {
  return JSON.parse(JSON.stringify(spec)) as ModuleSpecDoc;
}

export function ensureModels(spec: ModuleSpecDoc): ModuleSpecModel[] {
  return Array.isArray(spec.models) ? [...spec.models] : [];
}

export function ensureViews(spec: ModuleSpecDoc): ModuleSpecView[] {
  return Array.isArray(spec.views) ? [...spec.views] : [];
}

export function ensureMenus(spec: ModuleSpecDoc): ModuleSpecMenu[] {
  return Array.isArray(spec.menus) ? [...spec.menus] : [];
}

export function ensureAccessRules(spec: ModuleSpecDoc): ModuleSpecAccessRule[] {
  return Array.isArray(spec.access_rules) ? [...spec.access_rules] : [];
}

export function customCodeBlocks(spec: ModuleSpecDoc): Array<Record<string, unknown>> {
  if (Array.isArray(spec.custom_code_blocks)) return spec.custom_code_blocks;
  if (Array.isArray(spec.unmapped)) return spec.unmapped;
  return [];
}

export function asRecordList(value: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(value)) return [];
  return value.filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === "object");
}
