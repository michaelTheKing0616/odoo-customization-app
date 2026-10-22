"use client";

import { DesignerStudioShell } from "@/components/designer/DesignerStudioShell";
import { DesignerLiveCanvas } from "@/components/designer/DesignerLiveCanvas";
import { DesignerToolsRail, type DesignerRailTabId } from "@/components/designer/DesignerToolsRail";
import { createRef, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { FieldPalette } from "@/components/designer/FieldPalette";
import { FormCanvas } from "@/components/designer/FormCanvas";
import { KanbanCardPreview } from "@/components/designer/KanbanCardPreview";
import { OdooListView, OdooPreviewScope } from "@/components/odoo-preview";
import {
  NicheWidgetPalette,
  type NicheWidgetEntry,
} from "@/components/designer/NicheWidgetPalette";
import { PreviewThemeScope } from "@/components/designer/PreviewThemeScope";
import { DesignerSessionBar } from "@/components/designer/DesignerSessionBar";
import { PropsInspector } from "@/components/designer/PropsInspector";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { TooltipProvider } from "@/components/ui/Tooltip";
import { Kbd } from "@/components/ui/layout-primitives";
import type { CapabilityMatrix, Connection } from "@/lib/api";
import { moveIndex } from "@/components/ui/canvas/ReorderableBlocks";
import type { DesignerCanvasState } from "@/components/designer/designerCanvasState";

type ViewMode =
  | "form"
  | "list"
  | "kanban"
  | "calendar"
  | "graph"
  | "pivot"
  | "map"
  | "activity"
  | "gantt"
  | "cohort"
  | "search";

const ODOO_19_CAPS: CapabilityMatrix = {
  major: 19,
  edition: "community",
  server_version: "19.0",
  ga: true,
  message: "Odoo 19 Community — GA",
  supported: [
    "base_automation_safe_triggers",
    "list_as_list_type",
    "list_tree_fallback",
    "object_create_crud_model",
    "object_write_update_path",
    "related_write_dotted_path",
    "smart_button_inherit_box",
    "view_inject_inherit",
    "view_inject_mutate",
  ],
  unsupported: [],
};

const MOCK_CONNECTION: Connection = {
  id: "e2e-mock-19",
  name: "E2E Mock Odoo 19",
  url: "http://127.0.0.1:8069",
  db_name: "odoo_dev",
  username: "admin",
  server_version: "19.0",
  write_mode: "standard",
  created_at: null,
  updated_at: null,
  capabilities: ODOO_19_CAPS,
};

const SAMPLE_PALETTE = [
  { name: "x_name", ttype: "char", label: "Name" },
  { name: "x_stage", ttype: "selection", label: "Stage" },
  { name: "x_partner_id", ttype: "many2one", label: "Customer" },
  { name: "x_priority", ttype: "selection", label: "Priority" },
  { name: "x_amount", ttype: "float", label: "Amount" },
  { name: "x_notes", ttype: "text", label: "Notes" },
];

const SAMPLE_FORM_GROUPS = [
  {
    id: "g1",
    string: "General",
    fields: [
      { id: "f1", name: "x_name", string: "Name" },
      { id: "f2", name: "x_partner_id", string: "Customer" },
      { id: "f3", name: "x_priority", string: "Priority" },
    ],
  },
  {
    id: "g2",
    string: "Details",
    fields: [
      { id: "f4", name: "x_amount", string: "Amount" },
      { id: "f5", name: "x_notes", string: "Notes" },
    ],
  },
];

const SAMPLE_LIST_COLUMNS = [
  { id: "c1", name: "x_name", string: "Name" },
  { id: "c2", name: "x_stage", string: "Stage" },
  { id: "c3", name: "x_partner_id", string: "Customer" },
  { id: "c4", name: "x_amount", string: "Amount" },
];

const SAMPLE_KANBAN_FIELDS = [
  { id: "k1", name: "x_name", string: "Name" },
  { id: "k2", name: "x_partner_id", string: "Customer" },
  { id: "k3", name: "x_amount", string: "Amount" },
  { id: "k4", name: "x_priority", string: "Priority" },
];

const MOCK_NICHE_WIDGETS: NicheWidgetEntry[] = [
  {
    id: "boolean_favorite",
    label: "Favorite star",
    recommended_ttypes: ["boolean"],
  },
  {
    id: "color",
    label: "Color index",
    recommended_ttypes: ["integer"],
  },
  {
    id: "state_selection",
    label: "State selection",
    recommended_ttypes: ["selection"],
  },
];

const MOCK_COLOR_PALETTE = [
  { index: 0, name: "no_color" },
  { index: 1, name: "red" },
  { index: 5, name: "green" },
];

const MOCK_PREVIEW_VARS = {
  "--odoo-primary": "var(--accent8)",
  "--odoo-primary-hover": "var(--accent9)",
  "--odoo-statusbar": "var(--accent8)",
};

function parseMode(raw: string | null): ViewMode {
  const allowed: ViewMode[] = [
    "form",
    "list",
    "kanban",
    "calendar",
    "graph",
    "pivot",
    "map",
    "activity",
    "gantt",
    "cohort",
    "search",
  ];
  if (raw && (allowed as string[]).includes(raw)) return raw as ViewMode;
  return "form";
}

/** `?state=` previews the UI-S-12 canvas states with realistic Odoo messages. */
function parseCanvasState(raw: string | null): DesignerCanvasState | null {
  switch (raw) {
    case "xml-invalid":
      return {
        kind: "xml-invalid",
        line: 14,
        reason: "Opening and ending tag mismatch: group line 9 and form.",
        action: { label: "Open Advanced", onClick: () => undefined },
      };
    case "inherit-conflict":
      return {
        kind: "inherit-conflict",
        locator: "//field[@name='x_partner_id']",
        reason: "Element '<xpath expr=\"//field[@name='x_partner_id']\">' cannot be located in parent view",
        action: { label: "Open Advanced", onClick: () => undefined },
      };
    case "preview-stale":
      return {
        kind: "preview-stale",
        action: { label: "Show layout canvas", onClick: () => undefined },
      };
    default:
      return null;
  }
}

function DesignerHarnessInner() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const searchParams = useSearchParams();
  const mode = parseMode(searchParams.get("mode"));
  const canvasState = parseCanvasState(searchParams.get("state"));
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(() =>
    mode === "form" ? "f1" : mode === "list" ? "c2" : "k2",
  );
  const [kanbanFields, setKanbanFields] = useState(SAMPLE_KANBAN_FIELDS);
  const [listColumns, setListColumns] = useState(SAMPLE_LIST_COLUMNS);
  const [formGroups, setFormGroups] = useState(SAMPLE_FORM_GROUPS);
  const [railTab, setRailTab] = useState<DesignerRailTabId>("fields");
  const iframeRef = createRef<HTMLIFrameElement>();

  const title = "Ticket";
  const model = "x_ticket";

  const selectedMeta = useMemo(() => {
    if (mode === "form") {
      for (const g of formGroups) {
        const f = g.fields.find((x) => x.id === selectedFieldId);
        if (f) return f;
      }
    }
    if (mode === "list") return listColumns.find((c) => c.id === selectedFieldId);
    return kanbanFields.find((f) => f.id === selectedFieldId);
  }, [mode, formGroups, listColumns, kanbanFields, selectedFieldId]);

  function moveInList<T extends { id: string }>(
    items: T[],
    id: string,
    dir: -1 | 1,
  ): T[] {
    const idx = items.findIndex((x) => x.id === id);
    if (idx < 0) return items;
    const next = idx + dir;
    if (next < 0 || next >= items.length) return items;
    const copy = [...items];
    const [item] = copy.splice(idx, 1);
    copy.splice(next, 0, item);
    return copy;
  }

  if (!enabled) {
    return <p>E2E harness disabled</p>;
  }

  const selectedType = selectedMeta
    ? SAMPLE_PALETTE.find((f) => f.name === selectedMeta.name)?.ttype ?? "char"
    : null;

  const propertiesPanel = (
    <PropsInspector title="Field properties">
      {selectedMeta ? (
        <div className="designer-inspector-summary" data-testid="harness-field-summary">
          <p className="designer-inspector-label">{selectedMeta.string || "No label"}</p>
          <p className="designer-inspector-meta">
            <code>{selectedMeta.name}</code>
            <span>{selectedType}</span>
          </p>
          <dl className="designer-inspector-list">
            <div>
              <dt>Label</dt>
              <dd>{selectedMeta.string || "Uses the field label"}</dd>
            </div>
            <div>
              <dt>Widget</dt>
              <dd>Default for {selectedType}</dd>
            </div>
            <div>
              <dt>Saved as</dt>
              <dd>Inherit view on {model}</dd>
            </div>
          </dl>
          <p className="designer-inspector-hint">
            Press <Kbd>↑</Kbd> <Kbd>↓</Kbd> to move the selected field, or drag its grip.
          </p>
        </div>
      ) : (
        <p className="text-xs text-muted">
          Select a field on the canvas, or drag one in from Fields.
        </p>
      )}
    </PropsInspector>
  );

  return (
    <TooltipProvider>
    <main className="min-h-screen bg-background text-ink" data-testid="designer-harness" data-mode={mode}>
      <DesignerStudioShell
        testId="designer-studio-harness"
        flush
        className="min-h-screen"
        title="View designer"
        description={`${MOCK_CONNECTION.name} · drag fields onto the canvas · saves inherit views`}
        sessionBar={
          <div data-testid="harness-connection">
            <DesignerSessionBar
              publishState="unpublished"
              canUndo
              canRedo={false}
              canRollbackPublish={false}
              undoLabel="move field"
              onUndo={() => undefined}
              onRedo={() => undefined}
              onRollbackPublish={() => undefined}
            />
          </div>
        }
        toolbar={
          <div className="designer-toolbar flex flex-wrap items-end gap-3">
            <label className="text-sm">
              <span className="text-muted">Model</span>
              <input
                readOnly
                value={model}
                className="mt-1 block w-64 border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                data-testid="harness-model"
              />
            </label>
            <label className="text-sm">
              <span className="text-muted">View type</span>
              <select
                value={mode}
                onChange={() => undefined}
                disabled
                className="mt-1 block border border-border-subtle bg-surface px-3 py-2"
                data-testid="harness-view-type"
              >
                <option value="form">form</option>
                <option value="list">list</option>
                <option value="kanban">kanban</option>
              </select>
            </label>
            {mode === "kanban" && (
              <label className="text-sm">
                <span className="text-muted">Group by</span>
                <select
                  value="x_stage"
                  disabled
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                  data-testid="harness-groupby"
                >
                  <option value="x_stage">x_stage · selection</option>
                </select>
              </label>
            )}
            <button type="button" className="designer-save-btn ml-auto">
              Save to Odoo
            </button>
          </div>
        }
        notices={<VersionAwarenessBanner capabilities={MOCK_CONNECTION.capabilities} />}
        canvas={
          mode === "form" ? (
            <div data-testid="designer-form-layout">
              <DesignerLiveCanvas
                mode="structure"
                onModeChange={() => undefined}
                liveUrl={null}
                iframeRef={iframeRef}
                iframeKey={1}
                canvasState={canvasState}
                structural={
                  <OdooPreviewScope showBanner previewVars={MOCK_PREVIEW_VARS}>
                    <FormCanvas
                      title={title}
                      statusbar="x_stage"
                      statusbarVisible="new,in_progress,done"
                      groupLayout="two-column"
                      headerButtons={[
                        { id: "confirm", string: "Confirm", variant: "primary" },
                        { id: "cancel", string: "Cancel", variant: "secondary" },
                      ]}
                      smartButtons={[
                        { id: "sb1", string: "Orders", count: 3 },
                        { id: "sb2", string: "Invoices", count: 1 },
                      ]}
                      groups={formGroups}
                      notebooks={[
                        {
                          id: "nb1",
                          pages: [
                            {
                              id: "pg1",
                              string: "Lines",
                              fields: [{ id: "line1", name: "x_qty", string: "Qty" }],
                            },
                            {
                              id: "pg2",
                              string: "Notes",
                              fields: [{ id: "note1", name: "x_notes", string: "Notes" }],
                            },
                          ],
                        },
                      ]}
                      selectedFieldId={selectedFieldId}
                      onSelectField={(id) => {
                        setSelectedFieldId(id);
                        setRailTab("properties");
                      }}
                      onMoveField={(fieldId, dir) => {
                        setFormGroups((groups) =>
                          groups.map((g) => ({
                            ...g,
                            fields: moveInList(g.fields, fieldId, dir),
                          })),
                        );
                      }}
                      onReorderField={(fieldId, groupId, index) => {
                        setFormGroups((groups) =>
                          groups.map((g) =>
                            g.id === groupId
                              ? {
                                  ...g,
                                  fields: moveIndex(
                                    g.fields,
                                    g.fields.findIndex((f) => f.id === fieldId),
                                    index,
                                  ),
                                }
                              : g,
                          ),
                        );
                      }}
                      onDropFieldName={(groupId, fieldName, index) => {
                        setFormGroups((groups) =>
                          groups.map((g) => {
                            if (g.id !== groupId) return g;
                            if (g.fields.some((f) => f.name === fieldName)) return g;
                            const meta = SAMPLE_PALETTE.find((f) => f.name === fieldName);
                            const next = [...g.fields];
                            next.splice(index ?? next.length, 0, {
                              id: `d-${fieldName}`,
                              name: fieldName,
                              string: meta?.label || fieldName,
                            });
                            return { ...g, fields: next };
                          }),
                        );
                      }}
                    />
                  </OdooPreviewScope>
                }
              />
            </div>
          ) : mode === "list" ? (
            <div data-testid="designer-list-layout">
              <DesignerLiveCanvas
                mode="structure"
                onModeChange={() => undefined}
                liveUrl={null}
                iframeRef={iframeRef}
                iframeKey={1}
                canvasState={canvasState}
                structural={
                  <OdooPreviewScope showBanner={false} previewVars={MOCK_PREVIEW_VARS}>
                    <OdooListView
                      view={{
                        type: "list",
                        model: "x_ticket",
                        title,
                        columns: listColumns.map((c) => ({
                          id: c.id,
                          name: c.name,
                          string: c.string || c.name,
                        })),
                        decorations: {
                          danger: "x_priority == 'urgent'",
                          info: "x_stage == 'new'",
                          muted: "x_amount == 0",
                        },
                      }}
                    />
                  </OdooPreviewScope>
                }
              />
            </div>
          ) : (
            <div data-testid="designer-kanban-layout">
              <DesignerLiveCanvas
                mode="structure"
                onModeChange={() => undefined}
                liveUrl={null}
                iframeRef={iframeRef}
                iframeKey={1}
                canvasState={canvasState}
                structural={
                  <PreviewThemeScope previewVars={MOCK_PREVIEW_VARS}>
                    <KanbanCardPreview
                      title={title}
                      groupBy="x_stage"
                      fields={kanbanFields}
                      selectedFieldId={selectedFieldId}
                      onSelectField={setSelectedFieldId}
                      onMoveField={(fieldId, dir) => {
                        setKanbanFields((fields) => moveInList(fields, fieldId, dir));
                      }}
                      onRemoveField={(fieldId) => {
                        setKanbanFields((fields) => fields.filter((f) => f.id !== fieldId));
                        setSelectedFieldId((sel) => (sel === fieldId ? null : sel));
                      }}
                    />
                  </PreviewThemeScope>
                }
              />
            </div>
          )
        }
        rail={
          <DesignerToolsRail
            value={railTab}
            onValueChange={setRailTab}
            tabs={[
              {
                id: "fields",
                label: "Fields",
                content: (
                  <div>
                    <FieldPalette fields={SAMPLE_PALETTE} />
                    {(mode === "form" || mode === "kanban") && (
                      <NicheWidgetPalette
                        widgets={MOCK_NICHE_WIDGETS}
                        colorPalette={MOCK_COLOR_PALETTE}
                        onPick={() => undefined}
                      />
                    )}
                  </div>
                ),
              },
              {
                id: "properties",
                label: "Properties",
                content: propertiesPanel,
              },
            ]}
          />
        }
      />
    </main>
    </TooltipProvider>
  );
}

export default function E2EDesignerHarnessPage() {
  return (
    <Suspense fallback={<p className="p-8">Loading designer harness…</p>}>
      <DesignerHarnessInner />
    </Suspense>
  );
}
