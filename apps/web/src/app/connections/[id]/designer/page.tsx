"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { DomainBuilder } from "@/components/DomainBuilder";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { CapabilityProbePanel } from "@/components/CapabilityProbePanel";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { FormCanvas } from "@/components/designer/FormCanvas";
import { KanbanCardPreview } from "@/components/designer/KanbanCardPreview";
import { FieldPalette } from "@/components/designer/FieldPalette";
import {
  NicheWidgetPalette,
  type NicheWidgetEntry,
} from "@/components/designer/NicheWidgetPalette";
import { PreviewThemeScope } from "@/components/designer/PreviewThemeScope";
import { PropsInspector } from "@/components/designer/PropsInspector";
import {
  ActivityTypeRow,
  api,
  API_BASE,
  ConfirmationRequiredError,
  Connection,
  FieldRow,
  MailTemplateRow,
  PreviewTheme,
  SnapshotRow,
} from "@/lib/api";
import { DesignerFieldInspector } from "@/components/designer/DesignerFieldInspector";
import { fallbackWidgetsForTtype, type WidgetOption } from "@/lib/widgetCatalog";
import { DesignerFieldInspector } from "@/components/designer/DesignerFieldInspector";
import { fallbackWidgetsForTtype, type WidgetOption } from "@/lib/widgetCatalog";
import {
  bindModeSupported,
  bindModeUnsupportedReason,
  connectionSupports,
  connectionUnsupportedReason,
  injectStrategyCapabilityId,
  mutationAllowed,
  mutationBlockedReason,
} from "@/lib/capabilities";
import { odooViewUrl, pickStandaloneWindowAction, sameOriginPreviewUrl } from "@/lib/odoo-urls";

type ViewType =
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
  | "cohort";

type AxisDesignerField = {
  id: string;
  name: string;
  type?: "row" | "col" | "measure";
  interval?: string;
  string?: string;
};

type DesignerField = {
  kind: "field";
  id: string;
  name: string;
  string?: string;
  required?: boolean | string;
  readonly?: boolean | string;
  invisible?: string;
  widget?: string;
  options?: string;
};

