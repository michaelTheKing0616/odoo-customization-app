/**
 * Pure Designer canvas model — types + mapping helpers.
 * Extracted from designer/page.tsx (strangler Phase 1).
 */
import type { FieldRow } from "@/lib/api";

export type ViewType =
  | "form"
  | "list"
  | "search"
  | "kanban"
  | "calendar"
  | "graph"
  | "pivot"
  | "map"
  | "activity"
  | "gantt"
  | "cohort"
  | "grid";

export type AxisDesignerField = {
  id: string;
  name: string;
  type?: "row" | "col" | "measure";
  interval?: string;
  string?: string;
};

export type DesignerField = {
  kind: "field";
  id: string;
  name: string;
  string?: string;
  required?: boolean | string;
  readonly?: boolean | string;
  invisible?: boolean | string;
  widget?: string;
  options?: string;
  help?: string;
  placeholder?: string;
  class_name?: string;
  groups?: string;
};

export type DesignerButton = {
  kind: "button";
  id: string;
  string: string;
  name?: string;
  type?: string;
  class_name?: string;
  icon?: string;
  context?: string;
  count_field?: string;
};

export type DesignerGroup = {
  kind: "group";
  id: string;
  string?: string;
  children: Array<DesignerField | DesignerButton>;
};

export type DesignerPage = {
  id: string;
  string: string;
  children: Array<DesignerField | DesignerButton>;
};

export type DesignerNotebook = {
  kind: "notebook";
  id: string;
  pages: DesignerPage[];
};

export type FormChild = DesignerGroup | DesignerNotebook;

export type ButtonPlacement = "header" | "button_box" | "inline";

export type BindDialogMode =
  | "closed"
  | "create_update"
  | "create_related"
  | "create_activity"
  | "create_mail"
  | "create_smart"
  | "bind_existing";

export type SearchFilter = {
  id: string;
  name: string;
  string: string;
  domain?: string;
};

export type SearchGroupByFilter = {
  id: string;
  name: string;
  string: string;
  context?: string;
};

/** Canvas bits session undo/redo snapshots. Keep JSON-small; cap is in designerHistory. */
export type DesignerCanvasSnapshot = {
  title: string;
  formChildren: FormChild[];
  headerButtons: DesignerButton[];
  buttonBox: DesignerButton[];
  statusbarField: string;
  statusbarVisible: string;
  formCanCreate: boolean;
  formCanEdit: boolean;
  formCanDelete: boolean;
  formCanDuplicate: boolean;
  listColumns: DesignerField[];
  listDecorationDanger: string;
  listDecorationInfo: string;
  listDecorationMuted: string;
  listCanCreate: boolean;
  listCanEdit: boolean;
  listCanDelete: boolean;
  listMultiEdit: boolean;
  listDefaultOrder: string;
  viewSample: boolean;
  searchFields: DesignerField[];
  searchFilters: SearchFilter[];
  searchGroupByFilters: SearchGroupByFilter[];
  kanbanFields: DesignerField[];
  kanbanGroupBy: string;
  kanbanCanCreate: boolean;
  kanbanQuickCreate: boolean;
  calendarDateStart: string;
  calendarDateStop: string;
  calendarColor: string;
  calendarMode: string;
  calendarFields: DesignerField[];
  graphType: "bar" | "line" | "pie";
  graphFields: AxisDesignerField[];
  pivotFields: AxisDesignerField[];
  mapResPartner: string;
  mapRouting: boolean;
  mapFields: DesignerField[];
  activityFields: DesignerField[];
  ganttDateStart: string;
  ganttDateStop: string;
  ganttGroupBy: string;
  ganttColor: string;
  ganttProgress: string;
  ganttDefaultScale: string;
  ganttDependencyField: string;
  ganttFields: DesignerField[];
  cohortDateStart: string;
  cohortDateStop: string;
  cohortInterval: "day" | "week" | "month" | "year" | "";
  cohortMode: "retention" | "churn" | "";
  cohortTimeline: "forward" | "backward" | "";
  cohortMeasure: string;
  gridRowField: string;
  gridColField: string;
  gridMeasure: string;
  gridAdjustment: string;
  gridDateStart: string;
  gridDateStop: string;
  gridFields: DesignerField[];
  archOverride: string | null;
};

export function asSpecBool(v: unknown): boolean | null {
  if (typeof v === "boolean") return v;
  return null;
}


export type SelectedField =
  | { scope: "form-group"; groupId: string; fieldId: string }
  | { scope: "form-page"; notebookId: string; pageId: string; fieldId: string }
  | { scope: "list"; fieldId: string }
  | { scope: "search"; fieldId: string }
  | { scope: "kanban"; fieldId: string };

let _uidSeq = 0;

export function uid(prefix: string) {
  // Deterministic counter (same call count on SSR + hydrate). Do not use Math.random /
  // crypto.randomUUID in render or useState initializers — they mismatch across the wire.
  _uidSeq += 1;
  return `${prefix}_${_uidSeq}`;
}

/** Stable seed for first paint (no uid() in the useState initializer). */
export const INITIAL_FORM_CHILDREN: FormChild[] = [
  { kind: "group", id: "g_main", string: "Main", children: [] },
];

