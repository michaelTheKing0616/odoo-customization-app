import type { FieldRow } from "@/lib/api";
import type { SelectionRow } from "@/components/SelectionEditor";
import { parseSelectionInput } from "@/components/SelectionEditor";

export const CONFIRM_PHRASE = "I understand the risks";

export const FIELD_TYPES = [
  "char",
  "text",
  "integer",
  "float",
  "boolean",
  "date",
  "datetime",
  "html",
  "binary",
  "selection",
  "many2one",
  "many2many",
  "one2many",
  "monetary",
  "json",
] as const;

export type FieldTtype = (typeof FIELD_TYPES)[number];

export type FieldTypeGroupId = "text" | "number" | "choice" | "date" | "relation" | "file" | "other";

export const FIELD_TYPE_GROUPS: {
  id: FieldTypeGroupId;
  label: string;
  types: readonly FieldTtype[];
}[] = [
  { id: "text", label: "Text", types: ["char", "text", "html"] },
  { id: "number", label: "Number", types: ["integer", "float", "monetary"] },
  { id: "choice", label: "Choice", types: ["boolean", "selection"] },
  { id: "date", label: "Date", types: ["date", "datetime"] },
  { id: "relation", label: "Relation", types: ["many2one", "many2many", "one2many"] },
  { id: "file", label: "File", types: ["binary"] },
  { id: "other", label: "Other", types: ["json"] },
];

const FIELD_TYPE_LABELS: Record<FieldTtype, string> = {
  char: "Text",
  text: "Multiline text",
  integer: "Integer",
  float: "Decimal",
  boolean: "Checkbox",
  date: "Date",
  datetime: "Date and time",
  html: "HTML",
  binary: "File",
  selection: "Selection",
  many2one: "Many to one",
  many2many: "Many to many",
  one2many: "One to many",
  monetary: "Monetary",
  json: "JSON",
};

export function fieldTypeLabel(ttype: string): string {
  return FIELD_TYPE_LABELS[ttype as FieldTtype] ?? ttype;
}

export function slugifyTechnical(label: string, prefix = "x_"): string {
  const base = label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  const body = base || "custom";
  return body.startsWith("x_") ? body : `${prefix}${body}`;
}

export type ModelComposerForm = {
  name: string;
  model: string;
  enable_mail_thread: boolean;
};

export type FieldComposerForm = {
  model: string;
  name: string;
  field_description: string;
  ttype: string;
  required: boolean;
  readonly: boolean;
  tracking: boolean;
  relation: string;
  relation_field: string;
  selectionRows: SelectionRow[];
  help: string;
  related: string;
  currency_field: string;
  on_delete: "set null" | "restrict" | "cascade";
  inject_into_views: boolean;
  inject_strategy: "inherit" | "mutate";
  view_widget: string;
};

export type O2mComposerForm = {
  parent_model: string;
  child_model: string;
  parent_o2m_name: string;
  child_m2o_name: string;
  parent_o2m_string: string;
  child_m2o_string: string;
  inject_into_views: boolean;
};

export const DEFAULT_SELECTION_ROWS: SelectionRow[] = [
  { value: "draft", label: "Draft" },
  { value: "done", label: "Done" },
];

export function defaultModelForm(): ModelComposerForm {
  return { name: "", model: "x_", enable_mail_thread: false };
}

export function defaultFieldForm(model = "res.partner"): FieldComposerForm {
  return {
    model,
    name: "x_",
    field_description: "",
    ttype: "char",
    required: false,
    readonly: false,
    tracking: false,
    relation: "",
    relation_field: "",
    selectionRows: DEFAULT_SELECTION_ROWS.map((r) => ({ ...r })),
    help: "",
    related: "",
    currency_field: "currency_id",
    on_delete: "restrict",
    inject_into_views: true,
    inject_strategy: "inherit",
    view_widget: "",
  };
}

export function defaultO2mForm(parentModel = ""): O2mComposerForm {
  return {
    parent_model: parentModel,
    child_model: "",
    parent_o2m_name: "x_line_ids",
    child_m2o_name: "x_parent_id",
    parent_o2m_string: "Lines",
    child_m2o_string: "Parent",
    inject_into_views: true,
  };
}

export type BuilderSessionState = "draft" | "unsaved" | "saved";

export function composerSessionState(opts: {
  dirty: boolean;
  savedOnce: boolean;
}): BuilderSessionState {
  if (opts.dirty) return "unsaved";
  if (opts.savedOnce) return "saved";
  return "draft";
}