type DesignerButton = {
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

type DesignerGroup = {
  kind: "group";
  id: string;
  string?: string;
  children: Array<DesignerField | DesignerButton>;
};

type DesignerPage = {
  id: string;
  string: string;
  children: Array<DesignerField | DesignerButton>;
};

type DesignerNotebook = {
  kind: "notebook";
  id: string;
  pages: DesignerPage[];
};

type FormChild = DesignerGroup | DesignerNotebook;

type ButtonPlacement = "header" | "button_box" | "inline";

type BindDialogMode =
  | "closed"
  | "create_update"
  | "create_related"
  | "create_activity"
  | "create_mail"
  | "create_smart"
  | "bind_existing";

type SearchFilter = {
  id: string;
  name: string;
  string: string;
  domain?: string;
};

type SearchGroupByFilter = {
  id: string;
  name: string;
  string: string;
  context?: string;
};

function asSpecBool(v: unknown): boolean | null {
  if (typeof v === "boolean") return v;
  return null;
}

const CONFIRM_PHRASE = "I understand the risks";

type SelectedField =
  | { scope: "form-group"; groupId: string; fieldId: string }
  | { scope: "form-page"; notebookId: string; pageId: string; fieldId: string }
  | { scope: "list"; fieldId: string }
  | { scope: "search"; fieldId: string }
  | { scope: "kanban"; fieldId: string };

let _uidSeq = 0;

function uid(prefix: string) {
  // Deterministic counter (same call count on SSR + hydrate). Do not use Math.random /
  // crypto.randomUUID in render or useState initializers — they mismatch across the wire.
  _uidSeq += 1;
  return `${prefix}_${_uidSeq}`;
}

/** Stable seed for first paint (no uid() in the useState initializer). */
const INITIAL_FORM_CHILDREN: FormChild[] = [
  { kind: "group", id: "g_main", string: "Main", children: [] },
];

function fieldSpec(f: DesignerField) {
  return {
    kind: "field" as const,
    name: f.name,
    string: f.string,
    required: f.required,
    readonly: f.readonly,
    invisible: f.invisible || undefined,
    widget: f.widget || undefined,
    options: f.options || undefined,
  };
}

function mapParsedField(n: Record<string, unknown>): DesignerField {
  return {
    kind: "field",
    id: uid("f"),
    name: String(n.name || ""),
    string: n.string ? String(n.string) : undefined,
    required: n.required as boolean | string | undefined,
    readonly: n.readonly as boolean | string | undefined,
    invisible: n.invisible ? String(n.invisible) : undefined,
    widget: n.widget ? String(n.widget) : undefined,
    options: n.options ? String(n.options) : undefined,
  };
}

function resolveFieldLabel(
  name: string,
  string: string | undefined,
  rows: FieldRow[],
): string | undefined {
  return string || rows.find((f) => f.name === name)?.field_description || undefined;
}

function isDateLikeField(f: Pick<FieldRow, "ttype">): boolean {
  return f.ttype === "date" || f.ttype === "datetime";
}

/** Prefer custom x_* dates over create_date/write_date for calendar/gantt/cohort. */
function sortedDateFields(rows: FieldRow[]): FieldRow[] {
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

function pickTemporalDefaults(rows: FieldRow[]): {
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

function nodeSpec(n: DesignerField | DesignerButton) {
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

function parseSelectionOptions(raw: string | null | undefined): Array<{ value: string; label: string }> {
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

function mapParsedButton(n: Record<string, unknown>): DesignerButton {
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

export default function DesignerPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [probing, setProbing] = useState(false);
  const [model, setModel] = useState("");
  const [viewType, setViewType] = useState<ViewType>("form");
  const [title, setTitle] = useState("Form");
  const [fields, setFields] = useState<FieldRow[]>([]);
  const [fieldsModel, setFieldsModel] = useState("");
  const [formChildren, setFormChildren] =
    useState<FormChild[]>(INITIAL_FORM_CHILDREN);
  const [listColumns, setListColumns] = useState<DesignerField[]>([]);
  const [searchFields, setSearchFields] = useState<DesignerField[]>([]);
  const [kanbanFields, setKanbanFields] = useState<DesignerField[]>([]);
  const [kanbanGroupBy, setKanbanGroupBy] = useState("");
  const [calendarDateStart, setCalendarDateStart] = useState("");
  const [calendarDateStop, setCalendarDateStop] = useState("");
  const [calendarColor, setCalendarColor] = useState("");
  const [calendarMode, setCalendarMode] = useState("");
  const [calendarFields, setCalendarFields] = useState<DesignerField[]>([]);
  const [graphType, setGraphType] = useState<"bar" | "line" | "pie">("bar");
  const [graphFields, setGraphFields] = useState<AxisDesignerField[]>([]);
  const [pivotFields, setPivotFields] = useState<AxisDesignerField[]>([]);
  const [mapResPartner, setMapResPartner] = useState("");
  const [mapFields, setMapFields] = useState<DesignerField[]>([]);
  const [activityFields, setActivityFields] = useState<DesignerField[]>([]);
  const [windowActionId, setWindowActionId] = useState<number | null>(null);
  const [ganttDateStart, setGanttDateStart] = useState("");
  const [ganttDateStop, setGanttDateStop] = useState("");
  const [ganttGroupBy, setGanttGroupBy] = useState("");
  const [ganttColor, setGanttColor] = useState("");
  const [ganttProgress, setGanttProgress] = useState("");
  const [ganttFields, setGanttFields] = useState<DesignerField[]>([]);
  const [cohortDateStart, setCohortDateStart] = useState("");
  const [cohortDateStop, setCohortDateStop] = useState("");
  const [cohortInterval, setCohortInterval] = useState<
    "day" | "week" | "month" | "year" | ""
  >("week");
  const [cohortMode, setCohortMode] = useState<"retention" | "churn" | "">("retention");
  const [cohortTimeline, setCohortTimeline] = useState<"forward" | "backward" | "">("");
  const [cohortMeasure, setCohortMeasure] = useState("");
  const [formCanCreate, setFormCanCreate] = useState(true);
  const [formCanEdit, setFormCanEdit] = useState(true);
  const [formCanDelete, setFormCanDelete] = useState(true);
  const [formCanDuplicate, setFormCanDuplicate] = useState(true);
  const [listCanCreate, setListCanCreate] = useState(true);
  const [listCanEdit, setListCanEdit] = useState(true);
  const [listCanDelete, setListCanDelete] = useState(true);
  const [listMultiEdit, setListMultiEdit] = useState(false);
  const [listDefaultOrder, setListDefaultOrder] = useState("");
  const [kanbanCanCreate, setKanbanCanCreate] = useState(true);
  const [kanbanQuickCreate, setKanbanQuickCreate] = useState(true);
  const [viewSample, setViewSample] = useState(false);
  const [widgetAdvanced, setWidgetAdvanced] = useState(false);
  const [inspectorWidgets, setInspectorWidgets] = useState<WidgetOption[]>([]);
  const [nicheWidgets, setNicheWidgets] = useState<NicheWidgetEntry[]>([]);
  const [colorPalette, setColorPalette] = useState<Array<{ index: number; name: string }>>(
    [],
  );
  const [previewTheme, setPreviewTheme] = useState<PreviewTheme | null>(null);
  const [viewSample, setViewSample] = useState(false);
  const [widgetAdvanced, setWidgetAdvanced] = useState(false);
  const [inspectorWidgets, setInspectorWidgets] = useState<WidgetOption[]>([]);
  const [nicheWidgets, setNicheWidgets] = useState<NicheWidgetEntry[]>([]);
  const [colorPalette, setColorPalette] = useState<Array<{ index: number; name: string }>>(
    [],
  );
  const [previewTheme, setPreviewTheme] = useState<PreviewTheme | null>(null);
  const [searchGroupByFilters, setSearchGroupByFilters] = useState<SearchGroupByFilter[]>(
    [],
  );
  const [arch, setArch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [canvasFlashId, setCanvasFlashId] = useState<string | null>(null);
  const [toolbarFlash, setToolbarFlash] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragField, setDragField] = useState<string | null>(null);
  const [lastSnapshotId, setLastSnapshotId] = useState<string | null>(null);
  const [loadedViewId, setLoadedViewId] = useState<number | null>(null);
  const [snapshots, setSnapshots] = useState<SnapshotRow[]>([]);
  const [selected, setSelected] = useState<SelectedField | null>(null);
  const [showIframePreview, setShowIframePreview] = useState(false);
  const [previewKey, setPreviewKey] = useState(0);
  const [saveStrategy, setSaveStrategy] = useState<"inherit" | "overwrite">("inherit");
  const [confirmOverwriteOpen, setConfirmOverwriteOpen] = useState(false);
  const [searchFilters, setSearchFilters] = useState<SearchFilter[]>([]);
  const [headerButtons, setHeaderButtons] = useState<DesignerButton[]>([]);
  const [buttonBox, setButtonBox] = useState<DesignerButton[]>([]);
  const [bindMode, setBindMode] = useState<BindDialogMode>("closed");
  const [bindPlacement, setBindPlacement] = useState<ButtonPlacement>("header");
  const [bindLabel, setBindLabel] = useState("Mark Available");
  const [bindFieldName, setBindFieldName] = useState("x_status");
  const [bindValue, setBindValue] = useState("available");
  const [bindTargetModel, setBindTargetModel] = useState("x_lib_loan");
  const [bindRelationField, setBindRelationField] = useState("x_book_id");
  const [bindIcon, setBindIcon] = useState("fa-list");
  const [bindableActions, setBindableActions] = useState<
    Array<{
      id: number;
      name: string;
      action_type: "ir.actions.server" | "ir.actions.act_window";
      model: string;
      detail: string | null;
    }>
  >([]);
  const [selectedActionId, setSelectedActionId] = useState<number | "">("");
  const [listDecorationDanger, setListDecorationDanger] = useState("");
  const [listDecorationInfo, setListDecorationInfo] = useState("");
  const [listDecorationMuted, setListDecorationMuted] = useState("");
  const [statusbarField, setStatusbarField] = useState("");
  const [statusbarVisible, setStatusbarVisible] = useState("");
  const [newFieldName, setNewFieldName] = useState("");
  const [newFieldLabel, setNewFieldLabel] = useState("");
  const [newFieldType, setNewFieldType] = useState("char");
  const [injectStrategy, setInjectStrategy] = useState<"inherit" | "mutate">(
    "inherit",
  );
  const [confirmMutateOpen, setConfirmMutateOpen] = useState(false);
  const [confirmPhrase, setConfirmPhrase] = useState("");
  const [bindActivityTypeId, setBindActivityTypeId] = useState<number | "">("");
  const [bindActivitySummary, setBindActivitySummary] = useState("Follow up");
  const [bindActivityNote, setBindActivityNote] = useState("");
  const [activityTypes, setActivityTypes] = useState<ActivityTypeRow[]>([]);
  const [bindMailTemplateId, setBindMailTemplateId] = useState<number | "">("");
  const [bindMailMethod, setBindMailMethod] = useState<"email" | "comment" | "note">("email");
  const [bindMailSubject, setBindMailSubject] = useState("");
  const [bindMailBody, setBindMailBody] = useState("");
  const [bindMailEmailTo, setBindMailEmailTo] = useState("");
  const [mailTemplates, setMailTemplates] = useState<MailTemplateRow[]>([]);
  const [bindCreateCountField, setBindCreateCountField] = useState(false);
  const [bindOne2manyField, setBindOne2manyField] = useState("");
  const [bindCountFieldName, setBindCountFieldName] = useState("");
  const [bindSmartConfirmPhrase, setBindSmartConfirmPhrase] = useState("");
  const [xpathExpr, setXpathExpr] = useState("//sheet");
  const [xpathPosition, setXpathPosition] = useState<
    "inside" | "after" | "before" | "replace" | "attributes"
  >("inside");
  const [xpathBody, setXpathBody] = useState('<field name="x_name"/>');
  const [xpathIssues, setXpathIssues] = useState<string[]>([]);
  const [xpathArchPreview, setXpathArchPreview] = useState("");
  const [archOverride, setArchOverride] = useState<string | null>(null);
  const [editingFilterId, setEditingFilterId] = useState<string | null>(null);

  const refreshSnapshots = useCallback(async () => {
    try {
      const snaps = await api.listSnapshots(connectionId);
      setSnapshots(snaps.filter((s) => s.resource_type === "view"));
    } catch {
      setSnapshots([]);
    }
  }, [connectionId]);

  useEffect(() => {
    api
      .getConnection(connectionId)
      .then(setConnection)
      .catch((err: Error) => setError(err.message));
    refreshSnapshots().catch(() => undefined);
    api
      .getPreviewTheme(connectionId)
      .then(setPreviewTheme)
      .catch(() => setPreviewTheme(null));
  }, [connectionId, refreshSnapshots]);

  useEffect(() => {
    if (!connectionId) return;
    api
      .listNicheWidgets(connectionId, viewType)
      .then((res) => {
        setNicheWidgets(res.widgets);
        setColorPalette(res.color_palette);
      })
      .catch(() => {
        setNicheWidgets([]);
        setColorPalette([]);
      });
  }, [connectionId, viewType]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const fromQuery = new URLSearchParams(window.location.search).get("model");
    if (fromQuery) setModel(fromQuery);
  }, []);

  useEffect(() => {
    if (!canvasFlashId || typeof document === "undefined") return;
    const el = document.querySelector(`[data-canvas-id="${canvasFlashId}"]`);
    el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    const t = window.setTimeout(() => setCanvasFlashId(null), 2200);
    return () => window.clearTimeout(t);
  }, [canvasFlashId]);

  useEffect(() => {
    if (!toolbarFlash) return;
    const t = window.setTimeout(() => setToolbarFlash(null), 1800);
    return () => window.clearTimeout(t);
  }, [toolbarFlash]);

  function announceAction(message: string, flashId?: string | null, toolbarKey?: string) {
    setNotice(message);
    if (flashId) setCanvasFlashId(flashId);
    if (toolbarKey) setToolbarFlash(toolbarKey);
  }

  useEffect(() => {
    if (!connectionId || !model.trim()) {
      setWindowActionId(null);
      return;
    }
    let cancelled = false;
    api
      .listWindowActions(connectionId, { model: model.trim(), standaloneOnly: true })
      .then((rows) => {
        if (cancelled) return;
        setWindowActionId(pickStandaloneWindowAction(rows, viewType));
      })
      .catch(() => {
        if (!cancelled) setWindowActionId(null);
      });
    return () => {
      cancelled = true;
    };
  }, [connectionId, model, viewType]);

  const liveOdooUrl =
    connection?.url && model
      ? odooViewUrl(connection.url, model, viewType, windowActionId)
      : null;
  const proxyPreviewUrl = model
    ? sameOriginPreviewUrl(connectionId, model, viewType, API_BASE)
    : null;

  function applyFieldNamesToCanvas(names: string[], rows: FieldRow[]) {
    const nodes: DesignerField[] = names.map((name) => {
      const meta = rows.find((f) => f.name === name);
      return {
        kind: "field" as const,
        id: uid("f"),
        name,
        string: meta?.field_description,
      };
    });
    if (nodes.length === 0) {
      const nameField = rows.find((f) => f.name === "x_name") ?? rows[0];
      if (nameField) {
        nodes.push({
          kind: "field",
          id: uid("f"),
          name: nameField.name,
          string: nameField.field_description,
        });
      }
    }
    setFormChildren([
      { kind: "group", id: uid("g"), string: "Main", children: [...nodes] },
    ]);
    setListColumns(nodes.map((n) => ({ ...n, id: uid("f") })));
    setSearchFields(nodes.map((n) => ({ ...n, id: uid("f") })));
    setKanbanFields(nodes.map((n) => ({ ...n, id: uid("f") })));
    setCalendarFields(nodes.map((n) => ({ ...n, id: uid("f") })));
    setMapFields(nodes.map((n) => ({ ...n, id: uid("f") })));
    setActivityFields(nodes.map((n) => ({ ...n, id: uid("f") })));
    setGanttFields(nodes.map((n) => ({ ...n, id: uid("f") })));
    const { dateStart, dateStop } = pickTemporalDefaults(rows);
    setCalendarDateStart(dateStart);
    setCalendarDateStop(dateStop);
    setCalendarColor("");
    setCalendarMode("");
    setGanttDateStart(dateStart);
    setGanttDateStop(dateStop);
    setGanttGroupBy("");
    setGanttColor("");
    setGanttProgress("");
    setCohortDateStart(dateStart || "create_date");
    setCohortDateStop(dateStop);
    setCohortInterval("week");
    setCohortMode("retention");
    setCohortTimeline("");
    setCohortMeasure(
      rows.find(
        (f) =>
          f.ttype === "integer" || f.ttype === "float" || f.ttype === "monetary",
      )?.name ?? "",
    );
    setMapResPartner(
      rows.find((f) => f.ttype === "many2one" && f.relation === "res.partner")?.name ??
        "",
    );
    setFormCanCreate(true);
    setFormCanEdit(true);
    setFormCanDelete(true);
    setFormCanDuplicate(true);
    setListCanCreate(true);
    setListCanEdit(true);
    setListCanDelete(true);
    setListMultiEdit(false);
    setListDefaultOrder("");
    setKanbanCanCreate(true);
    setKanbanQuickCreate(true);
    setSearchFilters([]);
    setSearchGroupByFilters([]);
    const rowField =
      rows.find((f) => f.ttype === "many2one" || f.ttype === "selection" || f.ttype === "char")
        ?.name ?? nodes[0]?.name;
    const measureField =
      rows.find(
        (f) =>
          f.ttype === "integer" ||
          f.ttype === "float" ||
          f.ttype === "monetary",
      )?.name ?? nodes[0]?.name;
    const seededGraph: AxisDesignerField[] = [];
    if (rowField) seededGraph.push({ id: uid("af"), name: rowField, type: "row" });
    if (measureField)
      seededGraph.push({ id: uid("af"), name: measureField, type: "measure" });
    setGraphFields(seededGraph);
    setGraphType("bar");
    const seededPivot: AxisDesignerField[] = [];
    if (rowField) seededPivot.push({ id: uid("af"), name: rowField, type: "row" });
    if (measureField)
      seededPivot.push({ id: uid("af"), name: measureField, type: "measure" });
    setPivotFields(seededPivot);
    setSelected(null);
  }

  async function loadModelFields(target: string) {
    setError(null);
    setLoadedViewId(null);
    setLastSnapshotId(null);
    try {
      const rows = await api.listFields(connectionId, target);
      setFields(rows);
      setFieldsModel(target);
      applyFieldNamesToCanvas([], rows);
      setTitle(target);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load fields");
    }
  }

  async function ensureFieldsForModel(target: string) {
    const trimmed = target.trim();
    if (!trimmed || !connectionId) return;
    if (fieldsModel === trimmed && fields.length > 0) return;
    try {
      const rows = await api.listFields(connectionId, trimmed);
      setFields(rows);
      setFieldsModel(trimmed);
      const { dateStart, dateStop } = pickTemporalDefaults(rows);
      setCalendarDateStart((prev) =>
        prev && rows.some((f) => f.name === prev) ? prev : dateStart,
      );
      setCalendarDateStop((prev) =>
        prev && rows.some((f) => f.name === prev) ? prev : dateStop,
      );
      setGanttDateStart((prev) =>
        prev && rows.some((f) => f.name === prev) ? prev : dateStart,
      );
      setGanttDateStop((prev) =>
        prev && rows.some((f) => f.name === prev) ? prev : dateStop,
      );
      setCohortDateStart((prev) =>
        prev && rows.some((f) => f.name === prev) ? prev : dateStart || "create_date",
      );
      setCohortDateStop((prev) =>
        prev && rows.some((f) => f.name === prev) ? prev : dateStop,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load fields");
    }
  }

  async function loadExistingView() {
    if (!model) {
      setError("Enter a model first");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const [rows, views] = await Promise.all([
        api.listFields(connectionId, model),
        api.listViews(connectionId, model),
      ]);
      setFields(rows);
      setFieldsModel(model);
      const match =
        views.find((v) => v.type === viewType) ||
        (viewType === "list" ? views.find((v) => v.type === "tree") : undefined);
      if (!match) {
        setNotice(`No existing ${viewType} view — canvas seeded from fields.`);
        applyFieldNamesToCanvas([], rows);
        setLoadedViewId(null);
        return;
      }
      const full = match.arch ? match : await api.getView(connectionId, match.id);
      setLoadedViewId(full.id);
      setArch(full.arch ?? "");
      if (full.arch) {
        try {
          const parsed = await api.parseViewArch(connectionId, viewType, full.arch);
          const spec = parsed.spec as Record<string, unknown>;
          if (viewType === "form" && Array.isArray(spec.children)) {
            const children = (spec.children as Array<Record<string, unknown>>).map((child) => {
              if (child.kind === "notebook") {
                const pages = (child.pages as Array<Record<string, unknown>> | undefined) ?? [];
                return {
                  kind: "notebook" as const,
                  id: uid("n"),
                  pages: pages.map((p) => ({
                    id: uid("p"),
                    string: String(p.string || "Page"),
                    children: ((p.children as Array<Record<string, unknown>> | undefined) ?? []).map((n) =>
                      n.kind === "button"
                        ? mapParsedButton(n)
                        : { kind: "field" as const, id: uid("f"), name: String(n.name || ""), string: n.string ? String(n.string) : undefined, required: n.required as boolean | undefined, readonly: n.readonly as boolean | undefined, invisible: n.invisible ? String(n.invisible) : undefined, widget: n.widget ? String(n.widget) : undefined },
                    ),
                  })),
                };
              }
              const kids = (child.children as Array<Record<string, unknown>> | undefined) ?? [];
              return {
                kind: "group" as const,
                id: uid("g"),
                string: child.string ? String(child.string) : undefined,
                children: kids.map((n) =>
                  n.kind === "button"
                    ? mapParsedButton(n)
                    : { kind: "field" as const, id: uid("f"), name: String(n.name || ""), string: n.string ? String(n.string) : undefined, required: n.required as boolean | undefined, readonly: n.readonly as boolean | undefined, invisible: n.invisible ? String(n.invisible) : undefined, widget: n.widget ? String(n.widget) : undefined },
                ),
              };
            });
            setFormChildren(children.length ? children : [{ kind: "group", id: uid("g"), string: "Main", children: [] }]);
            setHeaderButtons(
              ((spec.header_buttons as Array<Record<string, unknown>> | undefined) ?? []).map(mapParsedButton),
            );
            setButtonBox(
              ((spec.button_box as Array<Record<string, unknown>> | undefined) ?? []).map(mapParsedButton),
            );
            setStatusbarField(
              typeof spec.statusbar_field === "string" ? spec.statusbar_field : "",
            );
            setStatusbarVisible(
              typeof spec.statusbar_visible === "string" ? spec.statusbar_visible : "",
            );
            const fc = asSpecBool(spec.create);
            const fe = asSpecBool(spec.edit);
            const fd = asSpecBool(spec.delete);
            const fdu = asSpecBool(spec.duplicate);
            setFormCanCreate(fc ?? true);
            setFormCanEdit(fe ?? true);
            setFormCanDelete(fd ?? true);
            setFormCanDuplicate(fdu ?? true);
            if (typeof spec.string === "string") setTitle(spec.string);
          } else if (viewType === "list" && Array.isArray(spec.columns)) {
            setListColumns((spec.columns as Array<Record<string, unknown>>).map((c) => ({
              kind: "field" as const, id: uid("f"), name: String(c.name || ""), string: c.string ? String(c.string) : undefined,
              required: c.required as boolean | undefined, readonly: c.readonly as boolean | undefined, widget: c.widget ? String(c.widget) : undefined,
            })));
            setListDecorationDanger(typeof spec.decoration_danger === "string" ? spec.decoration_danger : "");
            setListDecorationInfo(typeof spec.decoration_info === "string" ? spec.decoration_info : "");
            setListDecorationMuted(typeof spec.decoration_muted === "string" ? spec.decoration_muted : "");
            const lc = asSpecBool(spec.create);
            const le = asSpecBool(spec.edit);
            const ld = asSpecBool(spec.delete);
            const lm = asSpecBool(spec.multi_edit);
            setListCanCreate(lc ?? true);
            setListCanEdit(le ?? true);
            setListCanDelete(ld ?? true);
            setListMultiEdit(lm ?? false);
            setListDefaultOrder(
              typeof spec.default_order === "string" ? spec.default_order : "",
            );
            setViewSample(asSpecBool(spec.sample) ?? false);
            if (typeof spec.string === "string") setTitle(spec.string);
          } else if (viewType === "search") {
            setSearchFields(((spec.fields as Array<Record<string, unknown>> | undefined) ?? []).map((c) => ({
              kind: "field" as const, id: uid("f"), name: String(c.name || ""), string: c.string ? String(c.string) : undefined,
            })));
            setSearchFilters(((spec.filters as Array<Record<string, unknown>> | undefined) ?? []).map((f) => ({
              id: uid("sf"), name: String(f.name || "filter"), string: String(f.string || f.name || "Filter"), domain: f.domain ? String(f.domain) : undefined,
            })));
            setSearchGroupByFilters(
              ((spec.group_by_filters as Array<Record<string, unknown>> | undefined) ?? []).map(
                (f) => ({
                  id: uid("sg"),
                  name: String(f.name || "groupby"),
                  string: String(f.string || f.name || "Group By"),
                  context: f.context
                    ? String(f.context)
                    : "{'group_by': 'field'}",
                }),
              ),
            );
            if (typeof spec.string === "string") setTitle(spec.string);
          } else if (viewType === "kanban") {
            const names = (spec.records_fields as string[] | undefined) ?? [];
            setKanbanFields(names.map((name) => ({ kind: "field" as const, id: uid("f"), name, string: rows.find((r) => r.name === name)?.field_description })));
            setKanbanGroupBy(typeof spec.default_group_by === "string" ? spec.default_group_by : "");
            const kc = asSpecBool(spec.create);
            const kq = asSpecBool(spec.quick_create);
            setKanbanCanCreate(kc ?? true);
            setKanbanQuickCreate(kq ?? true);
            setViewSample(asSpecBool(spec.sample) ?? false);
            if (typeof spec.string === "string") setTitle(spec.string);
          } else if (viewType === "calendar") {
            setCalendarDateStart(typeof spec.date_start === "string" ? spec.date_start : "");
            setCalendarDateStop(typeof spec.date_stop === "string" ? spec.date_stop : "");
            setCalendarColor(typeof spec.color === "string" ? spec.color : "");
            setCalendarMode(typeof spec.mode === "string" ? spec.mode : "");
            setCalendarFields(
              ((spec.fields as Array<Record<string, unknown>> | undefined) ?? []).map((c) => ({
                kind: "field" as const,
                id: uid("f"),
                name: String(c.name || ""),
                string: c.string ? String(c.string) : undefined,
              })),
            );
            if (typeof spec.string === "string") setTitle(spec.string);
          } else if (viewType === "graph") {
            const gt = spec.type;
            setGraphType(gt === "line" || gt === "pie" ? gt : "bar");
            setGraphFields(
              ((spec.fields as Array<Record<string, unknown>> | undefined) ?? []).map((c) => ({
                id: uid("af"),
                name: String(c.name || ""),
                type:
                  c.type === "row" || c.type === "col" || c.type === "measure"
                    ? c.type
                    : undefined,
                interval: c.interval ? String(c.interval) : undefined,
                string: c.string ? String(c.string) : undefined,
              })),
            );
            setViewSample(asSpecBool(spec.sample) ?? false);
            if (typeof spec.string === "string") setTitle(spec.string);
          } else if (viewType === "pivot") {
            setPivotFields(
              ((spec.fields as Array<Record<string, unknown>> | undefined) ?? []).map((c) => ({
                id: uid("af"),
                name: String(c.name || ""),
                type:
                  c.type === "row" || c.type === "col" || c.type === "measure"
                    ? c.type
                    : undefined,
                interval: c.interval ? String(c.interval) : undefined,
                string: c.string ? String(c.string) : undefined,
              })),
            );
            setViewSample(asSpecBool(spec.sample) ?? false);
            if (typeof spec.string === "string") setTitle(spec.string);
          } else if (viewType === "map") {
            setMapResPartner(
              typeof spec.res_partner === "string" ? spec.res_partner : "",
            );
            setMapFields(
              ((spec.fields as Array<Record<string, unknown>> | undefined) ?? []).map((c) => ({
                kind: "field" as const,
                id: uid("f"),
                name: String(c.name || ""),
                string: c.string ? String(c.string) : undefined,
              })),
            );
            if (typeof spec.string === "string") setTitle(spec.string);
          } else if (viewType === "activity") {
            setActivityFields(
              ((spec.fields as Array<Record<string, unknown>> | undefined) ?? []).map((c) => ({
                kind: "field" as const,
                id: uid("f"),
                name: String(c.name || ""),
                string: c.string ? String(c.string) : undefined,
              })),
            );
            if (typeof spec.string === "string") setTitle(spec.string);
          } else if (viewType === "gantt") {
            setGanttDateStart(typeof spec.date_start === "string" ? spec.date_start : "");
            setGanttDateStop(typeof spec.date_stop === "string" ? spec.date_stop : "");
            setGanttGroupBy(
              typeof spec.default_group_by === "string" ? spec.default_group_by : "",
            );
            setGanttColor(typeof spec.color === "string" ? spec.color : "");
            setGanttProgress(typeof spec.progress === "string" ? spec.progress : "");
            setGanttFields(
              ((spec.fields as Array<Record<string, unknown>> | undefined) ?? []).map((c) => ({
                kind: "field" as const,
                id: uid("f"),
                name: String(c.name || ""),
                string: c.string ? String(c.string) : undefined,
              })),
            );
            if (typeof spec.string === "string") setTitle(spec.string);
          } else if (viewType === "cohort") {
            setCohortDateStart(typeof spec.date_start === "string" ? spec.date_start : "");
            setCohortDateStop(typeof spec.date_stop === "string" ? spec.date_stop : "");
            const iv = spec.interval;
            setCohortInterval(
              iv === "day" || iv === "week" || iv === "month" || iv === "year" ? iv : "week",
            );
            const cm = spec.mode;
            setCohortMode(cm === "churn" || cm === "retention" ? cm : "retention");
            const tl = spec.timeline;
            setCohortTimeline(tl === "forward" || tl === "backward" ? tl : "");
            setCohortMeasure(typeof spec.measure === "string" ? spec.measure : "");
            if (typeof spec.string === "string") setTitle(spec.string);
          }
          setNotice(`Loaded ${full.type} view #${full.id} with structure (round-trip parse).`);
        } catch {
          const names = (full.arch ?? "").match(/<field\b[^>]*\bname=["']([^"']+)["']/g)?.map((m) => m.replace(/.*name=["']([^"']+)["'].*/, "$1")).filter(Boolean) ?? [];
          const unique: string[] = [];
          for (const n of names) if (!unique.includes(n)) unique.push(n);
          applyFieldNamesToCanvas(unique, rows);
          setTitle(full.name || model);
          setNotice(`Loaded ${full.type} view #${full.id} (flat fallback — ${unique.length} fields).`);
        }
      } else {
        applyFieldNamesToCanvas([], rows);
        setTitle(full.name || model);
      }
      setSelected(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Load view failed");
    } finally {
      setBusy(false);
    }
  }

  const formSpec = useMemo(
    () => ({
      string: title,
      create: formCanCreate,
      edit: formCanEdit,
      delete: formCanDelete,
      duplicate: formCanDuplicate,
      statusbar_field: statusbarField || null,
      statusbar_visible: statusbarVisible || null,
      header_buttons: headerButtons.map((b) => nodeSpec(b)),
      button_box: buttonBox.map((b) => nodeSpec(b)),
      children: formChildren.map((child) => {
        if (child.kind === "group") {
          return {
            kind: "group",
            string: child.string,
            children: child.children.map((n) => {
              if (n.kind === "button") return nodeSpec(n);
              return fieldSpec({
                ...n,
                string: resolveFieldLabel(n.name, n.string, fields),
              });
            }),
          };
        }
        return {
          kind: "notebook",
          pages: child.pages.map((p) => ({
            string: p.string,
            children: p.children.map((n) => {
              if (n.kind === "button") return nodeSpec(n);
              return fieldSpec({
                ...n,
                string: resolveFieldLabel(n.name, n.string, fields),
              });
            }),
          })),
        };
      }),
    }),
    [
      formChildren,
      fields,
      title,
      headerButtons,
      buttonBox,
      statusbarField,
      statusbarVisible,
      formCanCreate,
      formCanEdit,
      formCanDelete,
      formCanDuplicate,
    ],
  );

  const listSpec = useMemo(
    () => ({
      string: title,
      create: listCanCreate,
      edit: listCanEdit,
      delete: listCanDelete,
      multi_edit: listMultiEdit,
      default_order: listDefaultOrder || null,
      sample: viewSample || null,
      sample: viewSample || null,
      columns: listColumns.map(fieldSpec),
      decoration_danger: listDecorationDanger || null,
      decoration_info: listDecorationInfo || null,
      decoration_muted: listDecorationMuted || null,
    }),
    [
      listColumns,
      listDecorationDanger,
      listDecorationInfo,
      listDecorationMuted,
      listCanCreate,
      listCanEdit,
      listCanDelete,
      listMultiEdit,
      listDefaultOrder,
      viewSample,
      title,
    ],
  );

  const searchSpec = useMemo(
    () => ({
      string: title,
      fields: searchFields.map(fieldSpec),
      filters: searchFilters.map((f) => ({
        kind: "filter" as const,
        name: f.name,
        string: f.string,
        domain: f.domain,
      })),
      group_by_filters: searchGroupByFilters.map((f) => ({
        kind: "filter" as const,
        name: f.name,
        string: f.string,
        context: f.context || undefined,
      })),
    }),
    [searchFields, searchFilters, searchGroupByFilters, title],
  );

  const kanbanSpec = useMemo(
    () => ({
      string: title,
      records_fields: kanbanFields.map((f) => f.name),
      default_group_by: kanbanGroupBy || null,
      create: kanbanCanCreate,
      quick_create: kanbanQuickCreate,
      sample: viewSample || null,
    }),
    [kanbanFields, kanbanGroupBy, kanbanCanCreate, kanbanQuickCreate, viewSample, title],
  );

  const calendarSpec = useMemo(
    () => ({
      string: title,
      date_start: calendarDateStart || "date",
      date_stop: calendarDateStop || null,
      color: calendarColor || null,
      mode: calendarMode || null,
      fields: calendarFields.map((f) => fieldSpec(f)),
    }),
    [calendarColor, calendarDateStart, calendarDateStop, calendarFields, calendarMode, title],
  );

  const dateFieldsForSelect = useMemo(() => sortedDateFields(fields), [fields]);

  const graphSpec = useMemo(
    () => ({
      string: title,
      type: graphType,
      sample: viewSample || null,
      fields: graphFields.map((f) => ({
        kind: "field" as const,
        name: f.name,
        type: f.type,
        interval: f.interval || undefined,
        string: f.string,
      })),
    }),
    [graphFields, graphType, viewSample, title],
  );

  const pivotSpec = useMemo(
    () => ({
      string: title,
      sample: viewSample || null,
      fields: pivotFields.map((f) => ({
        kind: "field" as const,
        name: f.name,
        type: f.type,
        interval: f.interval || undefined,
        string: f.string,
      })),
    }),
    [pivotFields, viewSample, title],
  );

  const mapSpec = useMemo(
    () => ({
      string: title,
      res_partner: mapResPartner || null,
      fields: mapFields.map((f) => fieldSpec(f)),
    }),
    [mapFields, mapResPartner, title],
  );

  const activitySpec = useMemo(
    () => ({
      string: title,
      fields: activityFields.map((f) => fieldSpec(f)),
    }),
    [activityFields, title],
  );

  const ganttSpec = useMemo(
    () => ({
      string: title,
      date_start: ganttDateStart || "date_start",
      date_stop: ganttDateStop || null,
      default_group_by: ganttGroupBy || null,
      color: ganttColor || null,
      progress: ganttProgress || null,
      fields: ganttFields.map((f) => fieldSpec(f)),
    }),
    [
      ganttColor,
      ganttDateStart,
      ganttDateStop,
      ganttFields,
      ganttGroupBy,
      ganttProgress,
      title,
    ],
  );

  const cohortSpec = useMemo(
    () => ({
      string: title,
      date_start: cohortDateStart || "create_date",
      date_stop: cohortDateStop || null,
      interval: cohortInterval || null,
      mode: cohortMode || null,
      timeline: cohortTimeline || null,
      measure: cohortMeasure || null,
    }),
    [
      cohortDateStart,
      cohortDateStop,
      cohortInterval,
      cohortMeasure,
      cohortMode,
      cohortTimeline,
      title,
    ],
  );

  const activeViewSpec = useMemo(() => {
    if (viewType === "form") return formSpec;
    if (viewType === "list") return listSpec;
    if (viewType === "kanban") return kanbanSpec;
    if (viewType === "calendar") return calendarSpec;
    if (viewType === "graph") return graphSpec;
    if (viewType === "pivot") return pivotSpec;
    if (viewType === "map") return mapSpec;
    if (viewType === "activity") return activitySpec;
    if (viewType === "gantt") return ganttSpec;
    if (viewType === "cohort") return cohortSpec;
    return searchSpec;
  }, [
    viewType,
    formSpec,
    listSpec,
    kanbanSpec,
    calendarSpec,
    graphSpec,
    pivotSpec,
    mapSpec,
    activitySpec,
    ganttSpec,
    cohortSpec,
    searchSpec,
  ]);

  const refreshPreview = useCallback(async () => {
    if (!model) return;
    try {
      const res = await api.previewViewArch(connectionId, viewType, activeViewSpec);
      setArch(res.arch);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preview failed");
    }
  }, [connectionId, activeViewSpec, model, viewType]);

  useEffect(() => {
    refreshPreview();
  }, [refreshPreview]);

  function moveKanbanField(fieldId: string, dir: -1 | 1) {
    setKanbanFields((cols) => {
      const idx = cols.findIndex((f) => f.id === fieldId);
      if (idx < 0) return cols;
      const next = idx + dir;
      if (next < 0 || next >= cols.length) return cols;
      const copy = [...cols];
      const [item] = copy.splice(idx, 1);
      copy.splice(next, 0, item);
      return copy;
    });
  }

  function findSelectedField(): DesignerField | null {
    if (!selected) return null;
    if (selected.scope === "list") {
      return listColumns.find((f) => f.id === selected.fieldId) ?? null;
    }
    if (selected.scope === "search") {
      return searchFields.find((f) => f.id === selected.fieldId) ?? null;
    }
    if (selected.scope === "kanban") {
      return kanbanFields.find((f) => f.id === selected.fieldId) ?? null;
    }
    if (selected.scope === "form-group") {
      for (const child of formChildren) {
        if (child.kind === "group" && child.id === selected.groupId) {
          const hit = child.children.find((f) => f.id === selected.fieldId);
          return hit && hit.kind === "field" ? hit : null;
        }
      }
      return null;
    }
    for (const child of formChildren) {
      if (child.kind === "notebook" && child.id === selected.notebookId) {
        const page = child.pages.find((p) => p.id === selected.pageId);
        const hit = page?.children.find((f) => f.id === selected.fieldId);
        return hit && hit.kind === "field" ? hit : null;
      }
    }
    return null;
  }

  function updateSelectedField(patch: Partial<DesignerField>) {
    if (!selected) return;
    if (selected.scope === "list") {
      setListColumns((cols) =>
        cols.map((f) => (f.id === selected.fieldId ? { ...f, ...patch } : f)),
      );
      return;
    }
    if (selected.scope === "search") {
      setSearchFields((cols) =>
        cols.map((f) => (f.id === selected.fieldId ? { ...f, ...patch } : f)),
      );
      return;
    }
    if (selected.scope === "kanban") {
      setKanbanFields((cols) =>
        cols.map((f) => (f.id === selected.fieldId ? { ...f, ...patch } : f)),
      );
      return;
    }
    if (selected.scope === "form-group") {
      setFormChildren((children) =>
        children.map((child) => {
          if (child.kind !== "group" || child.id !== selected.groupId) return child;
          return {
            ...child,
            children: child.children.map((node) => {
              if (node.id !== selected.fieldId || node.kind !== "field") return node;
              return { ...node, ...patch };
            }),
          };
        }),
      );
      return;
    }
    setFormChildren((children) =>
      children.map((child) => {
        if (child.kind !== "notebook" || child.id !== selected.notebookId) return child;
        return {
          ...child,
          pages: child.pages.map((p) => {
            if (p.id !== selected.pageId) return p;
            return {
              ...p,
              children: p.children.map((node) => {
                if (node.id !== selected.fieldId || node.kind !== "field") return node;
                return { ...node, ...patch };
              }),
            };
          }),
        };
      }),
    );
  }

  function addGroup() {
    const id = uid("g");
    setFormChildren((c) => [
      ...c,
      { kind: "group", id, string: `Group ${c.length + 1}`, children: [] },
    ]);
    announceAction(`Added group “Group ${formChildren.length + 1}” on the canvas.`, id, "group");
  }

  function addNotebook() {
    const id = uid("n");
    const pageLabel = "Page 1";
    setFormChildren((c) => [
      ...c,
      {
        kind: "notebook",
        id,
        pages: [{ id: uid("p"), string: pageLabel, children: [] }],
      },
    ]);
    announceAction(
      "Added notebook (tab strip) on the canvas below. Prefer “+ Page” on this notebook for another tab — not another notebook.",
      id,
      "notebook",
    );
  }

  function addPageToNotebook(notebookId: string) {
    const pageId = uid("p");
    let pageName = "Page";
    setFormChildren((children) =>
      children.map((child) => {
        if (child.kind !== "notebook" || child.id !== notebookId) return child;
        const n = child.pages.length + 1;
        pageName = `Page ${n}`;
        return {
          ...child,
          pages: [
            ...child.pages,
            { id: pageId, string: pageName, children: [] },
          ],
        };
      }),
    );
    announceAction(`Added tab “${pageName}” to the notebook.`, pageId, "page");
  }

  function removeFormChild(childId: string) {
    const target = formChildren.find((c) => c.id === childId);
    setFormChildren((children) => children.filter((c) => c.id !== childId));
    setSelected((sel) => {
      if (!sel) return null;
      if (sel.scope === "form-group" && sel.groupId === childId) return null;
      if (sel.scope === "form-page" && sel.notebookId === childId) return null;
      return sel;
    });
    announceAction(
      target?.kind === "notebook" ? "Removed notebook from canvas." : "Removed group from canvas.",
      null,
      "remove",
    );
  }

  function removeNotebookPage(notebookId: string, pageId: string) {
    setFormChildren((children) =>
      children
        .map((child) => {
          if (child.kind !== "notebook" || child.id !== notebookId) return child;
          const pages = child.pages.filter((p) => p.id !== pageId);
          if (pages.length === 0) return null;
          return { ...child, pages };
        })
        .filter((c): c is FormChild => c != null),
    );
    setSelected((sel) =>
      sel?.scope === "form-page" && sel.pageId === pageId ? null : sel,
    );
    announceAction("Removed notebook page (tab).", null, "remove");
  }

  function renameNotebookPage(notebookId: string, pageId: string, string: string) {
    setFormChildren((children) =>
      children.map((child) => {
        if (child.kind !== "notebook" || child.id !== notebookId) return child;
        return {
          ...child,
          pages: child.pages.map((p) =>
            p.id === pageId ? { ...p, string: string || p.string } : p,
          ),
        };
      }),
    );
  }

  function renameGroup(groupId: string, string: string) {
    setFormChildren((children) =>
      children.map((child) =>
        child.kind === "group" && child.id === groupId
          ? { ...child, string: string || child.string }
          : child,
      ),
    );
  }

  function openBindDialog(placement: ButtonPlacement, mode: BindDialogMode = "create_update") {
    setBindPlacement(placement);
    setBindMode(mode);
    setError(null);
    if (mode === "bind_existing" && model) {
      void api
        .listBindableActions(connectionId, model)
        .then((rows) => {
          setBindableActions(rows);
          setSelectedActionId(rows[0]?.id ?? "");
        })
        .catch((err) => setError(err instanceof Error ? err.message : "Failed to list actions"));
    }
    if (mode === "create_activity") {
      void api
        .listActivityTypes(connectionId)
        .then((rows) => {
          setActivityTypes(rows);
          setBindActivityTypeId(rows[0]?.id ?? "");
        })
        .catch((err) => setError(err instanceof Error ? err.message : "Failed to list activity types"));
    }
    if (mode === "create_mail" && model) {
      void api
        .listMailTemplates(connectionId, model)
        .then((rows) => {
          setMailTemplates(rows);
          setBindMailTemplateId(rows[0]?.id ?? "");
        })
        .catch(() => setMailTemplates([]));
    }
  }

  function placeBoundButton(btn: DesignerButton) {
    if (bindPlacement === "header") {
      setHeaderButtons((all) => [...all, btn]);
    } else if (bindPlacement === "button_box") {
      setButtonBox((all) => [
        ...all,
        {
          ...btn,
          class_name: btn.class_name || "oe_stat_button",
          icon: btn.icon || bindIcon || "fa-list",
        },
      ]);
    } else {
      setFormChildren((children) => {
        if (!children.length) {
          return [{ kind: "group", id: uid("g"), string: "Main", children: [btn] }];
        }
        return children.map((child, idx) => {
          if (idx !== 0 || child.kind !== "group") return child;
          return { ...child, children: [...child.children, btn] };
        });
      });
    }
  }

  async function submitBindDialog(opts?: {
    confirm_advanced?: boolean;
    confirm_phrase?: string;
  }) {
    if (!model) {
      setError("Enter a model first");
      return;
    }
    if (bindMode !== "closed" && !bindModeSupported(connection, bindMode)) {
      setError(
        bindModeUnsupportedReason(connection, bindMode) ??
          "Bind mode unavailable on this Odoo version",
      );
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (bindMode === "create_update") {
        const created = await api.createUpdateFieldAction(connectionId, {
          name: bindLabel,
          model,
          field_name: bindFieldName,
          value: bindValue,
          bind_to_model: true,
        });
        placeBoundButton({
          kind: "button",
          id: uid("b"),
          string: bindLabel,
          name: String(created.id),
          type: "action",
          class_name: bindPlacement === "header" ? "btn-primary" : undefined,
        });
        setNotice(`Created server action #${created.id} and bound button (${bindPlacement}). Save the view to apply.`);
      } else if (bindMode === "create_related") {
        const created = await api.createRelatedWindowAction(connectionId, {
          name: bindLabel,
          source_model: model,
          target_model: bindTargetModel,
          relation_field: bindRelationField,
        });
        placeBoundButton({
          kind: "button",
          id: uid("b"),
          string: bindLabel,
          name: String(created.id),
          type: "action",
          class_name: bindPlacement === "button_box" ? "oe_stat_button" : "btn-secondary",
          icon: bindPlacement === "button_box" ? bindIcon : undefined,
        });
        setNotice(`Created window action #${created.id} and bound button (${bindPlacement}). Save the view to apply.`);
      } else if (bindMode === "create_activity") {
        if (bindActivityTypeId === "") {
          setError("Pick an activity type");
          return;
        }
        const created = await api.createNextActivityAction(connectionId, {
          name: bindLabel,
          model,
          activity_type_id: bindActivityTypeId,
          summary: bindActivitySummary || "Follow up",
          note: bindActivityNote || null,
          user_type: "generic",
          user_field_name: undefined,
          bind_to_model: true,
        });
        placeBoundButton({
          kind: "button",
          id: uid("b"),
          string: bindLabel,
          name: String(created.id),
          type: "action",
          class_name: bindPlacement === "header" ? "btn-primary" : undefined,
        });
        setNotice(`Created next-activity action #${created.id} (${bindPlacement}). Save the view to apply.`);
      } else if (bindMode === "create_mail") {
        const created = await api.createMailPostAction(connectionId, {
          name: bindLabel,
          model,
          template_id: bindMailTemplateId === "" ? null : bindMailTemplateId,
          mail_post_method: bindMailMethod,
          subject: bindMailSubject || null,
          body_html: bindMailBody || null,
          email_to: bindMailEmailTo || null,
          bind_to_model: true,
        });
        placeBoundButton({
          kind: "button",
          id: uid("b"),
          string: bindLabel,
          name: String(created.id),
          type: "action",
          class_name: bindPlacement === "header" ? "btn-primary" : undefined,
        });
        setNotice(`Created mail-post action #${created.id} (${bindPlacement}). Save the view to apply.`);
      } else if (bindMode === "create_smart") {
        if (bindCreateCountField) {
          const phrase = (opts?.confirm_phrase || bindSmartConfirmPhrase).trim();
          if (phrase !== CONFIRM_PHRASE) {
            setError(`Create count field requires confirm phrase: ${CONFIRM_PHRASE}`);
            return;
          }
          if (!bindOne2manyField.trim()) {
            setError("one2many field on source model is required for count field");
            return;
          }
        }
        const bundle = await api.createSmartButtonBundle(connectionId, {
          name: bindLabel,
          source_model: model,
          target_model: bindTargetModel,
          relation_field: bindRelationField,
          one2many_field: bindOne2manyField.trim() || null,
          count_field_name: bindCountFieldName.trim() || null,
          create_count_field: bindCreateCountField,
          icon: bindIcon || "fa-list",
          confirm_advanced: bindCreateCountField
            ? opts?.confirm_advanced ?? true
            : false,
          confirm_phrase: bindCreateCountField
            ? opts?.confirm_phrase || bindSmartConfirmPhrase || CONFIRM_PHRASE
            : null,
        });
        const spec = bundle.button_spec;
        placeBoundButton({
          kind: "button",
          id: uid("b"),
          string: String(spec.string || bindLabel),
          name: String(spec.name || bundle.window_action.id),
          type: "action",
          class_name: String(spec.class || "oe_stat_button"),
          icon: String(spec.icon || bindIcon || "fa-list"),
          count_field: bundle.count_field || undefined,
        });
        setNotice(
          `Smart button bundle: window #${bundle.window_action.id}` +
            (bundle.count_field ? ` · count ${bundle.count_field}` : "") +
            `. Save the view to apply.`,
        );
      } else if (bindMode === "bind_existing") {
        if (selectedActionId === "") {
          setError("Pick an existing action");
          return;
        }
        placeBoundButton({
          kind: "button",
          id: uid("b"),
          string: bindLabel,
          name: String(selectedActionId),
          type: "action",
          class_name:
            bindPlacement === "button_box"
              ? "oe_stat_button"
              : bindPlacement === "header"
                ? "btn-primary"
                : undefined,
          icon: bindPlacement === "button_box" ? bindIcon : undefined,
        });
        setNotice(`Bound button to action #${selectedActionId}. Save the view to apply.`);
      }
      setBindMode("closed");
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setError(`${err.warning} Type “${err.confirm_phrase}” and retry.`);
        setBindSmartConfirmPhrase(err.confirm_phrase || CONFIRM_PHRASE);
      } else {
        setError(err instanceof Error ? err.message : "Failed to bind action");
      }
    } finally {
      setBusy(false);
    }
  }

  function addButtonToFirstGroup() {
    openBindDialog("inline", "create_update");
  }

  function dropOnGroup(groupId: string) {
    if (!dragField) return;
    const meta = fields.find((f) => f.name === dragField);
    const node: DesignerField = {
      kind: "field",
      id: uid("f"),
      name: dragField,
      string: meta?.field_description,
    };
    setFormChildren((children) =>
      children.map((child) => {
        if (child.kind === "group" && child.id === groupId) {
          if (child.children.some((n) => n.kind === "field" && n.name === dragField)) {
            return child;
          }
          return { ...child, children: [...child.children, node] };
        }
        return child;
      }),
    );
    announceAction(
      `Added ${meta?.field_description || dragField} to group.`,
      groupId,
      "drop",
    );
    setDragField(null);
  }

  function dropOnPage(notebookId: string, pageId: string) {
    if (!dragField) return;
    dropFieldOnPage(notebookId, pageId, dragField);
    setDragField(null);
  }

  function dropFieldOnPage(notebookId: string, pageId: string, fieldName: string) {
    const meta = fields.find((f) => f.name === fieldName);
    const node: DesignerField = {
      kind: "field",
      id: uid("f"),
      name: fieldName,
      string: meta?.field_description,
    };
    setFormChildren((children) =>
      children.map((child) => {
        if (child.kind !== "notebook" || child.id !== notebookId) return child;
        return {
          ...child,
          pages: child.pages.map((p) => {
            if (p.id !== pageId) return p;
            if (p.children.some((n) => n.kind === "field" && n.name === fieldName)) {
              return p;
            }
            return { ...p, children: [...p.children, node] };
          }),
        };
      }),
    );
    announceAction(
      `Added ${meta?.field_description || fieldName} to notebook tab.`,
      pageId,
      "drop",
    );
  }

  function addListColumn(fieldName: string) {
    if (listColumns.some((c) => c.name === fieldName)) return;
    const meta = fields.find((f) => f.name === fieldName);
    setListColumns((cols) => [
      ...cols,
      {
        kind: "field",
        id: uid("f"),
        name: fieldName,
        string: meta?.field_description,
      },
    ]);
  }

  function addSearchField(fieldName: string) {
    if (searchFields.some((c) => c.name === fieldName)) return;
    const meta = fields.find((f) => f.name === fieldName);
    setSearchFields((cols) => [
      ...cols,
      {
        kind: "field",
        id: uid("f"),
        name: fieldName,
        string: meta?.field_description,
      },
    ]);
  }

  function addKanbanField(fieldName: string) {
    if (kanbanFields.some((c) => c.name === fieldName)) return;
    const meta = fields.find((f) => f.name === fieldName);
    setKanbanFields((cols) => [
      ...cols,
      {
        kind: "field",
        id: uid("f"),
        name: fieldName,
        string: meta?.field_description,
      },
    ]);
  }

  async function addNicheWidget(entry: NicheWidgetEntry) {
    if (!model) {
      setError("Select a model first");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      let fieldName: string | undefined;
      const support = entry.supporting_field;
      let fieldRows = fields;

      const existing = fields.find(
        (f) =>
          entry.recommended_ttypes.includes(f.ttype) &&
          (!support || f.name === support.name),
      );
      if (existing) {
        fieldName = existing.name;
      } else if (support) {
        if (!fields.some((f) => f.name === support.name)) {
          await api.createField(connectionId, {
            model,
            name: support.name,
            field_description: support.string || support.name,
            ttype: support.ttype,
            inject_into_views: false,
            inject_strategy: "inherit",
            confirm_advanced: true,
            confirm_phrase: CONFIRM_PHRASE,
            ...(support.relation ? { relation: support.relation } : {}),
            ...(support.ttype === "selection"
              ? {
                  selection: [
                    { value: "normal", label: "Normal" },
                    { value: "done", label: "Done" },
                    { value: "blocked", label: "Blocked" },
                  ],
                }
              : {}),
          });
          fieldRows = await api.listFields(connectionId, model);
          setFields(fieldRows);
          setFieldsModel(model);
        }
        fieldName = support.name;
      } else {
        const match = fields.find((f) => entry.recommended_ttypes.includes(f.ttype));
        if (!match) {
          setNotice(
            `Add a ${entry.recommended_ttypes.join("/")} field first for ${entry.label}`,
          );
          return;
        }
        fieldName = match.name;
      }

      const meta = fieldRows.find((f) => f.name === fieldName);
      const node: DesignerField = {
        kind: "field",
        id: uid("f"),
        name: fieldName,
        string: meta?.field_description,
        widget: entry.id,
      };

      if (viewType === "kanban") {
        if (kanbanFields.some((c) => c.name === fieldName && c.widget === entry.id)) return;
        setKanbanFields((cols) => [...cols, node]);
        setSelected({ scope: "kanban", fieldId: node.id });
      } else if (viewType === "list") {
        if (listColumns.some((c) => c.name === fieldName && c.widget === entry.id)) return;
        setListColumns((cols) => [...cols, node]);
        setSelected({ scope: "list", fieldId: node.id });
      } else if (viewType === "form") {
        const firstGroup = formChildren.find((c) => c.kind === "group");
        if (!firstGroup) {
          setNotice("Add a form group before niche widgets");
          return;
        }
        setFormChildren((children) =>
          children.map((child) =>
            child.kind === "group" && child.id === firstGroup.id
              ? { ...child, children: [...child.children, node] }
              : child,
          ),
        );
        setSelected({ scope: "form-group", groupId: firstGroup.id, fieldId: node.id });
      } else {
        setNotice(`${entry.label} is available on form, list, and kanban views`);
        return;
      }
      announceAction(`Added ${entry.label} (${entry.id})`, node.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add niche widget");
    } finally {
      setBusy(false);
    }
  }

  function removeFormField(
    container: "group" | "page",
    containerId: string,
    fieldId: string,
    notebookId?: string,
  ) {
    setFormChildren((children) =>
      children.map((child) => {
        if (container === "group" && child.kind === "group" && child.id === containerId) {
          return { ...child, children: child.children.filter((f) => f.id !== fieldId) };
        }
        if (
          container === "page" &&
          child.kind === "notebook" &&
          child.id === notebookId
        ) {
          return {
            ...child,
            pages: child.pages.map((p) =>
              p.id === containerId
                ? { ...p, children: p.children.filter((f) => f.id !== fieldId) }
                : p,
            ),
          };
        }
        return child;
      }),
    );
    setSelected((sel) => (sel?.fieldId === fieldId ? null : sel));
  }

  async function createNewFieldWithInject(opts?: {
    confirm_advanced?: boolean;
    confirm_phrase?: string;
  }) {
    if (!model || !newFieldName.startsWith("x_")) return;
    const strategyCap = injectStrategyCapabilityId(injectStrategy);
    if (!connectionSupports(connection, strategyCap)) {
      setError(
        connectionUnsupportedReason(connection, strategyCap) ??
          "Inject strategy unavailable on this Odoo version",
      );
      return;
    }
    if (injectStrategy === "mutate" && !opts?.confirm_advanced) {
      setConfirmMutateOpen(true);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.createField(connectionId, {
        model,
        name: newFieldName,
        field_description: newFieldLabel || newFieldName,
        ttype: newFieldType,
        inject_into_views: true,
        inject_strategy: injectStrategy,
        ...(injectStrategy === "mutate"
          ? {
              confirm_advanced: true,
              confirm_phrase:
                opts?.confirm_phrase || confirmPhrase || CONFIRM_PHRASE,
            }
          : {
              confirm_advanced: true,
              confirm_phrase: confirmPhrase || CONFIRM_PHRASE,
            }),
        ...(newFieldType === "many2one" ? { relation: "res.partner" } : {}),
        ...(newFieldType === "selection"
          ? {
              selection: [
                { value: "a", label: "A" },
                { value: "b", label: "B" },
              ],
            }
          : {}),
      });
      setNotice(
        `Created ${newFieldName}` +
          (injectStrategy === "mutate" ? " (mutate inject)" : " (inherit inject)"),
      );
      setNewFieldName("");
      setConfirmMutateOpen(false);
      await loadModelFields(model);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmMutateOpen(true);
        setError(`${err.warning} Type “${err.confirm_phrase}” and retry.`);
        setConfirmPhrase(err.confirm_phrase || CONFIRM_PHRASE);
      } else {
        setError(err instanceof Error ? err.message : "Create field failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function onSave(opts?: {
    arch?: string;
    strategy?: "inherit" | "overwrite";
    confirm_phrase?: string;
  }) {
    if (!model) {
      setError("Load a model first");
      return;
    }
    const strategy = opts?.strategy ?? saveStrategy;
    // Stock models default to inherit — overwrite only via confirmed Power path
    if (!model.startsWith("x_") && strategy === "overwrite" && !opts?.confirm_phrase) {
      setConfirmOverwriteOpen(true);
      return;
    }
    if (strategy === "overwrite" && !opts?.confirm_phrase && model.startsWith("x_")) {
      setConfirmOverwriteOpen(true);
      return;
    }
    const useArch = opts?.arch ?? archOverride;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const saved = await api.saveView(connectionId, {
        model,
        view_type: viewType,
        name:
          strategy === "inherit"
            ? `${model}.designer.${viewType}`
            : `${model}.${viewType}`,
        view_id: strategy === "overwrite" ? (loadedViewId ?? undefined) : undefined,
        ...(useArch ? { arch: useArch } : { spec: activeViewSpec }),
        create_if_missing: true,
        strategy,
        ...(strategy === "overwrite"
          ? {
              confirm_advanced: true,
              confirm_phrase: opts?.confirm_phrase || CONFIRM_PHRASE,
            }
          : {}),
      });
      setLoadedViewId(saved.id);
      setConfirmOverwriteOpen(false);
      if (saved.snapshot_id) {
        setLastSnapshotId(saved.snapshot_id);
        setNotice(
          `Saved ${viewType} view #${saved.id}. Snapshot ${saved.snapshot_id.slice(0, 8)}… ready to undo.`,
        );
      } else {
        setNotice(`Saved new ${viewType} view #${saved.id} for ${model}`);
      }
      setArch(saved.arch ?? arch);
      setArchOverride(null);
      setPreviewKey((k) => k + 1);
      await refreshSnapshots();
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmOverwriteOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Save failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function runXpathPreview() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.xpathPreview(connectionId, {
        expr: xpathExpr,
        position: xpathPosition,
        body_xml: xpathBody,
      });
      setXpathArchPreview(res.arch);
      setXpathIssues(res.issues ?? []);
      if (res.issues?.length) {
        setNotice(`XPath preview built with ${res.issues.length} validation issue(s).`);
      } else {
        setNotice("XPath preview OK — no validation issues.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "XPath preview failed");
      setXpathArchPreview("");
      setXpathIssues([]);
    } finally {
      setBusy(false);
    }
  }

  async function onUndo() {
    if (!lastSnapshotId) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.rollbackSnapshot(connectionId, lastSnapshotId);
      setNotice(`Rolled back to snapshot — restored view #${res.id}`);
      setLastSnapshotId(null);
      await loadExistingView();
      await refreshSnapshots();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Undo failed");
    } finally {
      setBusy(false);
    }
  }

  async function onRollback(snapshotId: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await api.rollbackSnapshot(connectionId, snapshotId);
      setNotice(`Restored ${res.restored} #${res.id}`);
      if (snapshotId === lastSnapshotId) setLastSnapshotId(null);
      await loadExistingView();
      await refreshSnapshots();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rollback failed");
    } finally {
      setBusy(false);
    }
  }

  const selectedField = findSelectedField();

  useEffect(() => {
    if (!selectedField) {
      setInspectorWidgets([]);
      return;
    }
    const row = fields.find((f) => f.name === selectedField.name);
    const ttype = row?.ttype ?? "char";
    setInspectorWidgets(fallbackWidgetsForTtype(ttype));
    api
      .listBuilderWidgets(connectionId, ttype)
      .then((rows) => {
        if (rows.length > 0) setInspectorWidgets(rows);
      })
      .catch(() => {
        /* fallback */
      });
  }, [connectionId, fields, selectedField?.name]);

  return (
    <main className="odoo-shell min-h-screen px-6 py-10 text-[#f4eef2]">
      <div className="mx-auto max-w-7xl">
        <div className="flex flex-wrap gap-4 text-sm">
          <Link href={`/connections/${connectionId}`} className="text-[#c9a9c0] hover:underline">
            ← Metadata
          </Link>
          <Link
            href={`/connections/${connectionId}/builder`}
            className="text-[#8f7a88] hover:underline"
          >
            Builder
          </Link>
          <Link
            href={
              model
                ? `/connections/${connectionId}/automations?model=${encodeURIComponent(model)}`
                : `/connections/${connectionId}/automations`
            }
            className="text-[#8f7a88] hover:underline"
          >
            Automations
          </Link>
          <Link
            href={`/connections/${connectionId}/reminders`}
            className="text-[#8f7a88] hover:underline"
          >
            Reminders
          </Link>
        </div>
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl text-[#faf6f9]">
          View designer
        </h1>
        <p className="mt-1 text-sm text-[#8f7a88]">
          {connection?.name ?? connectionId} · drag fields onto the canvas ·
          saves real <code className="text-[#c9a9c0]">ir.ui.view</code> arch
        </p>
        <p className="mt-2 text-sm text-[#a8909e]">
          Removing a field from the view does not delete the database column.
        </p>
        <VersionAwarenessBanner capabilities={connection?.capabilities} />
        <CapabilityProbePanel
          capabilities={connection?.capabilities}
          defaultOpen={false}
          className="mt-2"
          refreshing={probing}
          onRefresh={() => {
            void (async () => {
              setProbing(true);
              setError(null);
              try {
                const result = await api.probeConnection(connectionId);
                setConnection((prev) =>
                  prev
                    ? {
                        ...prev,
                        server_version: result.server_version,
                        capabilities: result.capabilities,
                      }
                    : prev,
                );
              } catch (err) {
                setError(err instanceof Error ? err.message : "Probe failed");
              } finally {
                setProbing(false);
              }
            })();
          }}
        />
        <div className="mt-4 border border-[#3d2a38] bg-[#0f1a16]/80 px-4 py-3 text-xs text-[#d4c4ce]">
          <p className="font-semibold text-[#c9a9c0]">Production defaults</p>
          <ul className="mt-1 list-disc space-y-1 pl-4">
            <li>
              Save strategy defaults to <strong>Inherit</strong> (extension view) — safe for
              installed modules.
            </li>
            <li>
              <strong>Overwrite</strong> requires confirm and snapshots the primary view first.
            </li>
            <li>
              Buttons bind to real <code>ir.actions.server</code> /{" "}
              <code>ir.actions.act_window</code> (type=action). Python object methods need Option A.
            </li>
            <li>
              Prefer <strong>Open in Odoo</strong> for truth; iframe preview is best-effort via
              authenticated proxy.
            </li>
            <li>
              Create field requires the confirm phrase and injects via inherit xpath.
            </li>
          </ul>
        </div>

        <div className="mt-6 flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="text-[#a8909e]">Model</span>
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              onBlur={() => {
                if (model.trim()) void ensureFieldsForModel(model);
              }}
              className="mt-1 block w-64 border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
              placeholder="x_ticket"
            />
          </label>
          <button
            type="button"
            onClick={() => model && loadModelFields(model)}
            className="h-10 border border-[#c9a9c0] px-4 text-sm text-[#c9a9c0]"
          >
            Load fields
          </button>
          <button
            type="button"
            disabled={busy || !model}
            onClick={loadExistingView}
            className="h-10 border border-[#3d2a38] px-4 text-sm text-[#d4c4ce] disabled:opacity-60"
          >
            Load existing view
          </button>
          <label className="text-sm">
            <span className="text-[#a8909e]">View type</span>
            <select
              value={viewType}
              onChange={(e) => {
                const next = e.target.value as ViewType;
                setViewType(next);
                setSelected(null);
                if (
                  model.trim() &&
                  (next === "calendar" ||
                    next === "gantt" ||
                    next === "cohort" ||
                    next === "activity" ||
                    next === "map")
                ) {
                  void ensureFieldsForModel(model);
                }
              }}
              className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
            >
              <option value="form">form</option>
              <option value="list">
                list
                {!connectionSupports(connection, "list_as_list_type")
                  ? " (stored as tree on this Odoo)"
                  : ""}
              </option>
              <option value="search">search</option>
              <option value="kanban">kanban</option>
              <option value="calendar" disabled={!mutationAllowed(connection)}>
                calendar
                {!mutationAllowed(connection) ? " (probe connection)" : ""}
              </option>
              <option value="graph" disabled={!mutationAllowed(connection)}>
                graph
                {!mutationAllowed(connection) ? " (probe connection)" : ""}
              </option>
              <option value="pivot" disabled={!mutationAllowed(connection)}>
                pivot
                {!mutationAllowed(connection) ? " (probe connection)" : ""}
              </option>
              <option value="map" disabled={!mutationAllowed(connection)}>
                map
                {!mutationAllowed(connection) ? " (probe connection)" : ""}
              </option>
              <option value="activity" disabled={!mutationAllowed(connection)}>
                activity
                {!mutationAllowed(connection) ? " (probe connection)" : ""}
              </option>
              <option value="gantt" disabled={!mutationAllowed(connection)}>
                gantt
                {!mutationAllowed(connection) ? " (probe connection)" : ""}
              </option>
              <option value="cohort" disabled={!mutationAllowed(connection)}>
                cohort
                {!mutationAllowed(connection) ? " (probe connection)" : ""}
              </option>
            </select>
            {!mutationAllowed(connection) && (
              <p className="mt-1 text-xs text-[#c9a227]">
                {mutationBlockedReason(connection) ??
                  "Reporting views need a probed connection."}
              </p>
            )}
          </label>
          {viewType === "kanban" && (
            <label className="text-sm">
              <span className="text-[#a8909e]">Group by</span>
              <select
                value={kanbanGroupBy}
                onChange={(e) => setKanbanGroupBy(e.target.value)}
                className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
              >
                <option value="">(none)</option>
                {fields.map((f) => (
                  <option key={f.id} value={f.name}>
                    {f.name} · {f.ttype}
                  </option>
                ))}
              </select>
            </label>
          )}
          {viewType === "calendar" && (
            <>
              <label className="text-sm">
                <span className="text-[#a8909e]">date_start</span>
                <select
                  value={calendarDateStart}
                  onChange={(e) => setCalendarDateStart(e.target.value)}
                  className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                >
                  <option value="">(required)</option>
                  {dateFieldsForSelect.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name} · {f.ttype}
                      {f.field_description ? ` — ${f.field_description}` : ""}
                    </option>
                  ))}
                </select>
                {fieldsModel && fieldsModel !== model.trim() && (
                  <p className="mt-1 text-xs text-[#c9a227]">
                    Fields loaded for {fieldsModel || "(none)"} — click Load fields for{" "}
                    {model || "this model"}.
                  </p>
                )}
                {!dateFieldsForSelect.length && (
                  <p className="mt-1 text-xs text-[#c9a227]">
                    No date/datetime fields on loaded model. Set model to x_lib_loan and click
                    Load fields.
                  </p>
                )}
              </label>
              <label className="text-sm">
                <span className="text-[#a8909e]">date_stop</span>
                <select
                  value={calendarDateStop}
                  onChange={(e) => setCalendarDateStop(e.target.value)}
                  className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                >
                  <option value="">(optional)</option>
                  {dateFieldsForSelect.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name} · {f.ttype}
                      {f.field_description ? ` — ${f.field_description}` : ""}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-[#a8909e]">color</span>
                <select
                  value={calendarColor}
                  onChange={(e) => setCalendarColor(e.target.value)}
                  className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                >
                  <option value="">(optional)</option>
                  {fields.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-[#a8909e]">mode</span>
                <select
                  value={calendarMode}
                  onChange={(e) => setCalendarMode(e.target.value)}
                  className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2 text-sm"
                >
                  <option value="">(default)</option>
                  <option value="day">day</option>
                  <option value="week">week</option>
                  <option value="month">month</option>
                </select>
              </label>
            </>
          )}
          {viewType === "graph" && (
            <>
            <label className="text-sm">
              <span className="text-[#a8909e]">Graph type</span>
              <select
                value={graphType}
                onChange={(e) =>
                  setGraphType(e.target.value as "bar" | "line" | "pie")
                }
                className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2 text-sm"
              >
                <option value="bar">bar</option>
                <option value="line">line</option>
                <option value="pie">pie</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={viewSample}
                onChange={(e) => setViewSample(e.target.checked)}
                data-testid="designer-view-sample"
              />
              sample data
            </label>
            </>
          )}
          {viewType === "pivot" && (
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={viewSample}
                onChange={(e) => setViewSample(e.target.checked)}
                data-testid="designer-view-sample"
              />
              sample data
            </label>
          )}
          {viewType === "map" && (
            <label className="text-sm">
              <span className="text-[#a8909e]">res_partner</span>
              <select
                value={mapResPartner}
                onChange={(e) => setMapResPartner(e.target.value)}
                className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
              >
                <option value="">(required — partner m2o)</option>
                {fields
                  .filter((f) => f.ttype === "many2one")
                  .map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name}
                      {f.relation ? ` · ${f.relation}` : " · many2one"}
                      {f.relation === "res.partner" ? " ✓" : ""}
                    </option>
                  ))}
              </select>
            </label>
          )}
          {viewType === "gantt" && (
            <>
              <label className="text-sm">
                <span className="text-[#a8909e]">date_start</span>
                <select
                  value={ganttDateStart}
                  onChange={(e) => setGanttDateStart(e.target.value)}
                  className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                >
                  <option value="">(required)</option>
                  {dateFieldsForSelect.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name} · {f.ttype}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-[#a8909e]">date_stop</span>
                <select
                  value={ganttDateStop}
                  onChange={(e) => setGanttDateStop(e.target.value)}
                  className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                >
                  <option value="">(optional)</option>
                  {dateFieldsForSelect.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-[#a8909e]">default_group_by</span>
                <select
                  value={ganttGroupBy}
                  onChange={(e) => setGanttGroupBy(e.target.value)}
                  className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                >
                  <option value="">(optional)</option>
                  {fields.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-[#a8909e]">color</span>
                <select
                  value={ganttColor}
                  onChange={(e) => setGanttColor(e.target.value)}
                  className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                >
                  <option value="">(optional)</option>
                  {fields.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-[#a8909e]">progress</span>
                <select
                  value={ganttProgress}
                  onChange={(e) => setGanttProgress(e.target.value)}
                  className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                >
                  <option value="">(optional)</option>
                  {fields.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name} · {f.ttype}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}
          {viewType === "cohort" && (
            <>
              <label className="text-sm">
                <span className="text-[#a8909e]">date_start</span>
                <select
                  value={cohortDateStart}
                  onChange={(e) => setCohortDateStart(e.target.value)}
                  className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                >
                  <option value="">(required)</option>
                  {dateFieldsForSelect.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name} · {f.ttype}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-[#a8909e]">date_stop</span>
                <select
                  value={cohortDateStop}
                  onChange={(e) => setCohortDateStop(e.target.value)}
                  className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                >
                  <option value="">(optional)</option>
                  {dateFieldsForSelect.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-[#a8909e]">interval</span>
                <select
                  value={cohortInterval}
                  onChange={(e) =>
                    setCohortInterval(
                      e.target.value as "day" | "week" | "month" | "year" | "",
                    )
                  }
                  className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2 text-sm"
                >
                  <option value="day">day</option>
                  <option value="week">week</option>
                  <option value="month">month</option>
                  <option value="year">year</option>
                </select>
              </label>
              <label className="text-sm">
                <span className="text-[#a8909e]">mode</span>
                <select
                  value={cohortMode}
                  onChange={(e) =>
                    setCohortMode(e.target.value as "retention" | "churn" | "")
                  }
                  className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2 text-sm"
                >
                  <option value="retention">retention</option>
                  <option value="churn">churn</option>
                </select>
              </label>
              <label className="text-sm">
                <span className="text-[#a8909e]">timeline</span>
                <select
                  value={cohortTimeline}
                  onChange={(e) =>
                    setCohortTimeline(e.target.value as "forward" | "backward" | "")
                  }
                  className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2 text-sm"
                >
                  <option value="">(default)</option>
                  <option value="forward">forward</option>
                  <option value="backward">backward</option>
                </select>
              </label>
              <label className="text-sm">
                <span className="text-[#a8909e]">measure</span>
                <select
                  value={cohortMeasure}
                  onChange={(e) => setCohortMeasure(e.target.value)}
                  className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                >
                  <option value="">(optional)</option>
                  {fields.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name} · {f.ttype}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}
          <label className="text-sm">
            <span className="text-[#a8909e]">Title</span>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-1 block w-48 border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
            />
          </label>
          <label className="text-sm">
            <span className="text-[#a8909e]">Save strategy</span>
            <select
              value={saveStrategy}
              onChange={(e) => setSaveStrategy(e.target.value as "inherit" | "overwrite")}
              className="mt-1 block w-40 border border-[#3d2a38] bg-[#0c090b] px-2 py-2 text-sm"
            >
              <option value="inherit">Inherit (safe)</option>
              <option value="overwrite">Overwrite primary</option>
            </select>
          </label>
          <button
            type="button"
            disabled={busy || !model}
            onClick={() => void onSave()}
            className="h-10 bg-[#714B67] px-5 text-sm font-semibold text-white disabled:opacity-60"
          >
            {busy ? "Saving…" : archOverride ? "Save arch override" : "Save to Odoo"}
          </button>
          <button
            type="button"
            disabled={busy || !model}
            onClick={async () => {
              setBusy(true); setError(null);
              try {
                const out = await api.polishForm(connectionId, model, title);
                setNotice(out.applied ? `Polished form for ${model}` : `Polish skipped: ${JSON.stringify(out.detail)}`);
                await loadExistingView();
              } catch (err) {
                setError(err instanceof Error ? err.message : "Polish failed");
              } finally { setBusy(false); }
            }}
            className="h-10 border border-[#c9a9c0] px-4 text-sm text-[#c9a9c0] disabled:opacity-40"
          >
            Polish form layout
          </button>
          <button
            type="button"
            disabled={busy || !lastSnapshotId}
            onClick={onUndo}
            className="h-10 border border-[#f0a8a0] px-4 text-sm text-[#f0a8a0] disabled:opacity-40"
          >
            Undo last save
          </button>
          <a
            href={liveOdooUrl ?? "#"}
            target="_blank"
            rel="noopener noreferrer"
            aria-disabled={!liveOdooUrl}
            onClick={(e) => {
              if (!liveOdooUrl) e.preventDefault();
            }}
            className={`inline-flex h-10 items-center border border-[#c9a9c0] px-4 text-sm text-[#c9a9c0] ${
              !liveOdooUrl ? "pointer-events-none opacity-40" : ""
            }`}
          >
            Open in Odoo
          </a>
          <button
            type="button"
            disabled={!liveOdooUrl}
            onClick={() => setShowIframePreview((v) => !v)}
            className="h-10 border border-[#3d2a38] px-4 text-sm text-[#d4c4ce] disabled:opacity-40"
          >
            {showIframePreview ? "Hide preview" : "Toggle preview"}
          </button>
          <button
            type="button"
            disabled={!proxyPreviewUrl}
            onClick={() => {
              setShowIframePreview(true);
              setPreviewKey((k) => k + 1);
              setNotice("Preview refreshed. Open in Odoo remains authoritative.");
            }}
            className="h-10 border border-[#3d2a38] px-4 text-sm text-[#d4c4ce] disabled:opacity-40"
          >
            Refresh preview
          </button>
        </div>
        <p className="mt-2 text-xs text-[#8f7a88]">
          Preview uses a same-origin proxy (strips X-Frame-Options).{" "}
          <strong className="text-[#c9a9c0]">Open in Odoo is authoritative</strong> — the iframe
          is best-effort. Save defaults to <strong>inherit</strong> extension views.
          {archOverride ? " Arch override active — Save will POST raw inherit arch." : ""}
        </p>
        {error && (
          <p
            role="alert"
            className="mt-4 border border-[#7a3030] bg-[#2a1212] px-3 py-2 text-sm text-[#f0a8a0]"
          >
            {error}
          </p>
        )}
        {notice && (
          <p
            role="status"
            className="mt-4 animate-pulse border border-[#5a3d54] bg-[#1a1018] px-3 py-2 text-sm font-medium text-[#e8d4e0]"
          >
            {notice}
          </p>
        )}

        {viewType === "form" && model && (
          <div className="mt-6 grid gap-4 lg:grid-cols-[200px_1fr_240px]">
            <div>
              <FieldPalette
                fields={fields.map((f) => ({
                  name: f.name,
                  ttype: f.ttype,
                  label: f.field_description,
                }))}
              />
              <NicheWidgetPalette
                widgets={nicheWidgets}
                colorPalette={colorPalette}
                onPick={(w) => void addNicheWidget(w)}
              />
            </div>
            <div>
              <h2 className="mb-2 text-sm font-semibold text-[var(--odoo-primary-light)]">
                Odoo-style canvas
              </h2>
              <PreviewThemeScope previewVars={previewTheme?.preview_vars}>
              <FormCanvas
              title={title || model}
              statusbar={statusbarField || null}
              headerButtons={headerButtons.map((b) => b.string)}
              smartButtons={buttonBox.map((b) => ({ id: b.id, string: b.string }))}
              flashId={canvasFlashId}
              groups={formChildren
                .filter((c): c is DesignerGroup => c.kind === "group")
                .map((g) => ({
                  id: g.id,
                  string: g.string,
                  fields: g.children
                    .filter((n): n is DesignerField => n.kind === "field")
                    .map((f) => ({
                      id: f.id,
                      name: f.name,
                      string: resolveFieldLabel(f.name, f.string, fields),
                    })),
                }))}
              notebooks={formChildren
                .filter((c): c is DesignerNotebook => c.kind === "notebook")
                .map((nb) => ({
                  id: nb.id,
                  pages: nb.pages.map((p) => ({
                    id: p.id,
                    string: p.string,
                    fields: p.children
                      .filter((n): n is DesignerField => n.kind === "field")
                      .map((f) => ({
                        id: f.id,
                        name: f.name,
                        string: resolveFieldLabel(f.name, f.string, fields),
                      })),
                  })),
                }))}
              selectedFieldId={
                selected?.scope === "form-group" ? selected.fieldId : null
              }
              onSelectField={(fieldId) => {
                for (const child of formChildren) {
                  if (child.kind !== "group") continue;
                  if (child.children.some((n) => n.kind === "field" && n.id === fieldId)) {
                    setSelected({
                      scope: "form-group",
                      groupId: child.id,
                      fieldId,
                    });
                    break;
                  }
                }
              }}
              onMoveField={(fieldId, dir) => {
                setFormChildren((children) =>
                  children.map((child) => {
                    if (child.kind !== "group") return child;
                    const idx = child.children.findIndex(
                      (n) => n.kind === "field" && n.id === fieldId,
                    );
                    if (idx < 0) return child;
                    const next = idx + dir;
                    if (next < 0 || next >= child.children.length) return child;
                    const copy = [...child.children];
                    const [item] = copy.splice(idx, 1);
                    copy.splice(next, 0, item);
                    return { ...child, children: copy };
                  }),
                );
              }}
              onDropFieldName={(groupId, fieldName) => {
                const meta = fields.find((f) => f.name === fieldName);
                const node: DesignerField = {
                  kind: "field",
                  id: uid("f"),
                  name: fieldName,
                  string: meta?.field_description,
                };
                setFormChildren((children) =>
                  children.map((child) => {
                    if (child.kind === "group" && child.id === groupId) {
                      if (child.children.some((n) => n.kind === "field" && n.name === fieldName)) {
                        return child;
                      }
                      return { ...child, children: [...child.children, node] };
                    }
                    return child;
                  }),
                );
                announceAction(
                  `Added ${meta?.field_description || fieldName} to group.`,
                  groupId,
                  "drop",
                );
              }}
              onDropFieldOnPage={(notebookId, pageId, fieldName) => {
                dropFieldOnPage(notebookId, pageId, fieldName);
              }}
            />
              </PreviewThemeScope>
            </div>
            <PropsInspector title="Field properties">
              {selectedField ? (
                <div className="space-y-3 text-sm text-[#1a1a1a]">
                  <p className="font-mono text-[var(--odoo-primary)]">{selectedField.name}</p>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={!!selectedField.required}
                      onChange={(e) => updateSelectedField({ required: e.target.checked })}
                    />
                    <span>Required</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={!!selectedField.readonly}
                      onChange={(e) => updateSelectedField({ readonly: e.target.checked })}
                    />
                    <span>Readonly</span>
                  </label>
                  <label className="block text-xs">
                    Widget
                    <input
                      value={selectedField.widget ?? ""}
                      onChange={(e) =>
                        updateSelectedField({ widget: e.target.value || undefined })
                      }
                      className="mt-1 w-full border border-[var(--odoo-border)] px-2 py-1 font-mono text-xs"
                    />
                  </label>
                </div>
              ) : (
                <p className="text-xs text-[var(--odoo-muted)]">
                  Select a field on the canvas, or drag from the palette.
                </p>
              )}
            </PropsInspector>
          </div>
        )}

        {viewType === "kanban" && model && (
          <div className="mt-6 grid gap-4 lg:grid-cols-[200px_1fr_240px]">
            <div>
              <FieldPalette
                fields={fields.map((f) => ({
                  name: f.name,
                  ttype: f.ttype,
                  label: f.field_description,
                }))}
              />
              <NicheWidgetPalette
                widgets={nicheWidgets}
                colorPalette={colorPalette}
                onPick={(w) => void addNicheWidget(w)}
              />
            </div>
            <div>
              <h2 className="mb-2 text-sm font-semibold text-[var(--odoo-primary-light)]">
                Kanban card preview
              </h2>
              <PreviewThemeScope previewVars={previewTheme?.preview_vars}>
              <KanbanCardPreview
                title={title || model}
                groupBy={kanbanGroupBy || null}
                fields={kanbanFields.map((f) => ({
                  id: f.id,
                  name: f.name,
                  string: f.string,
                }))}
                selectedFieldId={
                  selected?.scope === "kanban" ? selected.fieldId : null
                }
                onSelectField={(fieldId) =>
                  setSelected({ scope: "kanban", fieldId })
                }
                onMoveField={moveKanbanField}
                onRemoveField={(fieldId) => {
                  setKanbanFields((cols) => cols.filter((c) => c.id !== fieldId));
                  setSelected((sel) =>
                    sel?.scope === "kanban" && sel.fieldId === fieldId ? null : sel,
                  );
                }}
                onDropFieldName={(fieldName) => addKanbanField(fieldName)}
              />
              </PreviewThemeScope>
            </div>
            <PropsInspector title="Card field">
              {selectedField && selected?.scope === "kanban" ? (
                <div className="space-y-3 text-sm text-[#1a1a1a]">
                  <p className="font-mono text-[var(--odoo-primary)]">
                    {selectedField.name}
                  </p>
                  <p className="text-xs text-[var(--odoo-muted)]">
                    {selectedField.string || "No label from field metadata"}
                  </p>
                  <p className="text-[11px] text-[var(--odoo-muted)]">
                    Card label show/hide (nolabel) is not in our kanban arch helpers
                    yet — values render in order only.
                  </p>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="text-xs text-[var(--odoo-primary)]"
                      onClick={() => moveKanbanField(selectedField.id, -1)}
                    >
                      Move up
                    </button>
                    <button
                      type="button"
                      className="text-xs text-[var(--odoo-primary)]"
                      onClick={() => moveKanbanField(selectedField.id, 1)}
                    >
                      Move down
                    </button>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-[var(--odoo-muted)]">
                  Select a card field, or drop from the palette. Set group-by above.
                </p>
              )}
            </PropsInspector>
          </div>
        )}

        {(viewType === "calendar" ||
          viewType === "graph" ||
          viewType === "pivot" ||
          viewType === "map" ||
          viewType === "activity" ||
          viewType === "gantt" ||
          viewType === "cohort") &&
          model && (
          <div className="mt-6 border border-[#3d2a38] bg-[#0b1210] p-4">
            <h2 className="mb-2 text-sm font-semibold text-[#c9a9c0]">
              {viewType} view fields
            </h2>
            <p className="mb-3 text-xs text-[#8f7a88]">
              Arch preview updates from these fields. Drag from the palette into
              form/list is unchanged — use the buttons below for reporting axes.
            </p>
            {viewType === "map" && (
              <p className="mb-3 border border-[#c9a227]/40 bg-[#1a1810] px-3 py-2 text-xs text-[#e8d09f]">
                Map views need a <code className="text-[#c9a9c0]">res.partner</code>{" "}
                many2one (<code className="text-[#c9a9c0]">res_partner</code> attr).
                Without a partner field, Odoo will not render the map.
              </p>
            )}
            {viewType === "gantt" && (
              <p className="mb-3 border border-[#c9a227]/40 bg-[#1a1810] px-3 py-2 text-xs text-[#e8d09f]">
                Gantt arch is Community-safe metadata, but the client often needs{" "}
                <code className="text-[#c9a9c0]">web_gantt</code> /{" "}
                <code className="text-[#c9a9c0]">project</code> (Enterprise or installed
                modules). We do not claim EE live — save may succeed while Open in Odoo
                shows nothing without the module.
              </p>
            )}
            {viewType === "cohort" && (
              <p className="mb-3 border border-[#c9a227]/40 bg-[#1a1810] px-3 py-2 text-xs text-[#e8d09f]">
                Cohort views are module/version gated. Arch can be saved via public RPC;
                the UI may be unavailable without the cohort client module. Not an EE
                live claim.
              </p>
            )}
            {viewType === "calendar" && (
              <ul className="space-y-1 font-mono text-sm text-[#d4c4ce]">
                {calendarFields.map((f) => (
                  <li key={f.id} className="flex items-center justify-between gap-2">
                    <span>{f.name}</span>
                    <button
                      type="button"
                      className="text-xs text-[#f0a8a0]"
                      onClick={() =>
                        setCalendarFields((cols) => cols.filter((c) => c.id !== f.id))
                      }
                    >
                      Remove
                    </button>
                  </li>
                ))}
                {!calendarFields.length && (
                  <li className="text-[#8f7a88]">No display fields yet</li>
                )}
              </ul>
            )}
            {(viewType === "map" || viewType === "activity" || viewType === "gantt") && (
              <ul className="space-y-1 font-mono text-sm text-[#d4c4ce]">
                {(viewType === "map"
                  ? mapFields
                  : viewType === "activity"
                    ? activityFields
                    : ganttFields
                ).map((f) => (
                  <li key={f.id} className="flex items-center justify-between gap-2">
                    <span>{f.name}</span>
                    <button
                      type="button"
                      className="text-xs text-[#f0a8a0]"
                      onClick={() => {
                        if (viewType === "map") {
                          setMapFields((cols) => cols.filter((c) => c.id !== f.id));
                        } else if (viewType === "activity") {
                          setActivityFields((cols) => cols.filter((c) => c.id !== f.id));
                        } else {
                          setGanttFields((cols) => cols.filter((c) => c.id !== f.id));
                        }
                      }}
                    >
                      Remove
                    </button>
                  </li>
                ))}
                {(viewType === "map"
                  ? mapFields
                  : viewType === "activity"
                    ? activityFields
                    : ganttFields
                ).length === 0 && (
                  <li className="text-[#8f7a88]">No display fields yet</li>
                )}
              </ul>
            )}
            {viewType === "cohort" && (
              <p className="text-xs text-[#8f7a88]">
                Cohort uses date_start / measure from the toolbar — no field list required.
              </p>
            )}
            {viewType === "graph" && (
              <ul className="space-y-2 font-mono text-sm text-[#d4c4ce]">
                {graphFields.map((f) => (
                  <li key={f.id} className="flex flex-wrap items-center gap-2">
                    <span className="min-w-[8rem]">{f.name}</span>
                    <select
                      value={f.type ?? ""}
                      onChange={(e) => {
                        const next = e.target.value as "" | "row" | "measure";
                        setGraphFields((cols) =>
                          cols.map((c) =>
                            c.id === f.id
                              ? {
                                  ...c,
                                  type: next === "" ? undefined : next,
                                }
                              : c,
                          ),
                        );
                      }}
                      className="border border-[#3d2a38] bg-[#0c090b] px-2 py-1 text-xs"
                    >
                      <option value="">(role)</option>
                      <option value="row">row</option>
                      <option value="measure">measure</option>
                    </select>
                    <button
                      type="button"
                      className="text-xs text-[#f0a8a0]"
                      onClick={() =>
                        setGraphFields((cols) => cols.filter((c) => c.id !== f.id))
                      }
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {viewType === "pivot" && (
              <ul className="space-y-2 font-mono text-sm text-[#d4c4ce]">
                {pivotFields.map((f) => (
                  <li key={f.id} className="flex flex-wrap items-center gap-2">
                    <span className="min-w-[8rem]">{f.name}</span>
                    <select
                      value={f.type ?? ""}
                      onChange={(e) => {
                        const next = e.target.value as "" | "row" | "col" | "measure";
                        setPivotFields((cols) =>
                          cols.map((c) =>
                            c.id === f.id
                              ? {
                                  ...c,
                                  type: next === "" ? undefined : next,
                                }
                              : c,
                          ),
                        );
                      }}
                      className="border border-[#3d2a38] bg-[#0c090b] px-2 py-1 text-xs"
                    >
                      <option value="">(role)</option>
                      <option value="row">row</option>
                      <option value="col">col</option>
                      <option value="measure">measure</option>
                    </select>
                    {f.type === "col" && (
                      <input
                        value={f.interval ?? ""}
                        placeholder="interval"
                        onChange={(e) =>
                          setPivotFields((cols) =>
                            cols.map((c) =>
                              c.id === f.id
                                ? { ...c, interval: e.target.value || undefined }
                                : c,
                            ),
                          )
                        }
                        className="w-24 border border-[#3d2a38] bg-[#0c090b] px-2 py-1 text-xs"
                      />
                    )}
                    <button
                      type="button"
                      className="text-xs text-[#f0a8a0]"
                      onClick={() =>
                        setPivotFields((cols) => cols.filter((c) => c.id !== f.id))
                      }
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {viewType !== "cohort" && (
            <div className="mt-3 space-y-2">
              <p className="text-[11px] text-[#8f7a88]">
                Click <span className="font-mono text-[#c9a9c0]">+ field</span> to include an
                existing model field. Custom <span className="font-mono">x_*</span> fields are
                listed first (do not use Create field — that creates new columns).
              </p>
              <div className="flex max-h-40 flex-wrap gap-2 overflow-y-auto">
              {[...fields]
                .sort((a, b) => {
                  const rank = (n: string) =>
                    n.startsWith("x_") ? 0 : n.startsWith("activity_") ? 2 : 1;
                  const d = rank(a.name) - rank(b.name);
                  return d !== 0 ? d : a.name.localeCompare(b.name);
                })
                .map((f) => (
                <button
                  key={f.id}
                  type="button"
                  className="border border-[#3d2a38] px-2 py-0.5 font-mono text-[11px] text-[#c9a9c0]"
                  onClick={() => {
                    const nextField: DesignerField = {
                      kind: "field",
                      id: uid("f"),
                      name: f.name,
                      string: f.field_description,
                    };
                    if (viewType === "calendar") {
                      setCalendarFields((cols) =>
                        cols.some((c) => c.name === f.name) ? cols : [...cols, nextField],
                      );
                    } else if (viewType === "map") {
                      setMapFields((cols) =>
                        cols.some((c) => c.name === f.name) ? cols : [...cols, nextField],
                      );
                    } else if (viewType === "activity") {
                      setActivityFields((cols) =>
                        cols.some((c) => c.name === f.name) ? cols : [...cols, nextField],
                      );
                    } else if (viewType === "gantt") {
                      setGanttFields((cols) =>
                        cols.some((c) => c.name === f.name) ? cols : [...cols, nextField],
                      );
                    } else if (viewType === "graph") {
                      setGraphFields((cols) =>
                        cols.some((c) => c.name === f.name)
                          ? cols
                          : [
                              ...cols,
                              {
                                id: uid("af"),
                                name: f.name,
                                type: "measure",
                                string: f.field_description,
                              },
                            ],
                      );
                    } else {
                      setPivotFields((cols) =>
                        cols.some((c) => c.name === f.name)
                          ? cols
                          : [
                              ...cols,
                              {
                                id: uid("af"),
                                name: f.name,
                                type: "row",
                                string: f.field_description,
                              },
                            ],
                      );
                    }
                  }}
                >
                  + {f.name}
                </button>
              ))}
              </div>
            </div>
            )}
          </div>
        )}

        {bindMode !== "closed" && (
          <div className="mt-4 border border-[#c9a9c0]/40 bg-[#0f1a16] p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm text-[#c9a9c0]">
                Bind {bindPlacement} button to a real Odoo action
              </p>
              <div className="flex flex-wrap gap-2 text-xs">
                {(
                  [
                    ["create_update", "Update field"],
                    ["create_related", "Open related"],
                    ["create_activity", "Next activity"],
                    ["create_mail", "Send mail"],
                    ["create_smart", "Smart button"],
                    ["bind_existing", "Existing action"],
                  ] as const
                ).map(([mode, label]) => {
                  const allowed = bindModeSupported(connection, mode);
                  const reason = bindModeUnsupportedReason(connection, mode);
                  return (
                    <button
                      key={mode}
                      type="button"
                      disabled={!allowed}
                      title={reason ?? undefined}
                      className={
                        !allowed
                          ? "cursor-not-allowed text-[#4a5c54] opacity-50"
                          : bindMode === mode
                            ? "text-[#c9a9c0]"
                            : "text-[#8f7a88]"
                      }
                      onClick={() => {
                        if (!allowed) return;
                        openBindDialog(bindPlacement, mode);
                      }}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
              {!bindModeSupported(connection, bindMode) && (
                <p className="mt-2 w-full text-[11px] text-[#e8d09f]">
                  {bindModeUnsupportedReason(connection, bindMode)}
                </p>
              )}
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-xs text-[#a8909e]">
                Button label
                <input
                  value={bindLabel}
                  onChange={(e) => setBindLabel(e.target.value)}
                  className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-sm"
                />
              </label>
              {bindMode === "create_update" && (
                <>
                  <label className="text-xs text-[#a8909e]">
                    Field to update
                    <select
                      value={bindFieldName}
                      onChange={(e) => {
                        const name = e.target.value;
                        setBindFieldName(name);
                        const meta = fields.find((f) => f.name === name);
                        const opts = parseSelectionOptions(meta?.selection);
                        if (opts[0]) setBindValue(opts[0].value);
                      }}
                      className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 font-mono text-sm"
                    >
                      <option value="">Select field…</option>
                      {fields
                        .filter((f) =>
                          ["char", "text", "selection", "boolean", "integer", "float"].includes(
                            f.ttype,
                          ),
                        )
                        .map((f) => (
                          <option key={f.id} value={f.name}>
                            {f.name} · {f.ttype}
                          </option>
                        ))}
                    </select>
                  </label>
                  <label className="text-xs text-[#a8909e]">
                    New value
                    {(() => {
                      const opts = parseSelectionOptions(
                        fields.find((f) => f.name === bindFieldName)?.selection,
                      );
                      if (opts.length) {
                        return (
                          <select
                            value={bindValue}
                            onChange={(e) => setBindValue(e.target.value)}
                            className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-sm"
                          >
                            {opts.map((o) => (
                              <option key={o.value} value={o.value}>
                                {o.label} ({o.value})
                              </option>
                            ))}
                          </select>
                        );
                      }
                      return (
                        <input
                          value={bindValue}
                          onChange={(e) => setBindValue(e.target.value)}
                          className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-sm"
                        />
                      );
                    })()}
                  </label>
                </>
              )}
              {(bindMode === "create_related" || bindMode === "create_smart") && (
                <>
                  <label className="text-xs text-[#a8909e]">
                    Target model
                    <input
                      value={bindTargetModel}
                      onChange={(e) => setBindTargetModel(e.target.value)}
                      className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 font-mono text-sm"
                    />
                  </label>
                  <label className="text-xs text-[#a8909e]">
                    Relation field on target
                    <input
                      value={bindRelationField}
                      onChange={(e) => setBindRelationField(e.target.value)}
                      className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 font-mono text-sm"
                    />
                  </label>
                  {(bindPlacement === "button_box" || bindMode === "create_smart") && (
                    <label className="text-xs text-[#a8909e]">
                      Icon (Font Awesome)
                      <input
                        value={bindIcon}
                        onChange={(e) => setBindIcon(e.target.value)}
                        className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 font-mono text-sm"
                      />
                    </label>
                  )}
                </>
              )}
              {bindMode === "create_smart" && (
                <>
                  <label className="flex items-center gap-2 text-xs text-[#a8909e] sm:col-span-2">
                    <input
                      type="checkbox"
                      checked={bindCreateCountField}
                      onChange={(e) => setBindCreateCountField(e.target.checked)}
                    />
                    Create computed count field (advanced — confirm required)
                  </label>
                  {bindCreateCountField && (
                    <>
                      <label className="text-xs text-[#a8909e]">
                        One2many field on source
                        <input
                          value={bindOne2manyField}
                          onChange={(e) => setBindOne2manyField(e.target.value)}
                          placeholder="x_loan_ids"
                          className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 font-mono text-sm"
                        />
                      </label>
                      <label className="text-xs text-[#a8909e]">
                        Count field name (optional)
                        <input
                          value={bindCountFieldName}
                          onChange={(e) => setBindCountFieldName(e.target.value)}
                          placeholder="x_loan_count"
                          className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 font-mono text-sm"
                        />
                      </label>
                      <label className="text-xs text-[#a8909e] sm:col-span-2">
                        Confirm phrase
                        <input
                          value={bindSmartConfirmPhrase}
                          onChange={(e) => setBindSmartConfirmPhrase(e.target.value)}
                          placeholder={CONFIRM_PHRASE}
                          className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-sm"
                        />
                      </label>
                    </>
                  )}
                </>
              )}
              {bindMode === "create_activity" && (
                <>
                  <label className="text-xs text-[#a8909e]">
                    Activity type
                    <select
                      value={bindActivityTypeId === "" ? "" : String(bindActivityTypeId)}
                      onChange={(e) =>
                        setBindActivityTypeId(e.target.value ? Number(e.target.value) : "")
                      }
                      className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-sm"
                    >
                      <option value="">Select…</option>
                      {activityTypes.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="text-xs text-[#a8909e]">
                    Summary
                    <input
                      value={bindActivitySummary}
                      onChange={(e) => setBindActivitySummary(e.target.value)}
                      className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-sm"
                    />
                  </label>
                  <label className="text-xs text-[#a8909e] sm:col-span-2">
                    Note (optional)
                    <input
                      value={bindActivityNote}
                      onChange={(e) => setBindActivityNote(e.target.value)}
                      className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-sm"
                    />
                  </label>
                </>
              )}
              {bindMode === "create_mail" && (
                <>
                  <label className="text-xs text-[#a8909e]">
                    Mail template (optional)
                    <select
                      value={bindMailTemplateId === "" ? "" : String(bindMailTemplateId)}
                      onChange={(e) =>
                        setBindMailTemplateId(e.target.value ? Number(e.target.value) : "")
                      }
                      className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-sm"
                    >
                      <option value="">None</option>
                      {mailTemplates.map((t) => (
                        <option key={t.id} value={t.id}>
                          #{t.id} · {t.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="text-xs text-[#a8909e]">
                    Method
                    <select
                      value={bindMailMethod}
                      onChange={(e) =>
                        setBindMailMethod(e.target.value as "email" | "comment" | "note")
                      }
                      className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-sm"
                    >
                      <option value="email">email</option>
                      <option value="comment">comment</option>
                      <option value="note">note</option>
                    </select>
                  </label>
                  <label className="text-xs text-[#a8909e]">
                    Subject
                    <input
                      value={bindMailSubject}
                      onChange={(e) => setBindMailSubject(e.target.value)}
                      className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-sm"
                    />
                  </label>
                  <label className="text-xs text-[#a8909e]">
                    Email to
                    <input
                      value={bindMailEmailTo}
                      onChange={(e) => setBindMailEmailTo(e.target.value)}
                      className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-sm"
                    />
                  </label>
                  <label className="text-xs text-[#a8909e] sm:col-span-2">
                    Body HTML
                    <textarea
                      value={bindMailBody}
                      onChange={(e) => setBindMailBody(e.target.value)}
                      rows={3}
                      className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 font-mono text-xs"
                    />
                  </label>
                </>
              )}
              {bindMode === "bind_existing" && (
                <label className="text-xs text-[#a8909e] sm:col-span-2">
                  Action
                  <select
                    value={selectedActionId === "" ? "" : String(selectedActionId)}
                    onChange={(e) =>
                      setSelectedActionId(e.target.value ? Number(e.target.value) : "")
                    }
                    className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-sm"
                  >
                    <option value="">Select…</option>
                    {bindableActions.map((a) => (
                      <option key={`${a.action_type}-${a.id}`} value={a.id}>
                        #{a.id} · {a.action_type} · {a.name}
                        {a.detail ? ` (${a.detail})` : ""}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
            <p className="mt-2 text-xs text-[#8f7a88]">
              Uses type=&quot;action&quot; + action id. Python methods (type=object) need Option A
              modules. Code/webhook server actions stay blocked here. Form-bound mail/activity
              live here; model automations live under Automations.
            </p>
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                disabled={busy || !bindModeSupported(connection, bindMode)}
                title={
                  bindModeUnsupportedReason(connection, bindMode) ?? undefined
                }
                onClick={() =>
                  void submitBindDialog(
                    bindMode === "create_smart" && bindCreateCountField
                      ? {
                          confirm_advanced: true,
                          confirm_phrase: bindSmartConfirmPhrase || CONFIRM_PHRASE,
                        }
                      : undefined,
                  )
                }
                className="border border-[#c9a9c0] px-3 py-1.5 text-sm text-[#c9a9c0] disabled:opacity-50"
              >
                Create &amp; bind
              </button>
              <button
                type="button"
                onClick={() => setBindMode("closed")}
                className="border border-[#3d2a38] px-3 py-1.5 text-sm text-[#d4c4ce]"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {showIframePreview && proxyPreviewUrl && (
          <div className="mt-4 border border-[#3d2a38] bg-[#0c090b]">
            <p className="border-b border-[#3d2a38] px-3 py-2 text-xs text-[#8f7a88]">
              Iframe preview is best-effort — use Open in Odoo for the authoritative client.
            </p>
            <iframe
              key={previewKey}
              title="Odoo live preview"
              src={proxyPreviewUrl}
              className="h-72 w-full"
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
            />
          </div>
        )}

        <div className="mt-8 grid gap-6 lg:grid-cols-[220px_1fr_280px]">
          <aside className="border border-[#3d2a38] bg-[#0f1a16]/70 p-4">
            <p className="text-xs uppercase tracking-wide text-[#8f7a88]">Fields</p>
            <div className="mt-3 space-y-2 border border-[#3d2a38] p-2 text-xs">
              <p className="text-[#8f7a88]">Create field on model</p>
              <input
                value={newFieldName}
                onChange={(e) => setNewFieldName(e.target.value)}
                placeholder="x_my_field"
                className="w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1 font-mono"
              />
              <input
                value={newFieldLabel}
                onChange={(e) => setNewFieldLabel(e.target.value)}
                placeholder="Label"
                className="w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1"
              />
              <select
                value={newFieldType}
                onChange={(e) => setNewFieldType(e.target.value)}
                className="w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1"
              >
                <option value="char">char</option>
                <option value="text">text</option>
                <option value="integer">integer</option>
                <option value="float">float</option>
                <option value="boolean">boolean</option>
                <option value="date">date</option>
                <option value="selection">selection</option>
                <option value="many2one">many2one</option>
                <option value="json">json</option>
              </select>
              <label className="block text-[11px] text-[#a8909e]">
                Inject strategy
                <select
                  value={injectStrategy}
                  onChange={(e) =>
                    setInjectStrategy(e.target.value as "inherit" | "mutate")
                  }
                  className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1 text-sm text-[#faf6f9]"
                >
                  <option
                    value="inherit"
                    disabled={!connectionSupports(connection, "view_inject_inherit")}
                  >
                    inherit (xpath child)
                    {!connectionSupports(connection, "view_inject_inherit")
                      ? " — unavailable"
                      : ""}
                  </option>
                  <option
                    value="mutate"
                    disabled={!connectionSupports(connection, "view_inject_mutate")}
                    title={
                      connectionUnsupportedReason(connection, "view_inject_mutate") ??
                      undefined
                    }
                  >
                    mutate (overwrite parent)
                    {!connectionSupports(connection, "view_inject_mutate")
                      ? " — unavailable"
                      : ""}
                  </option>
                </select>
              </label>
              {!connectionSupports(
                connection,
                injectStrategyCapabilityId(injectStrategy),
              ) && (
                <p className="text-[11px] text-[#e8d09f]">
                  {connectionUnsupportedReason(
                    connection,
                    injectStrategyCapabilityId(injectStrategy),
                  )}
                </p>
              )}
              {injectStrategy === "mutate" &&
                connectionSupports(connection, "view_inject_mutate") && (
                  <p className="text-[11px] text-[#e8d09f]">
                    Mutate overwrites parent view arch — requires advanced confirm.
                  </p>
                )}
              <input
                value={confirmPhrase}
                onChange={(e) => setConfirmPhrase(e.target.value)}
                placeholder="I understand the risks"
                className="w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1"
              />
              <button
                type="button"
                disabled={
                  busy ||
                  !model ||
                  !newFieldName.startsWith("x_") ||
                  !connectionSupports(
                    connection,
                    injectStrategyCapabilityId(injectStrategy),
                  )
                }
                title={
                  connectionUnsupportedReason(
                    connection,
                    injectStrategyCapabilityId(injectStrategy),
                  ) ?? undefined
                }
                className="w-full border border-[#c9a9c0] px-2 py-1 text-[#c9a9c0] disabled:opacity-40"
                onClick={() => void createNewFieldWithInject()}
              >
                Create + inject
              </button>
            </div>
            <ul className="mt-3 max-h-[28rem] space-y-1 overflow-auto text-sm">
              {fields.map((f) => (
                <li
                  key={f.id}
                  draggable={viewType === "form" || viewType === "kanban"}
                  onDragStart={(e) => {
                    setDragField(f.name);
                    e.dataTransfer.setData("text/odoo-field", f.name);
                  }}
                  onClick={() => {
                    if (viewType === "list") addListColumn(f.name);
                    if (viewType === "search") addSearchField(f.name);
                    if (viewType === "kanban") addKanbanField(f.name);
                  }}
                  className="cursor-grab border border-transparent px-2 py-1.5 hover:border-[#3d2a38]"
                >
                  <span className="font-mono text-[#c9a9c0]">{f.name}</span>
                  <span className="block text-xs text-[#8f7a88]">
                    {f.field_description} · {f.ttype}
                  </span>
                </li>
              ))}
              {fields.length === 0 && (
                <li className="text-[#8f7a88]">Load a model to populate.</li>
              )}
            </ul>
          </aside>

          <section className="border border-[#3d2a38] bg-[#0f1a16]/50 p-4">
            <div className="mb-4 flex flex-wrap gap-2">
              {viewType === "form" && (
                <>
                  <button
                    type="button"
                    onClick={addGroup}
                    className={`border px-3 py-1 text-xs ${
                      toolbarFlash === "group"
                        ? "border-[#c9a9c0] bg-[#3d2a38] text-[#f5eef3]"
                        : "border-[#3d2a38] text-[#d4c4ce]"
                    }`}
                  >
                    {toolbarFlash === "group" ? "✓ Group added" : "+ Group"}
                  </button>
                  <button
                    type="button"
                    onClick={addNotebook}
                    className={`border px-3 py-1 text-xs ${
                      toolbarFlash === "notebook"
                        ? "border-[#c9a9c0] bg-[#3d2a38] text-[#f5eef3]"
                        : "border-[#3d2a38] text-[#d4c4ce]"
                    }`}
                  >
                    {toolbarFlash === "notebook" ? "✓ Notebook added" : "+ Notebook"}
                  </button>
                  <button
                    type="button"
                    disabled={!connectionSupports(connection, "object_write_update_path")}
                    title={
                      connectionUnsupportedReason(connection, "object_write_update_path") ??
                      undefined
                    }
                    onClick={() => {
                      openBindDialog("header", "create_update");
                      announceAction("Opening header button binder…", null, "header");
                    }}
                    className={`border px-3 py-1 text-xs disabled:opacity-40 ${
                      toolbarFlash === "header"
                        ? "border-[#c9a9c0] bg-[#3d2a38] text-[#f5eef3]"
                        : "border-[#c9a9c0] text-[#c9a9c0]"
                    }`}
                  >
                    {toolbarFlash === "header" ? "✓ Header binder" : "+ Header button"}
                  </button>
                  <button
                    type="button"
                    disabled={!connectionSupports(connection, "smart_button_inherit_box")}
                    title={
                      connectionUnsupportedReason(connection, "smart_button_inherit_box") ??
                      undefined
                    }
                    onClick={() => {
                      openBindDialog("button_box", "create_smart");
                      announceAction("Opening smart button binder…", null, "smart");
                    }}
                    className={`border px-3 py-1 text-xs disabled:opacity-40 ${
                      toolbarFlash === "smart"
                        ? "border-[#c9a9c0] bg-[#3d2a38] text-[#f5eef3]"
                        : "border-[#c9a9c0] text-[#c9a9c0]"
                    }`}
                  >
                    {toolbarFlash === "smart" ? "✓ Smart binder" : "+ Smart button"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      addButtonToFirstGroup();
                      announceAction("Opening inline button binder…", null, "inline");
                    }}
                    className={`border px-3 py-1 text-xs ${
                      toolbarFlash === "inline"
                        ? "border-[#c9a9c0] bg-[#3d2a38] text-[#f5eef3]"
                        : "border-[#3d2a38] text-[#d4c4ce]"
                    }`}
                  >
                    {toolbarFlash === "inline" ? "✓ Inline binder" : "+ Inline button"}
                  </button>
                </>
              )}
            </div>

            {viewType === "form" && (
              <div className="mb-4 space-y-3">
                <div className="flex flex-wrap gap-4 border border-dashed border-[#4a3550] p-3 text-sm text-[#d4c4ce]">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={formCanCreate}
                      onChange={(e) => setFormCanCreate(e.target.checked)}
                    />
                    Can Create
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={formCanEdit}
                      onChange={(e) => setFormCanEdit(e.target.checked)}
                    />
                    Can Edit
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={formCanDelete}
                      onChange={(e) => setFormCanDelete(e.target.checked)}
                    />
                    Can Delete
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={formCanDuplicate}
                      onChange={(e) => setFormCanDuplicate(e.target.checked)}
                    />
                    Can Duplicate
                  </label>
                </div>
                <div className="grid gap-3 border border-dashed border-[#4a3550] p-3 sm:grid-cols-2">
                  <label className="text-xs text-[#a8909e]">
                    Statusbar field (selection)
                    <select
                      value={statusbarField}
                      onChange={(e) => setStatusbarField(e.target.value)}
                      className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 font-mono text-sm"
                    >
                      <option value="">(none)</option>
                      {fields
                        .filter((f) => f.ttype === "selection" || f.ttype === "many2one")
                        .map((f) => (
                          <option key={f.id} value={f.name}>
                            {f.name} · {f.ttype}
                          </option>
                        ))}
                    </select>
                  </label>
                  <label className="text-xs text-[#a8909e]">
                    statusbar_visible (comma-separated)
                    <input
                      value={statusbarVisible}
                      onChange={(e) => setStatusbarVisible(e.target.value)}
                      placeholder="draft,confirmed,done"
                      disabled={!statusbarField}
                      className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 font-mono text-sm disabled:opacity-40"
                    />
                  </label>
                </div>
                <div className="min-h-12 border border-dashed border-[#4a3550] p-3">
                  <p className="mb-2 text-xs uppercase text-[#8f7a88]">Header buttons</p>
                  <ul className="space-y-1">
                    {headerButtons.map((b) => (
                      <li
                        key={b.id}
                        className="flex items-center justify-between bg-[#0c090b] px-2 py-1.5 text-sm"
                      >
                        <span className="text-[#c9b89f]">
                          {b.string}{" "}
                          <span className="font-mono text-xs text-[#8f7a88]">
                            type={b.type || "action"} name={b.name || "?"}
                          </span>
                        </span>
                        <button
                          type="button"
                          className="text-xs text-[#f0a8a0]"
                          onClick={() =>
                            setHeaderButtons((all) => all.filter((x) => x.id !== b.id))
                          }
                        >
                          remove
                        </button>
                      </li>
                    ))}
                    {headerButtons.length === 0 && (
                      <li className="text-xs text-[#8f7a88]">
                        Bound to real ir.actions.* via type=&quot;action&quot;.
                      </li>
                    )}
                  </ul>
                </div>
                <div className="min-h-12 border border-dashed border-[#4a3550] p-3">
                  <p className="mb-2 text-xs uppercase text-[#8f7a88]">Smart button box</p>
                  <ul className="space-y-1">
                    {buttonBox.map((b) => (
                      <li
                        key={b.id}
                        className="flex items-center justify-between bg-[#0c090b] px-2 py-1.5 text-sm"
                      >
                        <span className="text-[#c9b89f]">
                          {b.string}{" "}
                          <span className="font-mono text-xs text-[#8f7a88]">
                            {b.icon || "fa-list"} · action {b.name || "?"}
                            {b.count_field ? ` · count ${b.count_field}` : ""}
                          </span>
                        </span>
                        <button
                          type="button"
                          className="text-xs text-[#f0a8a0]"
                          onClick={() => setButtonBox((all) => all.filter((x) => x.id !== b.id))}
                        >
                          remove
                        </button>
                      </li>
                    ))}
                    {buttonBox.length === 0 && (
                      <li className="text-xs text-[#8f7a88]">
                        Opens related records (window action + active_id domain).
                      </li>
                    )}
                  </ul>
                </div>
              </div>
            )}

            {viewType === "form" &&
              formChildren.map((child) => {
                if (child.kind === "group") {
                  return (
                    <div
                      key={child.id}
                      data-canvas-id={child.id}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={() => dropOnGroup(child.id)}
                      className={`mb-4 min-h-24 border border-dashed border-[#4a3550] p-3 ${
                        canvasFlashId === child.id ? "ring-2 ring-[#c9a9c0]" : ""
                      }`}
                    >
                      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                        <label className="flex min-w-0 flex-1 items-center gap-2 text-xs uppercase text-[#8f7a88]">
                          Group
                          <input
                            value={child.string || ""}
                            onChange={(e) => renameGroup(child.id, e.target.value)}
                            className="min-w-0 flex-1 border border-[#3d2a38] bg-[#0c090b] px-2 py-1 font-sans text-sm normal-case text-[#d4c4ce]"
                            placeholder="untitled"
                          />
                        </label>
                        <button
                          type="button"
                          className="shrink-0 text-xs text-[#f0a8a0]"
                          onClick={() => removeFormChild(child.id)}
                        >
                          remove group
                        </button>
                      </div>
                      <ul className="space-y-1">
                        {child.children.map((f) => (
                          <li
                            key={f.id}
                            className={`flex items-center justify-between bg-[#0c090b] px-2 py-1.5 text-sm ${
                              selected?.fieldId === f.id ? "ring-1 ring-[#c9a9c0]" : ""
                            }`}
                          >
                            <button
                              type="button"
                              className="text-left"
                              onClick={() =>
                                setSelected({
                                  scope: "form-group",
                                  groupId: child.id,
                                  fieldId: f.id,
                                })
                              }
                            >
                              {f.kind === "button" ? (
                                <span className="text-[#c9b89f]">
                                  Btn · {f.string}{" "}
                                  <span className="font-mono text-xs text-[#8f7a88]">
                                    {f.type || "action"}:{f.name || "?"}
                                  </span>
                                </span>
                              ) : (
                                <>
                                  <span className="font-mono text-[#c9a9c0]">{f.name}</span>
                                  {f.string ? ` — ${f.string}` : ""}
                                </>
                              )}
                            </button>
                            <button
                              type="button"
                              className="text-xs text-[#f0a8a0]"
                              onClick={() => removeFormField("group", child.id, f.id)}
                            >
                              remove
                            </button>
                          </li>
                        ))}
                        {child.children.length === 0 && (
                          <li className="text-xs text-[#8f7a88]">Drop fields here</li>
                        )}
                      </ul>
                    </div>
                  );
                }
                return (
                  <div
                    key={child.id}
                    data-canvas-id={child.id}
                    className={`mb-4 border border-[#3d2a38] p-3 ${
                      canvasFlashId === child.id ? "ring-2 ring-[#c9a9c0]" : ""
                    }`}
                  >
                    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                      <p className="text-xs uppercase text-[#8f7a88]">Notebook</p>
                      <div className="flex gap-3">
                        <button
                          type="button"
                          className="text-xs text-[#c9a9c0]"
                          onClick={() => addPageToNotebook(child.id)}
                        >
                          + Page
                        </button>
                        <button
                          type="button"
                          className="text-xs text-[#f0a8a0]"
                          onClick={() => removeFormChild(child.id)}
                        >
                          remove notebook
                        </button>
                      </div>
                    </div>
                    {child.pages.map((page) => (
                      <div
                        key={page.id}
                        data-canvas-id={page.id}
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={() => dropOnPage(child.id, page.id)}
                        className={`mb-3 min-h-20 border border-dashed border-[#4a3550] p-3 ${
                          canvasFlashId === page.id ? "ring-2 ring-[#c9a9c0]" : ""
                        }`}
                      >
                        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                          <label className="flex min-w-0 flex-1 items-center gap-2 text-sm text-[#d4c4ce]">
                            Page
                            <input
                              value={page.string}
                              onChange={(e) =>
                                renameNotebookPage(child.id, page.id, e.target.value)
                              }
                              className="min-w-0 flex-1 border border-[#3d2a38] bg-[#0c090b] px-2 py-1 font-mono text-sm"
                              placeholder="Tab title"
                            />
                          </label>
                          <button
                            type="button"
                            className="shrink-0 text-xs text-[#f0a8a0]"
                            onClick={() => removeNotebookPage(child.id, page.id)}
                          >
                            remove page
                          </button>
                        </div>
                        <ul className="space-y-1">
                          {page.children.map((f) => (
                            <li
                              key={f.id}
                              className={`flex items-center justify-between bg-[#0c090b] px-2 py-1.5 text-sm ${
                                selected?.fieldId === f.id ? "ring-1 ring-[#c9a9c0]" : ""
                              }`}
                            >
                              <button
                                type="button"
                                className="text-left"
                                onClick={() =>
                                  f.kind === "field"
                                    ? setSelected({
                                        scope: "form-page",
                                        notebookId: child.id,
                                        pageId: page.id,
                                        fieldId: f.id,
                                      })
                                    : undefined
                                }
                              >
                                {f.kind === "button" ? (
                                  <span className="text-[#c9b89f]">Btn · {f.string}</span>
                                ) : (
                                  <>
                                    <span className="text-[#d4c4ce]">
                                      {resolveFieldLabel(f.name, f.string, fields) || f.name}
                                    </span>
                                    <span className="ml-2 font-mono text-xs text-[#8f7a88]">
                                      {f.name}
                                    </span>
                                  </>
                                )}
                              </button>
                              <button
                                type="button"
                                className="text-xs text-[#f0a8a0]"
                                onClick={() =>
                                  removeFormField("page", page.id, f.id, child.id)
                                }
                              >
                                remove
                              </button>
                            </li>
                          ))}
                          {page.children.length === 0 && (
                            <li className="text-xs text-[#8f7a88]">Drop fields here</li>
                          )}
                        </ul>
                      </div>
                    ))}
                  </div>
                );
              })}

            {viewType === "list" && (
              <div className="min-h-40 border border-dashed border-[#4a3550] p-3">
                <div className="mb-3 flex flex-wrap gap-4 text-sm text-[#d4c4ce]">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={listCanCreate}
                      onChange={(e) => setListCanCreate(e.target.checked)}
                    />
                    Can Create
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={listCanEdit}
                      onChange={(e) => setListCanEdit(e.target.checked)}
                    />
                    Can Edit
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={listCanDelete}
                      onChange={(e) => setListCanDelete(e.target.checked)}
                    />
                    Can Delete
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={listMultiEdit}
                      onChange={(e) => setListMultiEdit(e.target.checked)}
                    />
                    multi_edit
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={viewSample}
                      onChange={(e) => setViewSample(e.target.checked)}
                      data-testid="designer-view-sample"
                    />
                    sample data
                  </label>
                </div>
                <label className="mb-3 block text-xs text-[#8f7a88]">
                  default_order (Sort By)
                  <input
                    value={listDefaultOrder}
                    onChange={(e) => setListDefaultOrder(e.target.value)}
                    placeholder="name asc, id desc"
                    className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1 font-mono"
                  />
                </label>
                <div className="mb-3 grid gap-2 sm:grid-cols-3">
                  <label className="block text-xs text-[#8f7a88]">
                    decoration-danger
                    <input
                      value={listDecorationDanger}
                      onChange={(e) => setListDecorationDanger(e.target.value)}
                      placeholder="not x_returned"
                      className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1 font-mono"
                    />
                  </label>
                  <label className="block text-xs text-[#8f7a88]">
                    decoration-info
                    <input
                      value={listDecorationInfo}
                      onChange={(e) => setListDecorationInfo(e.target.value)}
                      placeholder="x_priority == 'high'"
                      className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1 font-mono"
                    />
                  </label>
                  <label className="block text-xs text-[#8f7a88]">
                    decoration-muted
                    <input
                      value={listDecorationMuted}
                      onChange={(e) => setListDecorationMuted(e.target.value)}
                      placeholder="x_active == False"
                      className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1 font-mono"
                    />
                  </label>
                </div>
                <p className="mb-2 text-xs uppercase text-[#8f7a88]">
                  List columns (click a field to add)
                </p>
                <ul className="space-y-1">
                  {listColumns.map((f, idx) => (
                    <li
                      key={f.id}
                      className={`flex items-center justify-between bg-[#0c090b] px-2 py-1.5 text-sm ${
                        selected?.fieldId === f.id ? "ring-1 ring-[#c9a9c0]" : ""
                      }`}
                    >
                      <button
                        type="button"
                        className="text-left"
                        onClick={() => setSelected({ scope: "list", fieldId: f.id })}
                      >
                        {idx + 1}.{" "}
                        <span className="font-mono text-[#c9a9c0]">{f.name}</span>
                      </button>
                      <button
                        type="button"
                        className="text-xs text-[#f0a8a0]"
                        onClick={() => {
                          setListColumns((cols) => cols.filter((c) => c.id !== f.id));
                          setSelected((sel) => (sel?.fieldId === f.id ? null : sel));
                        }}
                      >
                        remove
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {viewType === "search" && (
              <div className="min-h-40 border border-dashed border-[#4a3550] p-3">
                <p className="mb-2 text-xs uppercase text-[#8f7a88]">
                  Search fields (click a field to add)
                </p>
                <button
                  type="button"
                  className="mb-2 text-xs text-[#c9a9c0]"
                  onClick={() =>
                    setSearchFilters((f) => [
                      ...f,
                      {
                        id: uid("sf"),
                        name: `filter_${f.length + 1}`,
                        string: `Filter ${f.length + 1}`,
                        domain: "[]",
                      },
                    ])
                  }
                >
                  + Add search filter
                </button>
                {searchFilters.length > 0 && (
                  <ul className="mb-3 space-y-3 text-xs text-[#d4c4ce]">
                    {searchFilters.map((f) => (
                      <li key={f.id} className="border border-[#1e2f29] p-2">
                        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                          <input
                            value={f.string}
                            onChange={(e) =>
                              setSearchFilters((all) =>
                                all.map((x) =>
                                  x.id === f.id ? { ...x, string: e.target.value } : x,
                                ),
                              )
                            }
                            className="min-w-[8rem] flex-1 border border-[#3d2a38] bg-[#0c090b] px-2 py-1"
                          />
                          <button
                            type="button"
                            className="text-[#c9a9c0]"
                            onClick={() =>
                              setEditingFilterId((id) => (id === f.id ? null : f.id))
                            }
                          >
                            {editingFilterId === f.id ? "Hide domain" : "Edit domain"}
                          </button>
                          <button
                            type="button"
                            className="text-[#f0a8a0]"
                            onClick={() =>
                              setSearchFilters((all) => all.filter((x) => x.id !== f.id))
                            }
                          >
                            remove
                          </button>
                        </div>
                        {editingFilterId === f.id ? (
                          <DomainBuilder
                            value={f.domain || "[]"}
                            onChange={(domain) =>
                              setSearchFilters((all) =>
                                all.map((x) => (x.id === f.id ? { ...x, domain } : x)),
                              )
                            }
                          />
                        ) : (
                          <span className="font-mono text-[#8f7a88]">{f.domain || "[]"}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                <div className="mb-3 border border-[#1e2f29] p-2">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <p className="text-xs uppercase text-[#8f7a88]">Group-by filters</p>
                    <button
                      type="button"
                      className="text-xs text-[#c9a9c0]"
                      onClick={() =>
                        setSearchGroupByFilters((f) => [
                          ...f,
                          {
                            id: uid("sg"),
                            name: `groupby_${f.length + 1}`,
                            string: `Group By ${f.length + 1}`,
                            context: "{'group_by': 'field'}",
                          },
                        ])
                      }
                    >
                      + Add group-by filter
                    </button>
                  </div>
                  {searchGroupByFilters.length === 0 ? (
                    <p className="text-xs text-[#8f7a88]">
                      No group-by filters. Context example:{" "}
                      <code className="text-[#c9a9c0]">{"{'group_by': 'x_stage'}"}</code>
                    </p>
                  ) : (
                    <ul className="space-y-2 text-xs text-[#d4c4ce]">
                      {searchGroupByFilters.map((f) => (
                        <li key={f.id} className="grid gap-2 border border-[#3d2a38] p-2 sm:grid-cols-3">
                          <label className="block">
                            name
                            <input
                              value={f.name}
                              onChange={(e) =>
                                setSearchGroupByFilters((all) =>
                                  all.map((x) =>
                                    x.id === f.id ? { ...x, name: e.target.value } : x,
                                  ),
                                )
                              }
                              className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1 font-mono"
                            />
                          </label>
                          <label className="block">
                            string
                            <input
                              value={f.string}
                              onChange={(e) =>
                                setSearchGroupByFilters((all) =>
                                  all.map((x) =>
                                    x.id === f.id ? { ...x, string: e.target.value } : x,
                                  ),
                                )
                              }
                              className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1"
                            />
                          </label>
                          <label className="block">
                            context
                            <input
                              value={f.context ?? ""}
                              onChange={(e) =>
                                setSearchGroupByFilters((all) =>
                                  all.map((x) =>
                                    x.id === f.id
                                      ? { ...x, context: e.target.value }
                                      : x,
                                  ),
                                )
                              }
                              placeholder="{'group_by': 'field'}"
                              className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1 font-mono"
                            />
                          </label>
                          <button
                            type="button"
                            className="justify-self-start text-[#f0a8a0] sm:col-span-3"
                            onClick={() =>
                              setSearchGroupByFilters((all) =>
                                all.filter((x) => x.id !== f.id),
                              )
                            }
                          >
                            remove
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <ul className="space-y-1">
                  {searchFields.map((f, idx) => (
                    <li
                      key={f.id}
                      className={`flex items-center justify-between bg-[#0c090b] px-2 py-1.5 text-sm ${
                        selected?.fieldId === f.id ? "ring-1 ring-[#c9a9c0]" : ""
                      }`}
                    >
                      <button
                        type="button"
                        className="text-left"
                        onClick={() => setSelected({ scope: "search", fieldId: f.id })}
                      >
                        {idx + 1}.{" "}
                        <span className="font-mono text-[#c9a9c0]">{f.name}</span>
                      </button>
                      <button
                        type="button"
                        className="text-xs text-[#f0a8a0]"
                        onClick={() => {
                          setSearchFields((cols) => cols.filter((c) => c.id !== f.id));
                          setSelected((sel) => (sel?.fieldId === f.id ? null : sel));
                        }}
                      >
                        remove
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {viewType === "kanban" && (
              <div className="min-h-40 space-y-3">
                <div className="flex flex-wrap gap-4 border border-dashed border-[#4a3550] p-3 text-sm text-[#d4c4ce]">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={kanbanCanCreate}
                      onChange={(e) => setKanbanCanCreate(e.target.checked)}
                    />
                    Can Create
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={kanbanQuickCreate}
                      onChange={(e) => setKanbanQuickCreate(e.target.checked)}
                    />
                    quick_create
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={viewSample}
                      onChange={(e) => setViewSample(e.target.checked)}
                      data-testid="designer-view-sample"
                    />
                    sample data
                  </label>
                </div>
                {!model && (
                  <KanbanCardPreview
                    title={title || "Kanban"}
                    groupBy={kanbanGroupBy || null}
                    fields={kanbanFields.map((f) => ({
                      id: f.id,
                      name: f.name,
                      string: f.string,
                    }))}
                    selectedFieldId={
                      selected?.scope === "kanban" ? selected.fieldId : null
                    }
                    onSelectField={(fieldId) =>
                      setSelected({ scope: "kanban", fieldId })
                    }
                    onMoveField={moveKanbanField}
                    onRemoveField={(fieldId) => {
                      setKanbanFields((cols) =>
                        cols.filter((c) => c.id !== fieldId),
                      );
                      setSelected((sel) =>
                        sel?.scope === "kanban" && sel.fieldId === fieldId
                          ? null
                          : sel,
                      );
                    }}
                    onDropFieldName={(fieldName) => addKanbanField(fieldName)}
                  />
                )}
                <div className="border border-[#4a3550] bg-[#0c090b]/80 p-3">
                  <p className="mb-2 text-xs uppercase tracking-wide text-[#8f7a88]">
                    Card field order
                    {kanbanGroupBy ? (
                      <span className="ml-2 rounded bg-[#714b67] px-1.5 py-0.5 text-[10px] normal-case text-white">
                        group by {kanbanGroupBy}
                      </span>
                    ) : null}
                  </p>
                  <ul className="space-y-1">
                    {kanbanFields.map((f, idx) => (
                      <li
                        key={f.id}
                        className={`flex items-center justify-between gap-2 px-2 py-1.5 text-sm ${
                          selected?.scope === "kanban" && selected.fieldId === f.id
                            ? "bg-[#1a2e28] ring-1 ring-[#c9a9c0]"
                            : "bg-[#0c1210]"
                        }`}
                      >
                        <button
                          type="button"
                          className="min-w-0 flex-1 text-left"
                          onClick={() =>
                            setSelected({ scope: "kanban", fieldId: f.id })
                          }
                        >
                          <span className="text-[#8f7a88]">{idx + 1}.</span>{" "}
                          <span className="font-mono text-[#c9a9c0]">{f.name}</span>
                          {f.string ? (
                            <span className="ml-2 text-xs text-[#8f7a88]">
                              {f.string}
                            </span>
                          ) : null}
                        </button>
                        <span className="flex shrink-0 items-center gap-2">
                          <button
                            type="button"
                            className="text-xs text-[#c9a9c0] disabled:opacity-30"
                            disabled={idx === 0}
                            aria-label={`Move ${f.name} up`}
                            onClick={() => moveKanbanField(f.id, -1)}
                          >
                            ↑
                          </button>
                          <button
                            type="button"
                            className="text-xs text-[#c9a9c0] disabled:opacity-30"
                            disabled={idx >= kanbanFields.length - 1}
                            aria-label={`Move ${f.name} down`}
                            onClick={() => moveKanbanField(f.id, 1)}
                          >
                            ↓
                          </button>
                          <button
                            type="button"
                            className="text-xs text-[#f0a8a0]"
                            onClick={() => {
                              setKanbanFields((cols) =>
                                cols.filter((c) => c.id !== f.id),
                              );
                              setSelected((sel) =>
                                sel?.scope === "kanban" && sel.fieldId === f.id
                                  ? null
                                  : sel,
                              );
                            }}
                          >
                            remove
                          </button>
                        </span>
                      </li>
                    ))}
                    {kanbanFields.length === 0 && (
                      <li className="text-xs text-[#8f7a88]">
                        Click or drop fields from the palette to build the card.
                      </li>
                    )}
                  </ul>
                </div>
              </div>
            )}
          </section>

          <aside className="space-y-4">
            <div className="border border-[#3d2a38] bg-[#0f1a16]/70 p-4">
              <p className="text-xs uppercase tracking-wide text-[#8f7a88]">
                Field properties
              </p>
              {selectedField ? (
                <>
                  <p className="mt-3 font-mono text-[#c9a9c0]">{selectedField.name}</p>
                  <DesignerFieldInspector
                    field={selectedField}
                    widgetOptions={inspectorWidgets}
                    widgetAdvanced={widgetAdvanced}
                    onWidgetAdvancedChange={setWidgetAdvanced}
                    onChange={updateSelectedField}
                  />
                </>
              ) : (
                <p className="mt-3 text-xs text-[#8f7a88]">
                  Select a field on the canvas to edit properties.
                </p>
              )}
            </div>

            <div className="border border-[#3d2a38] bg-[#0f1a16]/70 p-4">
              <p className="text-xs uppercase tracking-wide text-[#8f7a88]">
                XPath inherit editor
              </p>
              <div className="mt-3 space-y-2 text-sm">
                <label className="block text-xs text-[#a8909e]">
                  expr
                  <input
                    value={xpathExpr}
                    onChange={(e) => setXpathExpr(e.target.value)}
                    className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 font-mono text-xs"
                  />
                </label>
                <label className="block text-xs text-[#a8909e]">
                  position
                  <select
                    value={xpathPosition}
                    onChange={(e) =>
                      setXpathPosition(
                        e.target.value as
                          | "inside"
                          | "after"
                          | "before"
                          | "replace"
                          | "attributes",
                      )
                    }
                    className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-xs"
                  >
                    <option value="inside">inside</option>
                    <option value="after">after</option>
                    <option value="before">before</option>
                    <option value="replace">replace</option>
                    <option value="attributes">attributes</option>
                  </select>
                </label>
                <label className="block text-xs text-[#a8909e]">
                  body_xml
                  <textarea
                    value={xpathBody}
                    onChange={(e) => setXpathBody(e.target.value)}
                    rows={4}
                    className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 font-mono text-xs"
                  />
                </label>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void runXpathPreview()}
                    className="border border-[#c9a9c0] px-2 py-1 text-xs text-[#c9a9c0] disabled:opacity-40"
                  >
                    Preview
                  </button>
                  <button
                    type="button"
                    disabled={!xpathArchPreview}
                    onClick={() => {
                      setArch(xpathArchPreview);
                      setArchOverride(xpathArchPreview);
                      setNotice("Arch override set from XPath preview. Save will use inherit arch.");
                    }}
                    className="border border-[#3d2a38] px-2 py-1 text-xs text-[#d4c4ce] disabled:opacity-40"
                  >
                    Use as arch override
                  </button>
                  <button
                    type="button"
                    disabled={busy || !model || !xpathArchPreview}
                    onClick={() =>
                      void onSave({ arch: xpathArchPreview, strategy: "inherit" })
                    }
                    className="border border-[#c9a9c0] px-2 py-1 text-xs text-[#c9a9c0] disabled:opacity-40"
                  >
                    Save xpath inherit
                  </button>
                  {archOverride && (
                    <button
                      type="button"
                      onClick={() => {
                        setArchOverride(null);
                        setNotice("Cleared arch override — Save uses canvas spec again.");
                      }}
                      className="border border-[#f0a8a0] px-2 py-1 text-xs text-[#f0a8a0]"
                    >
                      Clear override
                    </button>
                  )}
                </div>
                {xpathIssues.length > 0 && (
                  <ul className="space-y-1 text-xs text-[#f0a8a0]">
                    {xpathIssues.map((issue, i) => (
                      <li key={i}>• {issue}</li>
                    ))}
                  </ul>
                )}
                {xpathArchPreview && (
                  <pre className="max-h-32 overflow-auto text-xs text-[#d4c4ce]">
                    {xpathArchPreview}
                  </pre>
                )}
              </div>
            </div>

            <div className="border border-[#3d2a38] bg-[#0c090b] p-4">
              <p className="text-xs uppercase tracking-wide text-[#8f7a88]">
                Generated arch
              </p>
              <pre className="mt-3 max-h-48 overflow-auto text-xs text-[#d4c4ce]">
                {arch || "—"}
              </pre>
            </div>

            <div className="border border-[#3d2a38] bg-[#0f1a16]/70 p-4">
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs uppercase tracking-wide text-[#8f7a88]">
                  Snapshots / undo
                </p>
                <button
                  type="button"
                  className="text-xs text-[#c9a9c0] hover:underline"
                  onClick={() => refreshSnapshots()}
                >
                  Refresh
                </button>
              </div>
              <ul className="mt-3 max-h-48 space-y-2 overflow-auto text-xs">
                {snapshots.length === 0 && (
                  <li className="text-[#8f7a88]">No view snapshots yet.</li>
                )}
                {snapshots.map((s) => (
                  <li
                    key={s.id}
                    className="flex items-start justify-between gap-2 border border-[#1e2f29] px-2 py-1.5"
                  >
                    <div>
                      <p className="text-[#faf6f9]">{s.label}</p>
                      <p className="text-[#8f7a88]">
                        {s.reversible} · {s.created_at}
                      </p>
                    </div>
                    <button
                      type="button"
                      disabled={busy || s.reversible === "no"}
                      onClick={() => onRollback(s.id)}
                      className="shrink-0 border border-[#c9a9c0] px-2 py-0.5 text-[#c9a9c0] disabled:opacity-40"
                    >
                      Undo
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </aside>
        </div>
      </div>
      <ConfirmDialog
        open={confirmOverwriteOpen}
        title="Overwrite primary view"
        warning={`Mutate the live primary arch for ${model || "this model"} (not an inherit child). Prefer Inherit for stock models.`}
        risks={[
          "Can break stock xpath inherits (e.g. Contacts)",
          "Module upgrades may conflict",
          "Snapshot is taken — Undo from the sidebar when reversible",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setConfirmOverwriteOpen(false)}
        onConfirm={(phrase) =>
          void onSave({ strategy: "overwrite", confirm_phrase: phrase })
        }
      />
      <ConfirmDialog
        open={confirmMutateOpen}
        title="Mutate parent view arch"
        warning="Mutating parent view arch overwrites existing module XML. Prefer inherit (default) for interop with installed modules."
        risks={[
          "Parent ir.ui.view arch is rewritten in place",
          "Module upgrades may conflict or overwrite your change",
          "Harder to uninstall cleanly than an extension view",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setConfirmMutateOpen(false)}
        onConfirm={(phrase) =>
          void createNewFieldWithInject({
            confirm_advanced: true,
            confirm_phrase: phrase,
          })
        }
      />
    </main>
  );
}