export function fieldSpec(f: DesignerField) {
  return {
    kind: "field" as const,
    name: f.name,
    string: f.string,
    required: f.required,
    readonly: f.readonly,
    invisible: f.invisible || undefined,
    widget: f.widget || undefined,
    options: f.options || undefined,
    help: f.help || undefined,
    placeholder: f.placeholder || undefined,
    class_name: f.class_name || undefined,
    groups: f.groups || undefined,
  };
}

export function mapParsedField(n: Record<string, unknown>): DesignerField {
  return {
    kind: "field",
    id: uid("f"),
    name: String(n.name || ""),
    string: n.string ? String(n.string) : undefined,
    required: n.required as boolean | string | undefined,
    readonly: n.readonly as boolean | string | undefined,
    invisible: n.invisible as boolean | string | undefined,
    widget: n.widget ? String(n.widget) : undefined,
    options: n.options ? String(n.options) : undefined,
    help: n.help ? String(n.help) : undefined,
    placeholder: n.placeholder ? String(n.placeholder) : undefined,
    class_name: n.class
      ? String(n.class)
      : n.class_name
        ? String(n.class_name)
        : undefined,
    groups: n.groups ? String(n.groups) : undefined,
  };
}

/** Flatten nested groups from parse; drop empty-name fields (invalid Odoo arch). */
export function mapFormGroupChildren(
  kids: Array<Record<string, unknown>>,
): Array<DesignerField | DesignerButton> {
  const out: Array<DesignerField | DesignerButton> = [];
  for (const n of kids) {
    const kind = String(n.kind || "");
    if (kind === "group" && Array.isArray(n.children)) {
      out.push(
        ...mapFormGroupChildren(n.children as Array<Record<string, unknown>>),
      );
      continue;
    }
    if (kind === "notebook") {
      // Nested notebooks inside a group are rare; skip rather than emit blank fields.
      continue;
    }
    if (kind === "button") {
      out.push(mapParsedButton(n));
      continue;
    }
    const name = String(n.name || "").trim();
    if (!name) continue;
    out.push(mapParsedField({ ...n, name }));
  }
  return out;
}

export function resolveFieldLabel(
  name: string,
  string: string | undefined,
  rows: FieldRow[],
): string | undefined {
  return string || rows.find((f) => f.name === name)?.field_description || undefined;
}

export function isDateLikeField(f: Pick<FieldRow, "ttype">): boolean {
  return f.ttype === "date" || f.ttype === "datetime";
}

/** Prefer custom x_* dates over create_date/write_date for calendar/gantt/cohort. */
export function sortedDateFields(rows: FieldRow[]): FieldRow[] {
  const rank = (name: string) => {
    if (name === "create_date" || name === "write_date") return 2;
    if (name.startsWith("x_")) return 0;
    return 1;
  };
  return rows
    .filter(isDateLikeField)
    .slice()
    .sort((a, b) => rank(a.name) - rank(b.name) || a.name.localeCompare(b.name));
}

export function pickTemporalDefaults(rows: FieldRow[]): {
  dateStart: string;
  dateStop: string;
} {
  const dates = sortedDateFields(rows);
  const byName = (n: string) => dates.find((f) => f.name === n)?.name;
  const dateStart =
    byName("x_loan_date") ||
    byName("x_date_start") ||
    byName("x_start") ||
    dates.find((f) => f.name.startsWith("x_"))?.name ||
    dates.find((f) => f.name !== "write_date")?.name ||
    dates[0]?.name ||
    "";
  const dateStop =
    byName("x_due_date") ||
    byName("x_date_stop") ||
    byName("x_date_end") ||
    byName("x_end") ||
    dates.find((f) => f.name !== dateStart && f.name.startsWith("x_"))?.name ||
    "";
  return { dateStart, dateStop };
}

export function nodeSpec(n: DesignerField | DesignerButton) {
  if (n.kind === "button") {
    return {
      kind: "button" as const,
      string: n.string,
      name: n.name,
      type: n.type || "action",
      class: n.class_name,
      icon: n.icon,
      context: n.context,
      count_field: n.count_field,
    };
  }
  return fieldSpec(n);
}

export function parseSelectionOptions(raw: string | null | undefined): Array<{ value: string; label: string }> {
  if (!raw) return [];
  const out: Array<{ value: string; label: string }> = [];
  const re = /\(\s*'((?:\\'|[^'])*)'\s*,\s*'((?:\\'|[^'])*)'\s*\)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(raw))) {
    out.push({ value: m[1].replace(/\\'/g, "'"), label: m[2].replace(/\\'/g, "'") });
  }
  if (!out.length) {
    const re2 = /\(\s*"((?:\\"|[^"])*)"\s*,\s*"((?:\\"|[^"])*)"\s*\)/g;
    while ((m = re2.exec(raw))) {
      out.push({ value: m[1].replace(/\\"/g, '"'), label: m[2].replace(/\\"/g, '"') });
    }
  }
  return out;
}

export function mapParsedButton(n: Record<string, unknown>): DesignerButton {
  return {
    kind: "button",
    id: uid("b"),
    string: String(n.string || "Button"),
    name: n.name ? String(n.name) : undefined,
    type: n.type ? String(n.type) : "action",
    class_name: n.class ? String(n.class) : n.class_name ? String(n.class_name) : undefined,
    icon: n.icon ? String(n.icon) : undefined,
    context: n.context ? String(n.context) : undefined,
    count_field: n.count_field ? String(n.count_field) : undefined,
  };
}

