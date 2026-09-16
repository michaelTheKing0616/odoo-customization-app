/**
 * Load an existing Odoo view into Designer canvas state.
 * Extracted from designer/page.tsx (strangler).
 */
import type { FieldRow, ViewRow } from "@/lib/api";
import { semanticInjectExpr } from "@/lib/xpathLocator";
import {
  asSpecBool,
  mapFormGroupChildren,
  mapParsedButton,
  uid,
  type AxisDesignerField,
  type DesignerButton,
  type DesignerField,
  type FormChild,
  type SearchFilter,
  type SearchGroupByFilter,
  type SelectedField,
  type ViewType,
} from "@/components/designer/designer-model";

export type LoadExistingViewApi = {
  listFields: (id: string, model: string) => Promise<FieldRow[]>;
  listViews: (id: string, model: string) => Promise<ViewRow[]>;
  getView: (id: string, viewId: number) => Promise<ViewRow>;
  parseViewArch: (
    id: string,
    view_type: string,
    arch: string,
  ) => Promise<{ view_type: string; spec: Record<string, unknown> }>;
};

export type LoadExistingViewDeps = {
  model: string;
  viewType: ViewType;
  connectionId: string;
  api: LoadExistingViewApi;
  historySkipRef: { current: "reset" | "apply" | null };
  applyFieldNamesToCanvas: (names: string[], rows: FieldRow[]) => void;
  setBusy: (v: boolean) => void;
  setError: (v: string | null) => void;
  setNotice: (v: string | null) => void;
  setFields: (rows: FieldRow[]) => void;
  setFieldsModel: (m: string) => void;
  setLoadedViewId: (id: number | null) => void;
  setArch: (arch: string) => void;
  setXpathExpr: (v: string | ((prev: string) => string)) => void;
  setTitle: (t: string) => void;
  setSelected: (v: SelectedField | null) => void;
  setFormChildren: (v: FormChild[]) => void;
  setHeaderButtons: (v: DesignerButton[]) => void;
  setButtonBox: (v: DesignerButton[]) => void;
  setStatusbarField: (v: string) => void;
  setStatusbarVisible: (v: string) => void;
  setFormCanCreate: (v: boolean) => void;
  setFormCanEdit: (v: boolean) => void;
  setFormCanDelete: (v: boolean) => void;
  setFormCanDuplicate: (v: boolean) => void;
  setListColumns: (v: DesignerField[]) => void;
  setListDecorationDanger: (v: string) => void;
  setListDecorationInfo: (v: string) => void;
  setListDecorationMuted: (v: string) => void;
  setListCanCreate: (v: boolean) => void;
  setListCanEdit: (v: boolean) => void;
  setListCanDelete: (v: boolean) => void;
  setListMultiEdit: (v: boolean) => void;
  setListDefaultOrder: (v: string) => void;
  setViewSample: (v: boolean) => void;
  setSearchFields: (v: DesignerField[]) => void;
  setSearchFilters: (v: SearchFilter[]) => void;
  setSearchGroupByFilters: (v: SearchGroupByFilter[]) => void;
  setKanbanFields: (v: DesignerField[]) => void;
  setKanbanGroupBy: (v: string) => void;
  setKanbanCanCreate: (v: boolean) => void;
  setKanbanQuickCreate: (v: boolean) => void;
  setCalendarDateStart: (v: string) => void;
  setCalendarDateStop: (v: string) => void;
  setCalendarColor: (v: string) => void;
  setCalendarMode: (v: string) => void;
  setCalendarFields: (v: DesignerField[]) => void;
  setGraphType: (v: "bar" | "line" | "pie") => void;
  setGraphFields: (v: AxisDesignerField[]) => void;
  setPivotFields: (v: AxisDesignerField[]) => void;
  setMapResPartner: (v: string) => void;
  setMapRouting: (v: boolean) => void;
  setMapFields: (v: DesignerField[]) => void;
  setActivityFields: (v: DesignerField[]) => void;
  setGanttDateStart: (v: string) => void;
  setGanttDateStop: (v: string) => void;
  setGanttGroupBy: (v: string) => void;
  setGanttColor: (v: string) => void;
  setGanttProgress: (v: string) => void;
  setGanttDefaultScale: (v: string) => void;
  setGanttDependencyField: (v: string) => void;
  setGanttFields: (v: DesignerField[]) => void;
  setCohortDateStart: (v: string) => void;
  setCohortDateStop: (v: string) => void;
  setCohortInterval: (v: "day" | "week" | "month" | "year" | "") => void;
  setCohortMode: (v: "retention" | "churn" | "") => void;
  setCohortTimeline: (v: "forward" | "backward" | "") => void;
  setCohortMeasure: (v: string) => void;
  setGridRowField: (v: string) => void;
  setGridColField: (v: string) => void;
  setGridMeasure: (v: string) => void;
  setGridAdjustment: (v: string) => void;
  setGridDateStart: (v: string) => void;
  setGridDateStop: (v: string) => void;
  setGridFields: (v: DesignerField[]) => void;
};

