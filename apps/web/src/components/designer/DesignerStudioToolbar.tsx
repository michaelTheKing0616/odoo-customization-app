"use client";

import type { Dispatch, SetStateAction } from "react";
import { Card } from "@/components/ui/layout-primitives";
import type { Connection, FieldRow } from "@/lib/api";
import {
  connectionSupports,
  gridViewAllowed,
  isEnterpriseEdition,
  mutationAllowed,
  mutationBlockedReason,
} from "@/lib/capabilities";
import type {
  AxisDesignerField,
  ViewType,
} from "@/components/designer/designer-model";
import type { SelectedField } from "@/components/designer/designer-model";

export type DesignerStudioToolbarProps = {
  model: string;
  setModel: (v: string) => void;
  ensureFieldsForModel: (model: string) => void | Promise<void>;
  loadModelFields: (model: string) => void | Promise<void>;
  loadExistingView: () => void | Promise<void>;
  viewType: ViewType;
  setViewType: (v: ViewType) => void;
  title: string;
  setTitle: (v: string) => void;
  busy: boolean;
  onSave: () => void | Promise<void>;
  saveStrategy: "inherit" | "overwrite";
  setSaveStrategy: (v: "inherit" | "overwrite") => void;
  setConfirmUnlinkInheritOpen: (v: boolean) => void;
  loadedViewId: number | null;
  setConfirmRepairChromeOpen?: (v: boolean) => void;
  setRepairDuplicateChromeOpen?: (v: boolean) => void;
  connection: Connection | null;
  connectionId: string;
  api: {
    polishForm: (
      connectionId: string,
      model: string,
      title: string,
    ) => Promise<{ applied: boolean; detail?: unknown }>;
  };
  setNotice: (v: string | null) => void;
  setError: (v: string | null) => void;
  setBusy: (v: boolean) => void;
  setSelected: Dispatch<SetStateAction<SelectedField | null>>;
  kanbanGroupBy: string;
  setKanbanGroupBy: (v: string) => void;
  fields: FieldRow[];
  dateFieldsForSelect: FieldRow[];
  calendarDateStart: string;
  setCalendarDateStart: (v: string) => void;
  calendarDateStop: string;
  setCalendarDateStop: (v: string) => void;
  calendarColor: string;
  setCalendarColor: (v: string) => void;
  calendarMode: string;
  setCalendarMode: (v: string) => void;
  viewSample: boolean;
  setViewSample: (v: boolean) => void;
  graphType: "bar" | "line" | "pie";
  setGraphType: (v: "bar" | "line" | "pie") => void;
  mapResPartner: string;
  setMapResPartner: (v: string) => void;
  mapRouting: boolean;
  setMapRouting: (v: boolean) => void;
  ganttDateStart: string;
  setGanttDateStart: (v: string) => void;
  ganttDateStop: string;
  setGanttDateStop: (v: string) => void;
  ganttGroupBy: string;
  setGanttGroupBy: (v: string) => void;
  ganttColor: string;
  setGanttColor: (v: string) => void;
  ganttProgress: string;
  setGanttProgress: (v: string) => void;
  ganttDefaultScale: string;
  setGanttDefaultScale: (v: string) => void;
  ganttDependencyField: string;
  setGanttDependencyField: (v: string) => void;
  cohortDateStart: string;
  setCohortDateStart: (v: string) => void;
  cohortDateStop: string;
  setCohortDateStop: (v: string) => void;
  cohortInterval: "day" | "week" | "month" | "year" | "";
  setCohortInterval: (v: "day" | "week" | "month" | "year" | "") => void;
  cohortMode: "retention" | "churn" | "";
  setCohortMode: (v: "retention" | "churn" | "") => void;
  cohortTimeline: "forward" | "backward" | "";
  setCohortTimeline: (v: "forward" | "backward" | "") => void;
  cohortMeasure: string;
  setCohortMeasure: (v: string) => void;
  gridRowField: string;
  setGridRowField: (v: string) => void;
  gridColField: string;
  setGridColField: (v: string) => void;
  gridMeasure: string;
  setGridMeasure: (v: string) => void;
  gridAdjustment: string;
  setGridAdjustment: (v: string) => void;
  gridDateStart: string;
  setGridDateStart: (v: string) => void;
  gridDateStop: string;
  setGridDateStop: (v: string) => void;
  fieldsModel: string;
  archOverride: string | null;
  pendingCoalesceRef: { current: string | undefined };
  pendingHistoryLabelRef: { current: string | undefined };
  onRepairDuplicateChrome: () => void | Promise<void>;
};