export function isComposerDirty<T>(form: T, baseline: T): boolean {
  return JSON.stringify(form) !== JSON.stringify(baseline);
}

export function needsRelation(ttype: string): boolean {
  return ttype === "many2one" || ttype === "many2many" || ttype === "one2many";
}

export function needsOnDelete(ttype: string): boolean {
  return ttype === "many2one";
}

export function needsSelection(ttype: string): boolean {
  return ttype === "selection";
}

export function needsCurrency(ttype: string): boolean {
  return ttype === "monetary";
}

export function selectionRowsFromField(selection: string | null | undefined): SelectionRow[] {
  if (!selection?.trim()) return DEFAULT_SELECTION_ROWS.map((r) => ({ ...r }));
  const parsed = parseSelectionInput(selection);
  return parsed.length ? parsed : DEFAULT_SELECTION_ROWS.map((r) => ({ ...r }));
}

export function fieldFormFromRow(row: FieldRow, model: string): FieldComposerForm {
  return {
    ...defaultFieldForm(model),
    name: row.name,
    field_description: row.field_description || "",
    ttype: row.ttype,
    required: Boolean(row.required),
    readonly: Boolean(row.readonly),
    tracking: Boolean(row.tracking),
    relation: row.relation || "",
    relation_field: row.relation_field || "",
    selectionRows: selectionRowsFromField(row.selection),
    help: row.help || "",
    related: row.related || "",
    currency_field: row.currency_field || "currency_id",
  };
}

export function filterByQuery<T>(
  rows: T[],
  query: string,
  haystack: (row: T) => string,
): T[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return rows;
  return rows.filter((row) => haystack(row).toLowerCase().includes(needle));
}

export const MODEL_DELETE_RISKS = [
  "Often irreversible — tables and data may not restore",
  "Dependent views and automations can break",
  "Snapshot stores definition only (partial)",
];

export const FIELD_DELETE_RISKS = [
  "Deprecate keeps column data under x_deprecated_*",
  "Hard delete exports CSV then drops the column",
  "Views referencing the old name may need updates",
];

export function isCustomTechnicalName(name: string): boolean {
  return name.startsWith("x_");
}

export function viewDesignerHref(connectionId: string, model: string): string {
  const base = `/connections/${connectionId}/designer`;
  const trimmed = model.trim();
  return trimmed ? `${base}?model=${encodeURIComponent(trimmed)}` : base;
}

export function automationsHref(connectionId: string, model: string): string {
  const base = `/connections/${connectionId}/automations`;
  const trimmed = model.trim();
  return trimmed ? `${base}?model=${encodeURIComponent(trimmed)}` : base;
}

export function fieldSubmitPayload(form: FieldComposerForm): {
  selection: { value: string; label: string }[] | null;
  relatedPath: string | null;
} {
  const selection = needsSelection(form.ttype)
    ? form.selectionRows
        .filter((r) => r.value.trim())
        .map((r) => ({
          value: r.value.trim(),
          label: (r.label.trim() || r.value).trim(),
        }))
    : null;
  const relatedPath = form.related.trim() || null;
  return { selection, relatedPath };
}

export function createdModelNotice(opts: {
  model: string;
  mailRequested: boolean;
  mailEnabled?: boolean;
  warnings?: string[];
}): string {
  const mailNote = opts.mailRequested
    ? opts.mailEnabled
      ? " Mail thread flag set on ir.model."
      : ` Chatter: ${(opts.warnings || []).join(" ") || "export mixins for full chatter."}`
    : "";
  return `Created model ${opts.model} with x_name, default list/form/search views, and Internal User ACL.${mailNote}`;
}

export function createdFieldNotice(opts: {
  name: string;
  model: string;
  injectedViewIds?: number[];
  wantedInject: boolean;
  currencyFieldCreated?: string | null;
}): string {
  const injected =
    (opts.injectedViewIds?.length ?? 0) > 0
      ? ` Injected into view(s) ${opts.injectedViewIds!.join(", ")}.`
      : opts.wantedInject
        ? " (no existing form/list/search to inject into)"
        : "";
  const currencyNote = opts.currencyFieldCreated
    ? ` Auto-created currency field ${opts.currencyFieldCreated}.`
    : "";
  return `Created field ${opts.name} on ${opts.model}.${injected}${currencyNote}`;
}