export async function loadExistingView(deps: LoadExistingViewDeps): Promise<void> {
  const {
    model,
    viewType,
    connectionId,
    api,
    historySkipRef,
    applyFieldNamesToCanvas,
    setBusy,
    setError,
    setNotice,
    setFields,
    setFieldsModel,
    setLoadedViewId,
    setArch,
    setXpathExpr,
    setTitle,
    setSelected,
    setFormChildren,
    setHeaderButtons,
    setButtonBox,
    setStatusbarField,
    setStatusbarVisible,
    setFormCanCreate,
    setFormCanEdit,
    setFormCanDelete,
    setFormCanDuplicate,
    setListColumns,
    setListDecorationDanger,
    setListDecorationInfo,
    setListDecorationMuted,
    setListCanCreate,
    setListCanEdit,
    setListCanDelete,
    setListMultiEdit,
    setListDefaultOrder,
    setViewSample,
    setSearchFields,
    setSearchFilters,
    setSearchGroupByFilters,
    setKanbanFields,
    setKanbanGroupBy,
    setKanbanCanCreate,
    setKanbanQuickCreate,
    setCalendarDateStart,
    setCalendarDateStop,
    setCalendarColor,
    setCalendarMode,
    setCalendarFields,
    setGraphType,
    setGraphFields,
    setPivotFields,
    setMapResPartner,
    setMapRouting,
    setMapFields,
    setActivityFields,
    setGanttDateStart,
    setGanttDateStop,
    setGanttGroupBy,
    setGanttColor,
    setGanttProgress,
    setGanttDefaultScale,
    setGanttDependencyField,
    setGanttFields,
    setCohortDateStart,
    setCohortDateStop,
    setCohortInterval,
    setCohortMode,
    setCohortTimeline,
    setCohortMeasure,
    setGridRowField,
    setGridColField,
    setGridMeasure,
    setGridAdjustment,
    setGridDateStart,
    setGridDateStop,
    setGridFields,
  } = deps;

  if (!model) {
    setError("Enter a model first");
    return;
  }
  setBusy(true);
  setError(null);
  setNotice(null);
  historySkipRef.current = "reset";
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
    setXpathExpr((prev) =>
      prev === "//sheet" || prev === "//form" || prev === "//list"
        ? semanticInjectExpr(full.arch ?? null, viewType)
        : prev,
    );
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
                  children: mapFormGroupChildren(
                    ((p.children as Array<Record<string, unknown>> | undefined) ??
                      []) as Array<Record<string, unknown>>,
                  ),
                })),
              };
            }
            const kids = (child.children as Array<Record<string, unknown>> | undefined) ?? [];
            return {
              kind: "group" as const,
              id: uid("g"),
              string: child.string ? String(child.string) : undefined,
              children: mapFormGroupChildren(kids),
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
          setMapRouting(asSpecBool(spec.routing) ?? false);
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
          setGanttDefaultScale(
            typeof spec.default_scale === "string" ? spec.default_scale : "",
          );
          setGanttDependencyField(
            typeof spec.dependency_field === "string" ? spec.dependency_field : "",
          );
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
        } else if (viewType === "grid") {
          setGridRowField(typeof spec.row_field === "string" ? spec.row_field : "");
          setGridColField(typeof spec.col_field === "string" ? spec.col_field : "");
          setGridMeasure(typeof spec.measure === "string" ? spec.measure : "");
          setGridAdjustment(typeof spec.adjustment === "string" ? spec.adjustment : "");
          setGridDateStart(typeof spec.date_start === "string" ? spec.date_start : "");
          setGridDateStop(typeof spec.date_stop === "string" ? spec.date_stop : "");
          setGridFields(
            ((spec.fields as Array<Record<string, unknown>> | undefined) ?? []).map((c) => ({
              kind: "field" as const,
              id: uid("f"),
              name: String(c.name || ""),
              string: c.string ? String(c.string) : undefined,
            })),
          );
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
    historySkipRef.current = null;
    setError(err instanceof Error ? err.message : "Load view failed");
  } finally {
    setBusy(false);
  }
}
