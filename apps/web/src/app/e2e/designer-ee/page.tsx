"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { gridViewAllowed } from "@/lib/capabilities";
import type { CapabilityMatrix, Connection } from "@/lib/api";

type EeViewType = "map" | "gantt" | "grid" | "cohort";

const FIELDS = [
  { name: "partner_id", ttype: "many2one", relation: "res.partner" },
  { name: "date_start", ttype: "datetime" },
  { name: "date_end", ttype: "datetime" },
  { name: "progress", ttype: "float" },
  { name: "depend_on_ids", ttype: "many2many" },
  { name: "user_id", ttype: "many2one" },
  { name: "amount", ttype: "monetary" },
  { name: "create_date", ttype: "datetime" },
];

function capsForEdition(edition: "community" | "enterprise"): CapabilityMatrix {
  return {
    major: 19,
    edition,
    server_version: edition === "enterprise" ? "19.0+e" : "19.0",
    ga: true,
    message: `Odoo 19 ${edition}`,
    supported: ["view_inject_inherit", "view_inject_mutate"],
    unsupported: [],
  };
}

/** E2E harness for EE view panel attrs (REM-8). */
export default function EeDesignerHarnessPage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const [edition, setEdition] = useState<"community" | "enterprise">("enterprise");
  const [viewType, setViewType] = useState<EeViewType>("map");
  const [arch, setArch] = useState("");
  const [lastSpec, setLastSpec] = useState<Record<string, unknown> | null>(null);

  const connection: Connection = useMemo(
    () => ({
      id: "e2e-ee-connection",
      name: "E2E EE",
      url: "http://127.0.0.1:8069",
      db_name: "odoo_dev",
      username: "admin",
      server_version: edition === "enterprise" ? "19.0+e" : "19.0",
      created_at: null,
      updated_at: null,
      capabilities: capsForEdition(edition),
    }),
    [edition],
  );

  const [mapResPartner, setMapResPartner] = useState("partner_id");
  const [mapRouting, setMapRouting] = useState(false);
  const [mapFields, setMapFields] = useState<string[]>(["amount"]);
  const [ganttDateStart, setGanttDateStart] = useState("date_start");
  const [ganttDefaultScale, setGanttDefaultScale] = useState("week");
  const [ganttDependency, setGanttDependency] = useState("");
  const [ganttProgress, setGanttProgress] = useState("progress");
  const [gridRowField, setGridRowField] = useState("user_id");
  const [gridColField, setGridColField] = useState("date_start");
  const [gridMeasure, setGridMeasure] = useState("amount");
  const [gridAdjustment, setGridAdjustment] = useState("increment");
  const [cohortMode, setCohortMode] = useState<"retention" | "churn">("retention");
  const [cohortDateStart, setCohortDateStart] = useState("create_date");

  const activeSpec = useMemo(() => {
    if (viewType === "map") {
      return {
        string: "Map",
        res_partner: mapResPartner,
        routing: mapRouting ? true : null,
        fields: mapFields.map((name) => ({ kind: "field", name })),
      };
    }
    if (viewType === "gantt") {
      return {
        string: "Gantt",
        date_start: ganttDateStart,
        default_scale: ganttDefaultScale || null,
        dependency_field: ganttDependency || null,
        progress: ganttProgress || null,
        fields: [],
      };
    }
    if (viewType === "grid") {
      return {
        string: "Grid",
        row_field: gridRowField || null,
        col_field: gridColField || null,
        measure: gridMeasure || null,
        adjustment: gridAdjustment || null,
        fields: [],
      };
    }
    return {
      string: "Cohort",
      date_start: cohortDateStart,
      mode: cohortMode,
      interval: "week",
    };
  }, [
    cohortDateStart,
    cohortMode,
    ganttDateStart,
    ganttDefaultScale,
    ganttDependency,
    ganttProgress,
    gridAdjustment,
    gridColField,
    gridMeasure,
    gridRowField,
    mapFields,
    mapResPartner,
    mapRouting,
    viewType,
  ]);

  const refresh = useCallback(async () => {
    const res = await api.previewViewArch(connection.id, viewType, activeSpec);
    setArch(res.arch);
    setLastSpec(activeSpec);
  }, [activeSpec, connection.id, viewType]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  const gridOk = gridViewAllowed(connection);

  return (
    <main className="mx-auto max-w-3xl space-y-4 p-6" data-testid="ee-designer-harness">
      <h1 className="text-lg font-semibold">EE view panel harness</h1>
      <label className="block text-sm">
        Edition
        <select
          value={edition}
          onChange={(e) => setEdition(e.target.value as "community" | "enterprise")}
          data-testid="ee-edition-select"
          className="mt-1 block border px-2 py-1"
        >
          <option value="community">community</option>
          <option value="enterprise">enterprise</option>
        </select>
      </label>
      <label className="block text-sm">
        View type
        <select
          value={viewType}
          onChange={(e) => setViewType(e.target.value as EeViewType)}
          data-testid="ee-view-type"
          className="mt-1 block border px-2 py-1"
        >
          <option value="map">map</option>
          <option value="gantt">gantt</option>
          <option value="grid" disabled={!gridOk}>
            grid{!gridOk ? " (Enterprise)" : ""}
          </option>
          <option value="cohort">cohort</option>
        </select>
      </label>

      {viewType === "map" && (
        <div data-testid="ee-map-panel" className="space-y-2">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={mapRouting}
              onChange={(e) => setMapRouting(e.target.checked)}
              data-testid="designer-map-routing"
            />
            routing
          </label>
          <fieldset className="space-y-1">
            <legend className="text-sm">Marker fields</legend>
            {FIELDS.map((f) => (
              <label key={f.name} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={mapFields.includes(f.name)}
                  onChange={(e) => {
                    setMapFields((prev) =>
                      e.target.checked
                        ? [...prev, f.name]
                        : prev.filter((n) => n !== f.name),
                    );
                  }}
                  data-testid={`designer-map-field-${f.name}`}
                />
                {f.name}
              </label>
            ))}
          </fieldset>
        </div>
      )}

      {viewType === "gantt" && (
        <div data-testid="ee-gantt-panel" className="space-y-2">
          <label className="block text-sm">
            default_scale
            <select
              value={ganttDefaultScale}
              onChange={(e) => setGanttDefaultScale(e.target.value)}
              data-testid="designer-gantt-default-scale"
              className="mt-1 block border px-2 py-1"
            >
              <option value="day">day</option>
              <option value="week">week</option>
              <option value="month">month</option>
            </select>
          </label>
          <label className="block text-sm">
            dependency_field
            <select
              value={ganttDependency}
              onChange={(e) => setGanttDependency(e.target.value)}
              data-testid="designer-gantt-dependency"
              className="mt-1 block border px-2 py-1"
            >
              <option value="">(none)</option>
              {FIELDS.filter((f) => f.ttype === "many2many").map((f) => (
                <option key={f.name} value={f.name}>
                  {f.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            progress
            <select
              value={ganttProgress}
              onChange={(e) => setGanttProgress(e.target.value)}
              data-testid="designer-gantt-progress"
              className="mt-1 block border px-2 py-1"
            >
              <option value="">(none)</option>
              {FIELDS.filter((f) => f.ttype === "float").map((f) => (
                <option key={f.name} value={f.name}>
                  {f.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      {viewType === "grid" && gridOk && (
        <div data-testid="ee-grid-panel" className="space-y-2">
          <label className="block text-sm">
            adjustment
            <select
              value={gridAdjustment}
              onChange={(e) => setGridAdjustment(e.target.value)}
              data-testid="designer-grid-adjustment"
              className="mt-1 block border px-2 py-1"
            >
              <option value="increment">increment</option>
              <option value="value">value</option>
            </select>
          </label>
          <p className="text-xs text-muted">
            row={gridRowField} col={gridColField} measure={gridMeasure}
          </p>
        </div>
      )}

      {viewType === "cohort" && (
        <div data-testid="ee-cohort-panel">
          <label className="block text-sm">
            mode
            <select
              value={cohortMode}
              onChange={(e) => setCohortMode(e.target.value as "retention" | "churn")}
              data-testid="designer-cohort-mode"
              className="mt-1 block border px-2 py-1"
            >
              <option value="retention">retention</option>
              <option value="churn">churn</option>
            </select>
          </label>
        </div>
      )}

      <button
        type="button"
        data-testid="ee-preview-refresh"
        className="rounded border px-3 py-1 text-sm"
        onClick={() => void refresh()}
      >
        Refresh preview
      </button>

      <pre data-testid="ee-arch-preview" className="overflow-x-auto rounded border p-3 text-xs">
        {arch || "(empty)"}
      </pre>
      <pre data-testid="ee-spec-json" className="hidden">
        {JSON.stringify(lastSpec)}
      </pre>
    </main>
  );
}