export function DesignerStudioToolbar(p: DesignerStudioToolbarProps) {
  const {
    model, setModel, ensureFieldsForModel, loadModelFields, loadExistingView,
    viewType, setViewType, title, setTitle, busy, onSave,
    saveStrategy, setSaveStrategy, setConfirmUnlinkInheritOpen, loadedViewId,
    connection, connectionId, api, setNotice, setError, setBusy, setSelected,
    kanbanGroupBy, setKanbanGroupBy, fields, dateFieldsForSelect,
    calendarDateStart, setCalendarDateStart, calendarDateStop, setCalendarDateStop,
    calendarColor, setCalendarColor, calendarMode, setCalendarMode,
    viewSample, setViewSample, graphType, setGraphType,
    mapResPartner, setMapResPartner, mapRouting, setMapRouting,
    ganttDateStart, setGanttDateStart, ganttDateStop, setGanttDateStop,
    ganttGroupBy, setGanttGroupBy, ganttColor, setGanttColor, ganttProgress, setGanttProgress,
    ganttDefaultScale, setGanttDefaultScale, ganttDependencyField, setGanttDependencyField,
    cohortDateStart, setCohortDateStart, cohortDateStop, setCohortDateStop,
    cohortInterval, setCohortInterval, cohortMode, setCohortMode,
    cohortTimeline, setCohortTimeline, cohortMeasure, setCohortMeasure,
    gridRowField, setGridRowField, gridColField, setGridColField, gridMeasure, setGridMeasure,
    gridAdjustment, setGridAdjustment, gridDateStart, setGridDateStart, gridDateStop, setGridDateStop,
    fieldsModel,
    archOverride,
    pendingCoalesceRef,
    pendingHistoryLabelRef,
    onRepairDuplicateChrome,
  } = p;


  return (
    <Card className="flex flex-wrap items-end gap-3 p-3" data-testid="designer-studio-toolbar">
      <label className="text-sm">
        <span className="text-muted">Model</span>
        <input
          value={model}
          onChange={(e) => setModel(e.target.value)}
          onBlur={() => {
            if (model.trim()) void ensureFieldsForModel(model);
          }}
          className="mt-1 block w-64 border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
          placeholder="x_ticket"
        />
      </label>
      <button
        type="button"
        onClick={() => model && loadModelFields(model)}
        className="h-10 border border-border-subtle px-4 text-sm text-muted"
      >
        Load fields
      </button>
      <button
        type="button"
        disabled={busy || !model}
        onClick={loadExistingView}
        className="h-10 border border-border-subtle px-4 text-sm text-muted disabled:opacity-60"
      >
        Load existing view
      </button>
      <label className="text-sm">
        <span className="text-muted">View type</span>
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
                next === "grid" ||
                next === "activity" ||
                next === "map")
            ) {
              void ensureFieldsForModel(model);
            }
          }}
          className="mt-1 block border border-border-subtle bg-surface px-3 py-2"
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
          <option value="grid" disabled={!gridViewAllowed(connection)}>
            grid
            {!gridViewAllowed(connection)
              ? !isEnterpriseEdition(connection?.capabilities)
                ? " (Enterprise edition)"
                : " (probe connection)"
              : ""}
          </option>
        </select>
        {!mutationAllowed(connection) && (
          <p className="mt-1 text-xs text-warning">
            {mutationBlockedReason(connection) ??
              "Reporting views need a probed connection."}
          </p>
        )}
      </label>
      {viewType === "kanban" && (
        <label className="text-sm">
          <span className="text-muted">Column field</span>
          <select
            value={kanbanGroupBy}
            onChange={(e) => setKanbanGroupBy(e.target.value)}
            className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
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
      {(viewType === "calendar" ||
        viewType === "graph" ||
        viewType === "pivot" ||
        viewType === "map" ||
        viewType === "activity" ||
        viewType === "gantt" ||
        viewType === "cohort" ||
        viewType === "grid") && (
        <details
          className="w-full rounded-md border border-border-subtle bg-surface px-3 py-2"
          data-testid="designer-view-axes"
          open
        >
          <summary className="cursor-pointer text-sm font-medium text-ink">
            View axes
          </summary>
          <div className="mt-2 flex flex-wrap items-end gap-3">
      {viewType === "calendar" && (
        <>
          <label className="text-sm">
            <span className="text-muted">date_start</span>
            <select
              value={calendarDateStart}
              onChange={(e) => setCalendarDateStart(e.target.value)}
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
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
              <p className="mt-1 text-xs text-warning">
                Fields loaded for {fieldsModel || "(none)"} — click Load fields for{" "}
                {model || "this model"}.
              </p>
            )}
            {!dateFieldsForSelect.length && (
              <p className="mt-1 text-xs text-warning">
                No date/datetime fields on loaded model. Set model to x_lib_loan and click
                Load fields.
              </p>
            )}
          </label>
          <label className="text-sm">
            <span className="text-muted">date_stop</span>
            <select
              value={calendarDateStop}
              onChange={(e) => setCalendarDateStop(e.target.value)}
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
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
            <span className="text-muted">color</span>
            <select
              value={calendarColor}
              onChange={(e) => setCalendarColor(e.target.value)}
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
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
            <span className="text-muted">mode</span>
            <select
              value={calendarMode}
              onChange={(e) => setCalendarMode(e.target.value)}
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 text-sm"
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
          <span className="text-muted">Graph type</span>
          <select
            value={graphType}
            onChange={(e) =>
              setGraphType(e.target.value as "bar" | "line" | "pie")
            }
            className="mt-1 block border border-border-subtle bg-surface px-3 py-2 text-sm"
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
        <>
        <label className="text-sm">
          <span className="text-muted">res_partner</span>
          <select
            value={mapResPartner}
            onChange={(e) => setMapResPartner(e.target.value)}
            className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
            data-testid="designer-map-res-partner"
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
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={mapRouting}
            onChange={(e) => setMapRouting(e.target.checked)}
            data-testid="designer-map-routing"
          />
          routing (directions)
        </label>
        </>
      )}
      {viewType === "gantt" && (
        <>
          <label className="text-sm">
            <span className="text-muted">date_start</span>
            <select
              value={ganttDateStart}
              onChange={(e) => setGanttDateStart(e.target.value)}
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
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
            <span className="text-muted">date_stop</span>
            <select
              value={ganttDateStop}
              onChange={(e) => setGanttDateStop(e.target.value)}
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
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
            <span className="text-muted">default_group_by</span>
            <select
              value={ganttGroupBy}
              onChange={(e) => setGanttGroupBy(e.target.value)}
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
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
            <span className="text-muted">color</span>
            <select
              value={ganttColor}
              onChange={(e) => setGanttColor(e.target.value)}
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
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
            <span className="text-muted">progress</span>
            <select
              value={ganttProgress}
              onChange={(e) => setGanttProgress(e.target.value)}
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
              data-testid="designer-gantt-progress"
            >
              <option value="">(optional)</option>
              {fields.map((f) => (
                <option key={f.id} value={f.name}>
                  {f.name} · {f.ttype}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="text-muted">default_scale</span>
            <select
              value={ganttDefaultScale}
              onChange={(e) => setGanttDefaultScale(e.target.value)}
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 text-sm"
              data-testid="designer-gantt-default-scale"
            >
              <option value="">(optional)</option>
              <option value="day">day</option>
              <option value="week">week</option>
              <option value="month">month</option>
              <option value="year">year</option>
            </select>
          </label>
          <label className="text-sm">
            <span className="text-muted">dependency_field</span>
            <select
              value={ganttDependencyField}
              onChange={(e) => setGanttDependencyField(e.target.value)}
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
              data-testid="designer-gantt-dependency"
            >
              <option value="">(optional)</option>
              {fields
                .filter((f) => f.ttype === "many2many" || f.ttype === "one2many")
                .map((f) => (
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
            <span className="text-muted">date_start</span>
            <select
              value={cohortDateStart}
              onChange={(e) => setCohortDateStart(e.target.value)}
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
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
            <span className="text-muted">date_stop</span>
            <select
              value={cohortDateStop}
              onChange={(e) => setCohortDateStop(e.target.value)}
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
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
            <span className="text-muted">interval</span>
            <select
              value={cohortInterval}
              onChange={(e) =>
                setCohortInterval(
                  e.target.value as "day" | "week" | "month" | "year" | "",
                )
              }
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 text-sm"
            >
              <option value="day">day</option>
              <option value="week">week</option>
              <option value="month">month</option>
              <option value="year">year</option>
            </select>
          </label>
          <label className="text-sm">
            <span className="text-muted">mode</span>
            <select
              value={cohortMode}
              onChange={(e) =>
                setCohortMode(e.target.value as "retention" | "churn" | "")
              }
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 text-sm"
              data-testid="designer-cohort-mode"
            >
              <option value="retention">retention</option>
              <option value="churn">churn</option>
            </select>
          </label>
          <label className="text-sm">
            <span className="text-muted">timeline</span>
            <select
              value={cohortTimeline}
              onChange={(e) =>
                setCohortTimeline(e.target.value as "forward" | "backward" | "")
              }
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 text-sm"
            >
              <option value="">(default)</option>
              <option value="forward">forward</option>
              <option value="backward">backward</option>
            </select>
          </label>
          <label className="text-sm">
            <span className="text-muted">measure</span>
            <select
              value={cohortMeasure}
              onChange={(e) => setCohortMeasure(e.target.value)}
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
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
      {viewType === "grid" && (
        <>
          <label className="text-sm">
            <span className="text-muted">row_field</span>
            <select
              value={gridRowField}
              onChange={(e) => setGridRowField(e.target.value)}
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
              data-testid="designer-grid-row-field"
            >
              <option value="">(optional)</option>
              {fields.map((f) => (
                <option key={f.id} value={f.name}>
                  {f.name} · {f.ttype}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="text-muted">col_field</span>
            <select
              value={gridColField}
              onChange={(e) => setGridColField(e.target.value)}
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
              data-testid="designer-grid-col-field"
            >
              <option value="">(optional)</option>
              {dateFieldsForSelect.map((f) => (
                <option key={f.id} value={f.name}>
                  {f.name} · {f.ttype}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="text-muted">measure</span>
            <select
              value={gridMeasure}
              onChange={(e) => setGridMeasure(e.target.value)}
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
              data-testid="designer-grid-measure"
            >
              <option value="">(optional)</option>
              {fields
                .filter(
                  (f) =>
                    f.ttype === "integer" ||
                    f.ttype === "float" ||
                    f.ttype === "monetary",
                )
                .map((f) => (
                  <option key={f.id} value={f.name}>
                    {f.name} · {f.ttype}
                  </option>
                ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="text-muted">adjustment</span>
            <select
              value={gridAdjustment}
              onChange={(e) => setGridAdjustment(e.target.value)}
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 text-sm"
              data-testid="designer-grid-adjustment"
            >
              <option value="">(optional)</option>
              <option value="increment">increment</option>
              <option value="value">value</option>
            </select>
          </label>
          <label className="text-sm">
            <span className="text-muted">date_start</span>
            <select
              value={gridDateStart}
              onChange={(e) => setGridDateStart(e.target.value)}
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
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
            <span className="text-muted">date_stop</span>
            <select
              value={gridDateStop}
              onChange={(e) => setGridDateStop(e.target.value)}
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
            >
              <option value="">(optional)</option>
              {dateFieldsForSelect.map((f) => (
                <option key={f.id} value={f.name}>
                  {f.name}
                </option>
              ))}
            </select>
          </label>
        </>
      )}
          </div>
        </details>
      )}
      <label className="text-sm">
        <span className="text-muted">Title</span>
        <input
          value={title}
          onChange={(e) => {
            pendingCoalesceRef.current = "title";
            pendingHistoryLabelRef.current = "Edit title";
            setTitle(e.target.value);
          }}
          className="mt-1 block w-48 border border-border-subtle bg-surface px-3 py-2"
        />
      </label>
      <label className="text-sm">
        <span className="text-muted">Save strategy</span>
        <select
          value={saveStrategy}
          onChange={(e) => setSaveStrategy(e.target.value as "inherit" | "overwrite")}
          className="mt-1 block w-40 border border-border-subtle bg-surface px-2 py-2 text-sm"
        >
          <option value="inherit">Inherit (safe)</option>
          <option value="overwrite">Overwrite primary</option>
        </select>
      </label>
      <button
        type="button"
        disabled={busy || !model}
        onClick={() => void onSave()}
        className="h-10 bg-accent px-5 text-sm font-semibold text-on-accent disabled:opacity-60"
      >
        {busy ? "Saving…" : archOverride ? "Save arch override" : "Save to Odoo"}
      </button>
      {!model.startsWith("x_") && viewType === "form" ? (
        <>
          <button
            type="button"
            disabled={busy || !model}
            onClick={() => void onRepairDuplicateChrome()}
            className="h-10 border border-border-subtle px-4 text-sm text-muted disabled:opacity-40"
            data-testid="designer-fix-duplicate-chrome"
            title="Rewrites account.move.designer.form (etc.) from full form replace to additive x_* only"
          >
            Fix duplicate chrome
          </button>
          <button
            type="button"
            disabled={busy || !model}
            onClick={() => setConfirmUnlinkInheritOpen(true)}
            className="h-10 border border-danger/50 px-4 text-sm text-danger disabled:opacity-40"
            data-testid="designer-unlink-inherit"
            title="Deletes {model}.designer.form inherit — restores stock toolbar/tabs"
          >
            Unlink designer inherit
          </button>
        </>
      ) : null}
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
        className="h-10 border border-border-subtle px-4 text-sm text-muted disabled:opacity-40"
      >
        Polish form layout
      </button>
    </Card>
  );
}
