"use client";

import type { Dispatch, SetStateAction } from "react";
import type { FieldRow } from "@/lib/api";
import {
  uid,
  type AxisDesignerField,
  type DesignerField,
  type ViewType,
} from "@/components/designer/designer-model";

export type DesignerReportingFieldsPanelProps = {
  viewType: ViewType;
  model: string;
  fields: FieldRow[];
  calendarFields: DesignerField[];
  setCalendarFields: Dispatch<SetStateAction<DesignerField[]>>;
  mapFields: DesignerField[];
  setMapFields: Dispatch<SetStateAction<DesignerField[]>>;
  activityFields: DesignerField[];
  setActivityFields: Dispatch<SetStateAction<DesignerField[]>>;
  ganttFields: DesignerField[];
  setGanttFields: Dispatch<SetStateAction<DesignerField[]>>;
  gridFields: DesignerField[];
  setGridFields: Dispatch<SetStateAction<DesignerField[]>>;
  graphFields: AxisDesignerField[];
  setGraphFields: Dispatch<SetStateAction<AxisDesignerField[]>>;
  pivotFields: AxisDesignerField[];
  setPivotFields: Dispatch<SetStateAction<AxisDesignerField[]>>;
};

const REPORTING_VIEW_TYPES: ViewType[] = [
  "calendar",
  "graph",
  "pivot",
  "map",
  "activity",
  "gantt",
  "cohort",
  "grid",
];

export function DesignerReportingFieldsPanel({
  viewType,
  model,
  fields,
  calendarFields,
  setCalendarFields,
  mapFields,
  setMapFields,
  activityFields,
  setActivityFields,
  ganttFields,
  setGanttFields,
  gridFields,
  setGridFields,
  graphFields,
  setGraphFields,
  pivotFields,
  setPivotFields,
}: DesignerReportingFieldsPanelProps) {
  if (!REPORTING_VIEW_TYPES.includes(viewType) || !model) {
    return null;
  }

  return (
        <div className="mt-6 border border-border-subtle bg-surface-muted p-4">
          <h2 className="mb-2 text-sm font-semibold text-ink">
            {viewType} view fields
          </h2>
          <p className="mb-3 text-xs text-muted">
            Arch preview updates from these fields. Drag from the palette into
            form/list is unchanged — use the buttons below for reporting axes.
          </p>
          {viewType === "map" && (
            <p className="mb-3 border border-warning/40 bg-warning-subtle px-3 py-2 text-xs text-warning">
              Map views need a <code className="text-muted">res.partner</code>{" "}
              many2one (<code className="text-muted">res_partner</code> attr).
              Without a partner field, Odoo will not render the map.
            </p>
          )}
          {viewType === "gantt" && (
            <p className="mb-3 border border-warning/40 bg-warning-subtle px-3 py-2 text-xs text-warning">
              Gantt arch is Community-safe metadata, but the client often needs{" "}
              <code className="text-muted">web_gantt</code> /{" "}
              <code className="text-muted">project</code> (Enterprise or installed
              modules). We do not claim EE live — save may succeed while Open in Odoo
              shows nothing without the module.
            </p>
          )}
          {viewType === "cohort" && (
            <p className="mb-3 border border-warning/40 bg-warning-subtle px-3 py-2 text-xs text-warning">
              Cohort views are module/version gated. Arch can be saved via public RPC;
              the UI may be unavailable without the cohort client module. Not an EE
              live claim.
            </p>
          )}
          {viewType === "grid" && (
            <p className="mb-3 border border-warning/40 bg-warning-subtle px-3 py-2 text-xs text-warning">
              Grid/planning views are Enterprise-gated. Arch emission is supported; live
              Open in Odoo requires EE modules on the instance.
            </p>
          )}
          {viewType === "calendar" && (
            <ul className="space-y-1 font-mono text-sm text-muted">
              {calendarFields.map((f) => (
                <li key={f.id} className="flex items-center justify-between gap-2">
                  <span>{f.name}</span>
                  <button
                    type="button"
                    className="text-xs text-danger"
                    onClick={() =>
                      setCalendarFields((cols) => cols.filter((c) => c.id !== f.id))
                    }
                  >
                    Remove
                  </button>
                </li>
              ))}
              {!calendarFields.length && (
                <li className="text-muted">No display fields yet</li>
              )}
            </ul>
          )}
          {(viewType === "map" ||
            viewType === "activity" ||
            viewType === "gantt" ||
            viewType === "grid") && (
            <ul className="space-y-1 font-mono text-sm text-muted">
              {(viewType === "map"
                ? mapFields
                : viewType === "activity"
                  ? activityFields
                  : viewType === "gantt"
                    ? ganttFields
                    : gridFields
              ).map((f) => (
                <li key={f.id} className="flex items-center justify-between gap-2">
                  <span>{f.name}</span>
                  <button
                    type="button"
                    className="text-xs text-danger"
                    onClick={() => {
                      if (viewType === "map") {
                        setMapFields((cols) => cols.filter((c) => c.id !== f.id));
                      } else if (viewType === "activity") {
                        setActivityFields((cols) => cols.filter((c) => c.id !== f.id));
                      } else if (viewType === "gantt") {
                        setGanttFields((cols) => cols.filter((c) => c.id !== f.id));
                      } else {
                        setGridFields((cols) => cols.filter((c) => c.id !== f.id));
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
                  : viewType === "gantt"
                    ? ganttFields
                    : gridFields
              ).length === 0 && (
                <li className="text-muted">No display fields yet</li>
              )}
            </ul>
          )}
          {viewType === "cohort" && (
            <p className="text-xs text-muted">
              Cohort uses date_start / measure from the toolbar — no field list required.
            </p>
          )}
          {viewType === "graph" && (
            <ul className="space-y-2 font-mono text-sm text-muted">
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
                    className="border border-border-subtle bg-surface px-2 py-1 text-xs"
                  >
                    <option value="">(role)</option>
                    <option value="row">row</option>
                    <option value="measure">measure</option>
                  </select>
                  <button
                    type="button"
                    className="text-xs text-danger"
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
            <ul className="space-y-2 font-mono text-sm text-muted">
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
                    className="border border-border-subtle bg-surface px-2 py-1 text-xs"
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
                      className="w-24 border border-border-subtle bg-surface px-2 py-1 text-xs"
                    />
                  )}
                  <button
                    type="button"
                    className="text-xs text-danger"
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
            <p className="text-[11px] text-muted">
              Click <span className="font-mono text-muted">+ field</span> to include an
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
                className="border border-border-subtle px-2 py-0.5 font-mono text-[11px] text-muted"
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
                  } else if (viewType === "grid") {
                    setGridFields((cols) =>
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

  );
}
